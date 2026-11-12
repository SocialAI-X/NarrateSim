"""OpenAI-compatible LLM client and the LLM minds for the Python engine.

Configuration comes from the environment (or ``studio/backend/.env``):

    NARRATESIM_LLM_BASE_URL   e.g. https://api.deepseek.com/v1
    NARRATESIM_LLM_MODEL      e.g. deepseek-chat
    NARRATESIM_LLM_API_KEY    never written to run files or logs
    NARRATESIM_LLM_CONCURRENCY  parallel requests (default 16)
    NARRATESIM_LLM_EXTRA_BODY   optional JSON merged into every request (provider-specific options)

OPENAI_BASE_URL / OPENAI_API_KEY / LLM_MODEL are accepted as fallbacks.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .prompts import agent_prompt, attacker_prompt, parse_decision


def load_env_file(path: Optional[Path] = None) -> None:
    """Minimal .env reader: KEY=VALUE lines, existing environment wins."""
    path = path or Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class LLMConfig:
    base_url: str = ""
    model: str = ""
    api_key: str = field(default="", repr=False)
    concurrency: int = 16
    temperature: float = 0.8
    timeout: float = 90.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        load_env_file()
        e = os.environ.get
        return cls(
            base_url=(e("NARRATESIM_LLM_BASE_URL") or e("OPENAI_BASE_URL") or "").rstrip("/"),
            model=e("NARRATESIM_LLM_MODEL") or e("LLM_MODEL") or "",
            api_key=e("NARRATESIM_LLM_API_KEY") or e("OPENAI_API_KEY") or "",
            concurrency=int(e("NARRATESIM_LLM_CONCURRENCY") or 16),
        )

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model and self.api_key)


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self.sem = asyncio.Semaphore(cfg.concurrency)
        self.calls = 0
        self.errors = 0
        self.tokens = 0
        self._http: Optional[httpx.AsyncClient] = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.cfg.timeout)
        return self._http

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def raw(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """POST a chat-completions body; returns the provider's JSON."""
        if not self.cfg.configured:
            raise RuntimeError("No LLM configured: set NARRATESIM_LLM_BASE_URL, NARRATESIM_LLM_MODEL and NARRATESIM_LLM_API_KEY")
        body = {**body, "model": body.get("model") or self.cfg.model}
        extra = os.environ.get("NARRATESIM_LLM_EXTRA_BODY")
        if extra:
            body = {**json.loads(extra), **body}
        http = await self._client()
        async with self.sem:
            for attempt in range(4):
                try:
                    res = await http.post(f"{self.cfg.base_url}/chat/completions", json=body, headers={"Authorization": f"Bearer {self.cfg.api_key}"})
                except httpx.HTTPError:
                    if attempt == 3:
                        self.errors += 1
                        raise
                    await asyncio.sleep(1.0 * 2**attempt + random.random())
                    continue
                if res.status_code == 429 or res.status_code >= 500:
                    await asyncio.sleep(1.0 * 2**attempt + random.random())
                    continue
                if res.status_code >= 400:
                    self.errors += 1
                    raise RuntimeError(f"LLM error {res.status_code}: {res.text[:300]}")
                j = res.json()
                self.calls += 1
                self.tokens += int((j.get("usage") or {}).get("total_tokens") or 0)
                return j
        self.errors += 1
        raise RuntimeError("LLM endpoint kept failing")

    async def chat(self, system: str, user: str, temperature: Optional[float] = None, max_tokens: int = 500) -> str:
        body: Dict[str, Any] = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": self.cfg.temperature if temperature is None else temperature,
            "max_tokens": max_tokens,
        }
        j = await self.raw(body)
        return ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


class LLMMinds:
    """The adapter the engine's generator yields to: agent decisions and operation posts."""

    def __init__(self, client: LLMClient, topic: Dict[str, Any], target: int, log: Optional[List[Dict[str, Any]]] = None):
        self.client = client
        self.topic = topic
        self.target = target
        self.log = log if log is not None else []
        self._base = (client.calls, client.tokens)

    def stats(self) -> Dict[str, int]:
        """Calls and tokens spent by this run (the client may be shared across twins)."""
        return {"llm_calls": self.client.calls - self._base[0], "tokens": self.client.tokens - self._base[1]}

    async def decide(self, ctx: List[Dict[str, Any]], rnd: int) -> List[Optional[Dict[str, Any]]]:
        async def one(c: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            a = c["agent"]
            t0 = time.perf_counter()
            try:
                pr = agent_prompt(a, self.topic, c["feed"], rnd, c["names"], c["defense"])
                raw = await self.client.chat(pr["system"], pr["user"], self.client.cfg.temperature + (a["id"] % 7) * 0.02)
                d = parse_decision(raw)
                self.log.append({"round": rnd, "agent": a["id"], "ms": int((time.perf_counter() - t0) * 1000), "ok": True})
                reply_id = None
                if d["target"]:
                    first = d["target"].lower().split(" ")[0]
                    reply_id = next((it["post"]["author"] for it in c["feed"] if c["names"](it["post"]["author"]).lower().startswith(first)), None)
                return {
                    "stance": d["stance"] if d["stance"] is not None else a["stance"],
                    "confidence": d["confidence"] if d["confidence"] is not None else a["confidence"],
                    "post": d["action"] != "silent" and bool(d["message"]),
                    "reply_to": reply_id if d["action"] == "reply" else None,
                    "agreeing": False,
                    "text": d["message"],
                    "bdi": d["bdi"] or c["heuristic"].bdi,
                }
            except Exception as e:  # noqa: BLE001 - a failed call falls back to the heuristic decision
                self.log.append({"round": rnd, "agent": a["id"], "ms": int((time.perf_counter() - t0) * 1000), "ok": False, "error": str(e)[:200]})
                return None

        return list(await asyncio.gather(*(one(c) for c in ctx)))

    async def attack(self, ctx: List[Dict[str, Any]], rnd: int) -> List[Optional[str]]:
        async def one(c: Dict[str, Any]) -> Optional[str]:
            try:
                pr = attacker_prompt(c["agent"], self.topic, c["framing"], self.target, c["feed"], rnd, c["escalation"], c["reply"], c["echo"])
                raw = await self.client.chat(pr["system"], pr["user"], 0.9)
                m = re.search(r"\{[\s\S]*\}", raw)
                msg = json.loads(m.group(0)).get("message") if m else raw
                return msg.strip()[:700] if isinstance(msg, str) and msg.strip() else None
            except Exception:  # noqa: BLE001
                return None

        return list(await asyncio.gather(*(one(c) for c in ctx)))
