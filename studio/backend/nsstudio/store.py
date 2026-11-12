"""Run storage: one JSON bundle per run under a data directory (default ``studio/backend/data``)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def data_dir() -> Path:
    d = Path(os.environ.get("NARRATESIM_DATA") or Path(__file__).resolve().parent.parent / "data")
    (d / "runs").mkdir(parents=True, exist_ok=True)
    return d


def _path(run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", run_id):
        raise ValueError("bad run id")
    return data_dir() / "runs" / f"{run_id}.json"


def save(bundle: Dict[str, Any]) -> Path:
    p = _path(bundle["id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)
    return p


def load(run_id: str) -> Optional[Dict[str, Any]]:
    p = _path(run_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def delete(run_id: str) -> bool:
    p = _path(run_id)
    if p.exists():
        p.unlink()
        return True
    return False


def summaries() -> List[Dict[str, Any]]:
    out = []
    for p in sorted((data_dir() / "runs").glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append(
            {
                "id": b["id"],
                "name": b.get("name"),
                "created": b.get("created"),
                "status": b.get("status", "done"),
                "mind": b["scenario"]["engine"]["mind"],
                "model": b["scenario"]["engine"].get("model"),
                "summary": b.get("summary"),
            }
        )
    return out
