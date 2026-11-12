import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NARRATESIM_DATA", str(tmp_path))
    from nsstudio.api import app

    with TestClient(app) as c:
        yield c


def test_health_and_presets(client):
    h = client.get("/api/health").json()
    assert h["ok"] and "strategy" in h["axes"]
    assert len(client.get("/api/presets").json()) >= 8


def test_simulate_inline(client):
    r = client.post("/api/simulate", json={"scenario": {"society": {"n_agents": 40, "rounds": 5}, "defenses": [{"kind": "prebunking", "enabled": True}]}})
    assert r.status_code == 200
    runs = r.json()["runs"]
    assert set(runs) == {"baseline", "attacked", "defended"}
    assert len(runs["attacked"]["frames"]) == 6
    # defaults were filled: every defense kind present, given fields kept, the rest from defaults
    pre = next(d for d in r.json()["scenario"]["defenses"] if d["kind"] == "prebunking")
    assert pre["enabled"] and pre["coverage"] == 0.6 and pre["strength"] == 0.7


def test_validation_rejects_bad_input(client):
    assert client.post("/api/simulate", json={"scenario": {"society": {"n_agents": 3}}}).status_code == 422
    assert client.post("/api/simulate", json={"scenario": {"topic": "nope"}}).status_code == 422
    assert client.post("/api/simulate", json={"scenario": {"surprise": 1}}).status_code == 422


def test_background_run_and_events(client):
    rid = client.post("/api/runs", json={"scenario": {"society": {"n_agents": 30, "rounds": 4}}, "mind": "heuristic"}).json()["id"]
    with client.websocket_connect(f"/api/runs/{rid}/events") as ws:
        types = []
        for _ in range(200):
            e = ws.receive_json()
            types.append(e["type"])
            if e["type"] == "snapshot" and e["bundle"]["status"] == "done":
                break
            if e["type"] == "status":
                break
    for _ in range(50):
        b = client.get(f"/api/runs/{rid}").json()
        if b["status"] == "done":
            break
        time.sleep(0.05)
    assert b["status"] == "done" and b["summary"]["attack_effect"] is not None
    assert any(r["id"] == rid for r in client.get("/api/runs").json()["runs"])
    assert client.delete(f"/api/runs/{rid}").json()["deleted"]
    assert client.get("/api/runs/../../etc").status_code in (400, 404)


def test_sweep(client):
    r = client.post("/api/sweeps", json={"scenario": {"society": {"n_agents": 30, "rounds": 4}}, "x": "placement", "seeds": 2})
    cells = r.json()["cells"]
    assert [c["x"] for c in cells] == ["hub", "bridge", "random", "periphery"]


def test_llm_gateway_without_key(client, monkeypatch):
    from nsstudio import api

    monkeypatch.setattr(api.CFG, "api_key", "")
    assert client.post("/api/llm/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 503
    assert client.post("/api/runs", json={"scenario": {}, "mind": "llm"}).status_code == 400
