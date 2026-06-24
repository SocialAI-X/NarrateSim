import asyncio
import json
import os
import random
import re
import time
from typing import Any, Dict, Optional

from openai import AsyncOpenAI, RateLimitError


class _GlobalStats:
    """Shared statistics across all LLMClient instances."""

    _instance = None

    def __init__(self):
        self.total_success = 0
        self.total_errors = 0
        self.total_ratelimit = 0
        self.start_time = time.monotonic()
        self._lock = asyncio.Lock()

    @classmethod
    def get(cls) -> "_GlobalStats":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    def record_success(self):
        self.total_success += 1

    def record_error(self, is_ratelimit: bool = False):
        self.total_errors += 1
        if is_ratelimit:
            self.total_ratelimit += 1

    def summary(self) -> str:
        elapsed = time.monotonic() - self.start_time
        rps = self.total_success / max(elapsed, 1)
        return (f"calls={self.total_success} ok, errors={self.total_errors} "
                f"(rl={self.total_ratelimit}), speed={rps:.1f} req/s, "
                f"elapsed={elapsed/60:.1f}min")


class _GlobalRateLimiter:
    """Token-bucket rate limiter shared across all LLMClient instances."""

    _instance = None

    def __init__(self, rpm: int = 350):
        self._interval = 60.0 / rpm
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    @classmethod
    def get(cls, rpm: int = 350) -> "_GlobalRateLimiter":
        if cls._instance is None:
            cls._instance = cls(rpm)
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self._last_call + self._interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()


class LLMClient:
    """Async LLM client with shared global stats and rate limiting."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_concurrent: int = 20,
        global_rpm: int = 350,
    ):
        api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("SILICONFLOW_API_KEY")
        if not api_key:
            raise ValueError(
                "API key required. Set OPENAI_API_KEY or SILICONFLOW_API_KEY environment variable."
            )
        base_url = base_url or os.environ.get(
            "OPENAI_BASE_URL", "https://api.siliconflow.cn/v1/"
        )
        model = model or os.environ.get(
            "LLM_MODEL", "Pro/deepseek-ai/DeepSeek-V3.2"
        )
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._max_retries = 10
        self._base_delay = 3.0
        self._rate_limiter = _GlobalRateLimiter.get(global_rpm)
        self._stats = _GlobalStats.get()
        # Per-instance counters (for per-experiment reporting)
        self._error_count = 0
        self._success_count = 0

    async def query(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        async with self.semaphore:
            for attempt in range(self._max_retries):
                await self._rate_limiter.acquire()
                try:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    self._success_count += 1
                    self._stats.record_success()
                    return response.choices[0].message.content
                except RateLimitError:
                    self._error_count += 1
                    self._stats.record_error(is_ratelimit=True)
                    wait = self._base_delay * (2 ** min(attempt, 4)) + random.uniform(2, 5)
                    if self._stats.total_ratelimit % 50 == 1:
                        print(f"  [LLM] {self._stats.summary()} | "
                              f"RateLimit retry {attempt+1}, wait={wait:.0f}s", flush=True)
                    await asyncio.sleep(wait)
                except Exception as e:
                    self._error_count += 1
                    self._stats.record_error(is_ratelimit=False)
                    if attempt == self._max_retries - 1:
                        print(f"  [LLM] FINAL FAIL: {type(e).__name__}: {str(e)[:120]}", flush=True)
                        raise
                    if self._stats.total_errors % 30 == 1:
                        print(f"  [LLM] {self._stats.summary()} | "
                              f"Error retry {attempt+1}: {type(e).__name__}: {str(e)[:60]}", flush=True)
                    await asyncio.sleep(self._base_delay * (attempt + 1))

    async def query_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        raw = await self.query(system_prompt, user_prompt, temperature, max_tokens)
        return self._parse_json(raw)

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        text = text.strip()
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            raise ValueError(f"Cannot parse JSON from response: {text[:200]}")
