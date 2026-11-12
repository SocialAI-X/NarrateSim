"""The Python engine must reproduce the browser engine: same RNG, same graphs, same frames."""

import json
from pathlib import Path

import pytest

from nsstudio.engine import Simulation, variant_of
from nsstudio.rng import hash32, normal, u01

FIX = Path(__file__).parent / "fixtures"


def test_rng_vectors():
    v = json.loads((FIX / "rng.json").read_text())
    for *args, h in v["hash"]:
        assert hash32(*args) == h
    for *args, x in v["u01"]:
        assert u01(*args) == x
    for *args, x in v["normal"]:
        assert normal(*args) == pytest.approx(x, abs=1e-12)


GOLDEN = json.loads((FIX / "golden.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", GOLDEN, ids=[g["id"] for g in GOLDEN])
def test_engine_matches_browser(case):
    for gv in case["variants"]:
        rec = Simulation(variant_of(case["scenario"], gv["variant"]), gv["variant"]).run().record()
        assert [list(e) for e in rec["graph"]["edges"]] == gv["edges"]
        assert len(rec["frames"]) == len(gv["frames"])
        for f, g in zip(rec["frames"], gv["frames"]):
            assert f["stances"] == pytest.approx(g["stances"], abs=0.011), f"{gv['variant']} round {f['round']}"
            for k, val in g["metrics"].items():
                assert f["metrics"][k] == pytest.approx(val, abs=2e-4), f"{gv['variant']} round {f['round']} {k}"
            assert [[p["author"], p["reply_to"], p["stance"], p["framing"], p["label"], p["text"]] for p in f["posts"]] == g["posts"]
