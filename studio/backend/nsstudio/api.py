"""HTTP and WebSocket API.

    GET    /api/health                 version, whether an LLM is configured
    GET    /api/presets                built-in scenarios
    POST   /api/simulate               heuristic run with twins, returned inline
    POST   /api/runs                   start a background run (heuristic or LLM), returns its id
    GET    /api/runs                   run summaries
    GET    /api/runs/{id}              the full bundle
    DELETE /api/runs/{id}
    WS     /api/runs/{id}/events       snapshot, then frame-by-frame events while it runs
    POST   /api/sweeps                 factorial sweep with seed replicates
    POST   /api/llm/chat               gateway: chat completion with the server's key

The gateway lets the browser console use LLM agents without ever seeing the key. Bind the server
to localhost (the default) unless you put authentication in front of it.
"""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, store
from .engine import PRESETS, run_triad
from .llm import LLMClient, LLMConfig
from .runner import new_bundle, run_bundle
from .scenario import validate_scenario
from .sweep import AXES, METRICS, run_sweep

app = FastAPI(title="NarrateSim Studio", version=__version__)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def private_network_access(request: Request, call_next):
    # Lets the GitHub Pages console (https) reach a server on localhost in Chromium browsers.
    if request.method == "OPTIONS" and request.headers.get("access-control-request-private-network"):
        resp = await call_next(request)
        resp.headers["Access-Control-Allow-Private-Network"] = "true"
        return resp
    return await call_next(request)


CFG = LLMConfig.from_env()
_gateway: Optional[LLMClient] = None
_subscribers: Dict[str, Set[asyncio.Queue]] = {}
_tasks: Dict[str, asyncio.Task] = {}


def gateway() -> LLMClient:
    global _gateway
    if _gateway is None:
        _gateway = LLMClient(CFG)
    return _gateway


class RunRequest(BaseModel):
    scenario: Dict[str, Any]
    mind: Optional[str] = Field(None, pattern="^(heuristic|llm)$")
    twins: bool = True
    name: Optional[str] = None


class SweepRequest(BaseModel):
    scenario: Dict[str, Any]
    x: str
    y: Optional[str] = None
    metric: str = "attack_effect"
    seeds: int = Field(4, ge=1, le=30)


class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    temperature: float = 0.8
    max_tokens: int = Field(500, le=4000)
    model: Optional[str] = None


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "version": __version__, "llm_configured": CFG.configured, "model": CFG.model or None, "axes": sorted(AXES), "metrics": METRICS}


@app.get("/api/presets")
def presets() -> List[Dict[str, Any]]:
    return PRESETS


@app.post("/api/simulate")
async def simulate(body: Dict[str, Any]) -> Dict[str, Any]:
    scenario = validate_scenario(body.get("scenario", body))
    scenario["engine"]["mind"] = "heuristic"
    runs = await asyncio.to_thread(run_triad, scenario)
    return {"scenario": scenario, "runs": runs}


async def _publish(run_id: str, event: Dict[str, Any]) -> None:
    for q in list(_subscribers.get(run_id, ())):
        q.put_nowait(event)


@app.post("/api/runs")
async def create_run(req: RunRequest) -> Dict[str, Any]:
    scenario = validate_scenario(req.scenario)
    if (req.mind or scenario["engine"]["mind"]) == "llm" and not CFG.configured:
        raise HTTPException(400, "No LLM configured on the server")
    bundle = new_bundle(scenario, req.name)
    store.save(bundle)

    async def job() -> None:
        try:
            await run_bundle(bundle, req.mind, req.twins, lambda e: _publish(bundle["id"], e), CFG)
        except Exception:  # noqa: BLE001 - recorded in the bundle
            pass
        finally:
            _tasks.pop(bundle["id"], None)

    _tasks[bundle["id"]] = asyncio.create_task(job())
    return {"id": bundle["id"], "status": "running"}


@app.get("/api/runs")
def list_runs() -> Dict[str, Any]:
    return {"runs": store.summaries()}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> Dict[str, Any]:
    try:
        b = store.load(run_id)
    except ValueError:
        raise HTTPException(400, "bad run id")
    if not b:
        raise HTTPException(404, "no such run")
    b.pop("llm_log", None) if len(b.get("llm_log", [])) > 2000 else None
    return b


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str) -> Dict[str, Any]:
    t = _tasks.get(run_id)
    if t:
        t.cancel()
    try:
        return {"deleted": store.delete(run_id)}
    except ValueError:
        raise HTTPException(400, "bad run id")


@app.websocket("/api/runs/{run_id}/events")
async def run_events(ws: WebSocket, run_id: str) -> None:
    await ws.accept()
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(run_id, set()).add(q)
    try:
        b = store.load(run_id)
        await ws.send_json({"type": "snapshot", "bundle": b})
        if not b or b.get("status") in ("done", "error"):
            return
        while True:
            e = await q.get()
            await ws.send_json(e)
            if e.get("type") == "status" and e.get("status") in ("done", "error"):
                return
    except WebSocketDisconnect:
        pass
    finally:
        _subscribers.get(run_id, set()).discard(q)
        try:
            await ws.close()
        except RuntimeError:
            pass


@app.post("/api/sweeps")
async def sweeps(req: SweepRequest) -> Dict[str, Any]:
    scenario = validate_scenario(req.scenario)
    try:
        cells = await asyncio.to_thread(run_sweep, scenario, req.x, req.y, req.metric, req.seeds)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"x": req.x, "y": req.y, "metric": req.metric, "seeds": req.seeds, "cells": cells}


@app.post("/api/llm/chat")
async def llm_chat(req: ChatRequest) -> Dict[str, Any]:
    if not CFG.configured:
        raise HTTPException(503, "No LLM configured on the server")
    try:
        return await gateway().raw({"messages": req.messages, "temperature": req.temperature, "max_tokens": req.max_tokens, **({"model": req.model} if req.model else {})})
    except RuntimeError as e:
        raise HTTPException(502, str(e))


# The built console, when present (studio/web/dist), is served at /.
_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_DIST / "index.html")

    @app.get("/favicon.svg")
    def favicon() -> FileResponse:
        return FileResponse(_DIST / "favicon.svg")
