"""Properties the studio's claims rest on: determinism, common random numbers, forks, attribution."""

import copy

import pytest

from nsstudio.engine import Simulation, esteban_ray, fork_at, preset, run_triad, triad_summary, variant_of
from nsstudio.network import build_graph, place_attackers
from nsstudio.prompts import parse_decision


def small(pid="hub-victim", n=50, rounds=8):
    s = preset(pid)
    s["society"]["n_agents"] = n
    s["society"]["rounds"] = rounds
    return s


def test_deterministic():
    s = small()
    a = Simulation(copy.deepcopy(s)).run().record()
    b = Simulation(copy.deepcopy(s)).run().record()
    assert [f["stances"] for f in a["frames"]] == [f["stances"] for f in b["frames"]]


def test_twins_identical_before_the_operation_starts():
    s = small(rounds=10)
    s["adversary"]["start"] = 5
    base = Simulation(variant_of(s, "baseline")).run().record()
    att = Simulation(variant_of(s, "attacked")).run().record()
    # Posts written in round 5 are first read in round 6, so rounds 0..5 match exactly.
    for r in range(6):
        assert base["frames"][r]["stances"] == att["frames"][r]["stances"], r
    assert base["frames"][-1]["stances"] != att["frames"][-1]["stances"]


def test_twins_share_honest_agents_at_round_zero():
    s = small()
    runs = run_triad(s)
    means = {v: r["frames"][0]["metrics"]["mean"] for v, r in runs.items()}
    assert len(set(means.values())) == 1, means


def test_fork_reproduces_parent_then_diverges():
    s = small(rounds=10)
    parent = Simulation(variant_of(s, "attacked")).run().record()
    patch = {"adversary": {**s["adversary"], "end": 4}}
    child = fork_at(variant_of(s, "attacked"), 4, patch, parent["meta"]["id"]).run().record()
    for r in range(5):
        assert child["frames"][r]["stances"] == parent["frames"][r]["stances"]
    assert child["frames"][-1]["metrics"]["mean"] != parent["frames"][-1]["metrics"]["mean"]
    assert any(e["kind"] == "fork" for e in child["frames"][4]["events"])


def test_operation_moves_the_target_and_early_prebunking_protects():
    s = small("prebunk-early", n=120, rounds=16)
    runs = run_triad(s)
    summ = triad_summary(runs["baseline"], runs["attacked"], runs["defended"])
    assert summ["attack_effect"] > 0.5
    assert 0.2 < summ["protection"] <= 1.2


def test_earlier_defense_protects_more():
    early = small("prebunk-early", n=120, rounds=16)
    late = small("prebunk-late", n=120, rounds=16)
    pe = triad_summary(*[run_triad(early)[v] for v in ("baseline", "attacked", "defended")])["protection_auc"]
    pl = triad_summary(*[run_triad(late)[v] for v in ("baseline", "attacked", "defended")])["protection_auc"]
    assert pe > pl


def test_placement_and_dose_order_effects():
    def eff(mut):
        s = small(n=120, rounds=16)
        mut(s)
        r = run_triad(s)
        return triad_summary(r["baseline"], r["attacked"])["attack_effect"]

    hub = eff(lambda s: s["adversary"].update(placement="hub"))
    periphery = eff(lambda s: s["adversary"].update(placement="periphery"))
    assert hub > periphery
    assert eff(lambda s: s["adversary"].update(n_attackers=8)) > eff(lambda s: s["adversary"].update(n_attackers=1))


def test_guardian_reports_errors_against_ground_truth():
    s = small("guardian-downrank", n=80, rounds=10)
    s["defenses"] = [{**d, "threshold": 0.5} if d["kind"] == "guardian" else d for d in s["defenses"]]
    rec = Simulation(variant_of(s, "defended")).run().record()
    tp = sum(f["metrics"]["tp"] for f in rec["frames"])
    fp = sum(f["metrics"]["fp"] for f in rec["frames"])
    assert tp > 0 and fp > 0  # a realistic detector catches attackers and some honest people


def test_influence_edges_have_hops():
    rec = Simulation(variant_of(small(n=120, rounds=16), "attacked")).run().record()
    gens = {e["generation"] for f in rec["frames"] for e in f["influence"] if e["via_attack"]}
    assert 1 in gens and any(g >= 2 for g in gens)


@pytest.mark.parametrize("kind", ["scale_free", "small_world", "random", "communities"])
def test_networks_connected_enough(kind):
    s = small(n=80)
    s["network"]["kind"] = kind
    g = build_graph(s)
    assert all(len(a) > 0 for a in g.adj)
    assert len(place_attackers(g, 4, "bridge", 1)) == 4


def test_esteban_ray_bounds():
    assert esteban_ray([0] * 10) == 0
    assert esteban_ray([-5] * 5 + [5] * 5) > esteban_ray([-1] * 5 + [1] * 5)


def test_parse_decision_handles_messy_output():
    raw = """[BDI]
Belief: People seem worried.
Desire: Calm things down.
Intention: reply to Nora
[/BDI]
Sure! {"action": "reply", "target": "Nora Hale", "stance": 7, "confidence": 6, "message": "I hear you."}"""
    d = parse_decision(raw)
    assert d["action"] == "reply" and d["stance"] == 5 and d["target"] == "Nora Hale"
    assert d["bdi"]["desire"] == "Calm things down."
    broken = '{"action": "speak", "stance": -2, "confidence": 4, "message": "unterminated", }'
    assert parse_decision(broken)["stance"] == -2
    assert parse_decision("no json at all")["action"] == "silent"
