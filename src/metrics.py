"""Metrics computation for simulation results.

All metrics operate ONLY on normal agents — malicious injectors are excluded.
"""

import numpy as np
from typing import Dict, List


def compute_stance_metrics(stances: List[int]) -> Dict:
    arr = np.array(stances, dtype=float)
    return {
        "mean_stance": float(np.mean(arr)),
        "std_stance": float(np.std(arr)),
        "var_stance": float(np.var(arr)),
        "median_stance": float(np.median(arr)),
        "extreme_negative_ratio": float(np.mean(arr <= -4)),
        "extreme_positive_ratio": float(np.mean(arr >= 4)),
        "extreme_total_ratio": float(np.mean((arr <= -4) | (arr >= 4))),
    }


def compute_stance_change(initial_stances: List[int], final_stances: List[int]) -> Dict:
    init = np.array(initial_stances, dtype=float)
    final = np.array(final_stances, dtype=float)
    changes = final - init
    abs_changes = np.abs(changes)

    return {
        "mean_change": float(np.mean(changes)),
        "mean_abs_change": float(np.mean(abs_changes)),
        "max_abs_change": float(np.max(abs_changes)),
        "pct_moved_positive": float(np.mean(changes > 0)),
        "pct_moved_negative": float(np.mean(changes < 0)),
        "pct_unchanged": float(np.mean(changes == 0)),
    }


def esteban_ray_polarization(stances: List[int], alpha: float = 1.6, K: int = 5) -> float:
    """Esteban-Ray polarization index with K=5 bins for better sensitivity."""
    arr = np.array(stances, dtype=float)
    if len(arr) == 0:
        return 0.0

    bins = np.linspace(-5.5, 5.5, K + 1)
    hist, _ = np.histogram(arr, bins=bins)
    proportions = hist / hist.sum()
    bin_centers = (bins[:-1] + bins[1:]) / 2

    er_index = 0.0
    for i in range(K):
        for j in range(K):
            er_index += (proportions[i] ** (1 + alpha)) * proportions[j] * abs(bin_centers[i] - bin_centers[j])

    return float(er_index)


def _filter_normal(records: List[Dict]) -> List[Dict]:
    """Exclude malicious agent records."""
    return [r for r in records if not r.get("is_malicious", False)]


def compute_round_metrics(round_data: Dict) -> Dict:
    normal = _filter_normal(round_data["records"])
    if not normal:
        return {}

    stances = [r["stance"] for r in normal]
    confidences = [r["confidence"] for r in normal]
    actions = [r["action"] for r in normal]

    messages = [r["message"] for r in normal if r.get("message")]
    avg_msg_len = np.mean([len(m.split()) for m in messages]) if messages else 0

    return {
        "stance_metrics": compute_stance_metrics(stances),
        "er_polarization": esteban_ray_polarization(stances),
        "mean_confidence": float(np.mean(confidences)),
        "action_distribution": {
            "speak": sum(1 for a in actions if a == "speak"),
            "reply": sum(1 for a in actions if a == "reply"),
            "silent": sum(1 for a in actions if a == "silent"),
        },
        "avg_message_word_count": float(avg_msg_len),
        "errors": round_data.get("errors", 0),
    }


def compute_stance_flip_rate(initial_stances: List[int], final_stances: List[int]) -> Dict:
    """Stance Flip Rate (立场翻转率): fraction of opinionated agents whose stance
    crossed from one side to the other.

    Counts both directions:
      - positive→negative  (e.g. supporters converted to opponents)
      - negative→positive  (e.g. opponents converted to supporters)

    Agents who start at 0 (neutral) are excluded — they have no "side" to flip from.
    """
    init = np.array(initial_stances, dtype=float)
    final = np.array(final_stances, dtype=float)

    has_side = init != 0
    n_opinionated = int(has_side.sum())
    if n_opinionated == 0:
        return {"flip_rate": 0.0, "n_opinionated": 0,
                "n_flipped": 0, "n_pos_to_neg": 0, "n_neg_to_pos": 0}

    pos_to_neg = has_side & (init > 0) & (final < 0)
    neg_to_pos = has_side & (init < 0) & (final > 0)
    n_p2n = int(pos_to_neg.sum())
    n_n2p = int(neg_to_pos.sum())
    n_flipped = n_p2n + n_n2p

    return {
        "flip_rate": float(n_flipped / n_opinionated),
        "n_opinionated": n_opinionated,
        "n_flipped": n_flipped,
        "n_pos_to_neg": n_p2n,
        "n_neg_to_pos": n_n2p,
    }


def compute_full_metrics(results: Dict) -> Dict:
    initial_stances = [a["initial_stance"] for a in results["agents_initial"]]
    final_stances = [a["final_stance"] for a in results["agents_final"]]

    round_metrics = [compute_round_metrics(rd) for rd in results["rounds"]]

    init_arr = np.array(initial_stances, dtype=float)
    final_arr = np.array(final_stances, dtype=float)

    flip = compute_stance_flip_rate(initial_stances, final_stances)

    return {
        "topic": results["topic"],
        "elapsed_seconds": results["elapsed_seconds"],
        "stance_trajectory": {
            "initial": compute_stance_metrics(initial_stances),
            "final": compute_stance_metrics(final_stances),
            "change": compute_stance_change(initial_stances, final_stances),
        },
        "flip_rate": flip["flip_rate"],
        "n_opinionated": flip["n_opinionated"],
        "n_flipped": flip["n_flipped"],
        "n_pos_to_neg": flip["n_pos_to_neg"],
        "n_neg_to_pos": flip["n_neg_to_pos"],
        "polarization_trajectory": [rm["er_polarization"] for rm in round_metrics],
        "dispersion_trajectory": [
            rm["stance_metrics"]["std_stance"] for rm in round_metrics if rm
        ],
        "extreme_trajectory": [
            rm["stance_metrics"]["extreme_total_ratio"] for rm in round_metrics if rm
        ],
        "er_polarization_initial": esteban_ray_polarization(initial_stances),
        "er_polarization_final": esteban_ray_polarization(final_stances),
        "dispersion_initial": float(np.std(init_arr)),
        "dispersion_final": float(np.std(final_arr)),
        "extreme_ratio_initial": float(np.mean((np.abs(init_arr) >= 3))),
        "extreme_ratio_final": float(np.mean((np.abs(final_arr) >= 3))),
        "disagreement_final": float(np.mean(np.abs(
            final_arr[:, None] - final_arr[None, :]
        ))) if len(final_arr) > 1 else 0.0,
        "round_metrics": round_metrics,
    }
