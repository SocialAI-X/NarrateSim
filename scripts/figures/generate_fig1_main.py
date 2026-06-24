"""
Figure 1 — Main trajectories (2x4 panel).

Top row: mean stance over rounds 1-15 (four topics).
Bottom row: cumulative emotional negativity index (ENI) over rounds 1-15.
Lines: Baseline + per-topic top strategies covering the strongest stance harm
and the strongest emotional negativity (ENI) harm.
95% CI: agent-level SEM for stance; Wilson intervals for cumulative ENI.

Outputs: latex_paper/figures/fig_study1_trajectories.{pdf,png}
"""

from __future__ import annotations

import json
import pathlib
from typing import Dict, List, Tuple

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
RESULTS_BASE = ROOT / "results" / "full_study_20260521_v3"
OUTPUT_DIR = ROOT / "latex_paper" / "figures"
OUTPUT_DIR.mkdir(exist_ok=True)

TOPICS = [
    ("vaccine", "Vaccine"),
    ("climate", "Climate"),
    ("immigration", "Immigration"),
    ("gmo_food", "GMO Food"),
]

ALL_ATTACKS = [
    "victim_narrative",
    "fear_appeal",
    "pseudo_rational",
    "conspiracy_theory",
    "authority_manipulation",
    "social_proof",
]

Z = 1.96

# Muted, colorblind-safe academic palette inspired by Nature/ACL figures.
# Baseline stays neutral; attack strategies use dark, high-contrast hues.
PALETTE = {
    "baseline": "#7A8CA0",              # slate blue-gray
    "pseudo_rational": "#1F4E79",       # deep academic blue
    "victim_narrative": "#A51C30",      # muted crimson
    "authority_manipulation": "#C46A1B",# burnt orange
    "conspiracy_theory": "#7B3294",     # muted purple
    "fear_appeal": "#2A7F62",           # deep teal
    "social_proof": "#9AA64A",          # muted olive
    "gaslighting": "#5B6770",           # dark gray
}

STRATEGY_LABELS = {
    "baseline": "Baseline",
    "victim_narrative": "Victim Narrative",
    "pseudo_rational": "Pseudo-Rational",
    "authority_manipulation": "Authority Manip.",
    "fear_appeal": "Fear Appeal",
    "emotional_flooding": "Emo. Flooding",
    "conspiracy_theory": "Conspiracy",
    "gaslighting": "Gaslighting",
    "social_proof": "Social Proof",
}

_STRATEGY_MARKERS = {
    "baseline": ("o", 2),
    "victim_narrative": ("s", 5),
    "pseudo_rational": ("D", 6),
    "authority_manipulation": ("^", 6),
    "conspiracy_theory": ("P", 4),
    "fear_appeal": ("v", 4),
    "social_proof": ("X", 4),
    "gaslighting": ("X", 4),
}

mpl.rcParams.update({
    "font.family": "Times New Roman",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.sans-serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 7.5,
    "axes.titlesize": 8,
    "axes.labelsize": 7.5,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "legend.fontsize": 6.3,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.01,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.65,
    "lines.solid_capstyle": "round",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})


# ── helpers ──────────────────────────────────────────────────────────────────

def _style_for(strat: str) -> Dict:
    marker, zorder = _STRATEGY_MARKERS.get(strat, ("o", 3))
    color = PALETTE.get(strat, "#333333")
    filled = strat in ("pseudo_rational", "authority_manipulation", "fear_appeal")
    return {
        "color": color,
        "label": STRATEGY_LABELS.get(strat, strat),
        "ls": "-",
        "marker": marker,
        "lw": 1.55 if strat != "baseline" else 1.20,
        "ms": 3.2 if strat != "baseline" else 3.0,
        "fill_alpha": 0.09 if strat != "baseline" else 0.075,
        "zorder": zorder,
        "markerfacecolor": color if filled else "white",
    }


def _condition_dir(topic: str, strategy: str) -> pathlib.Path:
    return RESULTS_BASE / f"main_{topic}_{strategy}"


def _load_results(topic: str, strategy: str) -> Dict:
    with open(_condition_dir(topic, strategy) / "results.json", encoding="utf-8") as f:
        return json.load(f)


def _load_metrics(topic: str, strategy: str) -> Dict:
    with open(_condition_dir(topic, strategy) / "summary.json", encoding="utf-8") as f:
        return json.load(f)


def _neg_ratio(topic: str, strat: str) -> float:
    ep = _condition_dir(topic, strat) / "emotion_analysis.json"
    if not ep.exists():
        return 0.0
    with open(ep, encoding="utf-8") as f:
        return json.load(f).get("negative_ratio", 0.0)


def _emotion_summary(topic: str, strat: str) -> Tuple[float, float, float]:
    """Return (negative_ratio, positive_ratio, ENI) for updated emotion metrics."""
    ep = _condition_dir(topic, strat) / "emotion_analysis.json"
    if not ep.exists():
        return 0.0, 0.0, 0.0
    with open(ep, encoding="utf-8") as f:
        data = json.load(f)
    neg = data.get("negative_ratio", 0.0)
    pos = data.get("positive_ratio", 0.0)
    eni = neg / (neg + pos) if (neg + pos) > 0 else 0.0
    return neg, pos, eni


def _p2c_rate(topic: str, strat: str) -> float:
    d = _load_results(topic, strat)
    mal = set(d.get("config", {}).get("malicious", {}).get("positions", []))
    init = {
        a["agent_id"]: a["initial_stance"]
        for a in d.get("agents_initial", [])
        if a["agent_id"] not in mal
    }
    fin = {
        a["agent_id"]: a.get("final_stance")
        for a in d.get("agents_final", [])
        if a["agent_id"] not in mal
    }
    n_pos = sum(1 for a in init if init[a] > 0 and a in fin)
    n_p2c = sum(1 for a in init if init[a] > 0 and a in fin and fin[a] < 0)
    return n_p2c / n_pos if n_pos else 0.0


def select_top2_per_topic() -> Dict[str, List[str]]:
    """Pick strategies that cover the strongest stance and ENI harms.

    The updated table reports both stance damage and emotional negativity
    (ENI = P_negative / (P_negative + P_positive)). A pure stance ranking would
    hide victim narratives in some topics despite their strongest ENI effect, so
    each topic gets the worst stance-harm strategy plus the worst ENI-harm
    strategy. If those coincide, the second strategy is chosen by composite harm.
    """
    selection: Dict[str, List[str]] = {}
    for topic_key, _ in TOPICS:
        b_m = _load_metrics(topic_key, "baseline")
        b_shift = b_m["mean_shift"]
        _, _, b_eni = _emotion_summary(topic_key, "baseline")
        b_p2c = _p2c_rate(topic_key, "baseline")
        ranked = []
        for strat in ALL_ATTACKS:
            m = _load_metrics(topic_key, strat)
            shift = m["mean_shift"]
            _, _, eni = _emotion_summary(topic_key, strat)
            p2c = _p2c_rate(topic_key, strat)
            stance_harm = b_shift - shift
            eni_delta = eni - b_eni
            ranked.append({
                "strat": strat,
                "stance_harm": stance_harm,
                "eni_delta": eni_delta,
                "p2c_delta": p2c - b_p2c,
                "composite": stance_harm + 1.5 * eni_delta,
            })
        stance_best = max(ranked, key=lambda r: (r["stance_harm"], r["eni_delta"], r["p2c_delta"]))
        eni_best = max(ranked, key=lambda r: (r["eni_delta"], r["stance_harm"], r["p2c_delta"]))
        selected = [stance_best["strat"]]
        if eni_best["strat"] != selected[0]:
            selected.append(eni_best["strat"])
        else:
            runner_up = max(
                [r for r in ranked if r["strat"] != selected[0]],
                key=lambda r: (r["composite"], r["stance_harm"], r["eni_delta"]),
            )
            selected.append(runner_up["strat"])
        selection[topic_key] = selected
    return selection


# ── trajectory extraction ────────────────────────────────────────────────────

def _initial_stance_stats(results: Dict) -> Tuple[float, float]:
    """Return (mean, sem) of initial stances for normal agents (= Round 0 point)."""
    mal = set(results.get("config", {}).get("malicious", {}).get("positions", []))
    stances = np.array([
        a["initial_stance"]
        for a in results.get("agents_initial", [])
        if a["agent_id"] not in mal
    ], dtype=float)
    m = stances.mean()
    sem = stances.std(ddof=1) / np.sqrt(len(stances)) if len(stances) > 1 else 0.0
    return m, sem


def _per_agent_stance_matrix(results: Dict) -> np.ndarray:
    rounds = results.get("rounds", [])
    if not rounds:
        return np.array([])
    agent_ids = sorted({
        r["agent_id"]
        for rd in rounds
        for r in rd["records"]
        if not r.get("is_malicious")
    })
    idx = {aid: i for i, aid in enumerate(agent_ids)}
    mat = np.full((len(agent_ids), len(rounds)), np.nan)
    for t, rd in enumerate(rounds):
        for rec in rd["records"]:
            if rec.get("is_malicious") or rec.get("stance") is None:
                continue
            if rec["agent_id"] in idx:
                mat[idx[rec["agent_id"]], t] = rec["stance"]
    return mat


def stance_trajectory_ci(
    results: Dict,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Rounds 1..15 using the recorded per-round stance states."""
    mat = _per_agent_stance_matrix(results)
    if mat.size == 0:
        r = np.arange(1, 16)
        z = np.zeros(15)
        return r, z, z, z

    n_valid = np.sum(~np.isnan(mat), axis=0)
    means = np.nanmean(mat, axis=0)
    stds = np.nanstd(mat, axis=0, ddof=1)
    sems = np.where(n_valid > 1, stds / np.sqrt(n_valid), 0.0)

    rounds = np.arange(1, mat.shape[1] + 1)
    return rounds, means, means - Z * sems, means + Z * sems


def _messages_per_round(results: Dict) -> List[int]:
    return [
        sum(1 for r in rd["records"] if not r.get("is_malicious") and r.get("message"))
        for rd in results.get("rounds", [])
    ]


def _wilson_ci(p: float, n: int) -> Tuple[float, float]:
    if n <= 0:
        return p, p
    denom = 1 + Z**2 / n
    center = (p + Z**2 / (2 * n)) / denom
    margin = Z * np.sqrt(p * (1 - p) / n + Z**2 / (4 * n**2)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def emotion_trajectory_ci(
    topic: str, strategy: str, results: Dict,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Rounds 1..15 cumulative ENI.

    ENI follows the updated table definition:
        ENI = P_negative / (P_negative + P_positive)
    The trajectory is cumulative through each round, so the final point matches
    the aggregate ENI in the updated table while avoiding unstable per-round
    spikes from small emotional-message denominators.
    """
    ep = _condition_dir(topic, strategy) / "emotion_analysis.json"
    with open(ep, encoding="utf-8") as f:
        emo = json.load(f)

    neg_by_round = emo.get("negative_ratio_per_round", {})
    pos_by_round = emo.get("positive_ratio_per_round", {})
    if not neg_by_round:
        r = np.arange(1, 16)
        return r, np.zeros(15), np.zeros(15), np.zeros(15)

    data_rounds = sorted(int(k) for k in neg_by_round.keys())
    neg_vals = np.array([
        neg_by_round[str(r)] if str(r) in neg_by_round else neg_by_round.get(r, 0.0)
        for r in data_rounds
    ])
    pos_vals = np.array([
        pos_by_round[str(r)] if str(r) in pos_by_round else pos_by_round.get(r, 0.0)
        for r in data_rounds
    ])
    msg_counts = _messages_per_round(results)
    n_msgs = np.array([
        msg_counts[r - 1] if r - 1 < len(msg_counts) else 100
        for r in data_rounds
    ], dtype=float)

    neg_counts = neg_vals * n_msgs
    pos_counts = pos_vals * n_msgs
    cum_neg = np.cumsum(neg_counts)
    cum_pos = np.cumsum(pos_counts)
    cum_denom = cum_neg + cum_pos
    vals = np.divide(cum_neg, cum_denom, out=np.zeros_like(cum_neg), where=cum_denom > 0)
    ns = [max(1, int(round(n))) for n in cum_denom]
    lo, hi = zip(*[_wilson_ci(p, n) for p, n in zip(vals, ns)])

    return np.array(data_rounds), vals, np.array(lo), np.array(hi)


def _nice_ceil(x: float, step: float) -> float:
    return float(np.ceil(x / step) * step)


def _nice_floor(x: float, step: float) -> float:
    return float(np.floor(x / step) * step)


def _load_topic_series(topic_key: str, strategies: List[str]) -> Dict:
    out = {}
    for strat in strategies:
        results = _load_results(topic_key, strat)
        out[strat] = {
            "stance": stance_trajectory_ci(results),
            "emotion": emotion_trajectory_ci(topic_key, strat, results),
        }
    return out


def _plot_series(ax, rounds, mean, lo, hi, strat: str, ylo: float, yhi: float):
    s = _style_for(strat)
    lo_c = np.clip(lo, ylo, yhi)
    hi_c = np.clip(hi, ylo, yhi)
    ax.fill_between(
        rounds, lo_c, hi_c,
        color=s["color"], alpha=s["fill_alpha"], linewidth=0, zorder=s["zorder"] - 1,
    )
    ax.plot(
        rounds, mean,
        color=s["color"], linestyle=s["ls"], linewidth=s["lw"],
        marker=s["marker"], markersize=s["ms"], markevery=3,
        markerfacecolor=s["markerfacecolor"],
        markeredgewidth=0.85, markeredgecolor=s["color"],
        label=s["label"], zorder=s["zorder"],
    )


# ── main figure ──────────────────────────────────────────────────────────────

def fig1_main_trajectories():
    top2 = select_top2_per_topic()
    print("Per-topic strategies (strongest stance harm + strongest ENI harm):")
    for topic_key, topic_label in TOPICS:
        names = [STRATEGY_LABELS[s] for s in top2[topic_key]]
        print(f"  {topic_label}: {names[0]} + {names[1]}")

    # Collect all unique strategies (for unified legend)
    all_strats_ordered = ["baseline"]
    for topic_key, _ in TOPICS:
        for s in top2[topic_key]:
            if s not in all_strats_ordered:
                all_strats_ordered.append(s)

    data = {}
    for topic_key, topic_label in TOPICS:
        strats = ["baseline"] + top2[topic_key]
        data[topic_key] = {
            "label": topic_label,
            "strategies": strats,
            "series": _load_topic_series(topic_key, strats),
        }

    # Data-driven y-limits: shared within each row, but close to the observed range.
    stance_lo, stance_hi, emo_hi = [], [], []
    for topic_key, _ in TOPICS:
        for strat in data[topic_key]["strategies"]:
            _, _, lo, hi = data[topic_key]["series"][strat]["stance"]
            stance_lo.append(lo.min())
            stance_hi.append(hi.max())
            _, _, _, hi_e = data[topic_key]["series"][strat]["emotion"]
            emo_hi.append(hi_e.max())

    y_stance_min = _nice_floor(min(stance_lo) - 0.08, 0.25)
    y_stance_max = _nice_ceil(max(stance_hi) + 0.08, 0.25)
    y_emo = min(1.0, _nice_ceil(max(emo_hi) + 0.025, 0.05))

    fig = plt.figure(figsize=(7.05, 3.15))
    gs = gridspec.GridSpec(
        2, 4, figure=fig,
        height_ratios=[1, 1],
        hspace=0.20,
        wspace=0.12,
        left=0.075,
        right=0.995,
        top=0.89,
        bottom=0.215,
    )

    panel_letters = list("abcdefgh")

    for col, (topic_key, topic_label) in enumerate(TOPICS):
        ax_stance = fig.add_subplot(gs[0, col])
        ax_emo = fig.add_subplot(gs[1, col], sharex=ax_stance)
        plot_order = data[topic_key]["strategies"]

        for strat in plot_order:
            r_s, m_s, lo_s, hi_s = data[topic_key]["series"][strat]["stance"]
            _plot_series(ax_stance, r_s, m_s, lo_s, hi_s, strat, y_stance_min, y_stance_max)

            r_e, m_e, lo_e, hi_e = data[topic_key]["series"][strat]["emotion"]
            _plot_series(ax_emo, r_e, m_e, lo_e, hi_e, strat, 0.0, y_emo)

        ax_stance.axhline(0, color="#CCCCCC", ls=":", lw=0.5, zorder=0)
        ax_stance.set_title(topic_label, fontsize=8, fontweight="medium", pad=1.5)
        ax_stance.text(
            -0.11, 1.06, f"({panel_letters[col]})",
            transform=ax_stance.transAxes, fontsize=7.5, fontweight="bold",
            va="bottom", ha="left", clip_on=False,
        )
        ax_stance.set_ylim(y_stance_min, y_stance_max)
        ax_stance.set_xlim(0.7, 15.5)
        ax_stance.set_xticks([1, 3, 6, 9, 12, 15])
        ax_stance.tick_params(axis="x", labelbottom=False, length=2, pad=1)
        ax_stance.tick_params(axis="y", length=2, pad=1)
        ax_stance.yaxis.set_major_locator(mticker.MaxNLocator(4))
        ax_stance.grid(axis="y", color="#EDEDED", linewidth=0.45, zorder=0)

        ax_emo.text(
            -0.11, 1.06, f"({panel_letters[col + 4]})",
            transform=ax_emo.transAxes, fontsize=7.5, fontweight="bold",
            va="bottom", ha="left", clip_on=False,
        )
        ax_emo.set_ylim(0, y_emo)
        ax_emo.set_xlim(0.7, 15.5)
        ax_emo.set_xticks([1, 3, 6, 9, 12, 15])
        ax_emo.set_xlabel("")
        ax_emo.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
        ax_emo.yaxis.set_major_locator(mticker.MaxNLocator(4))
        ax_emo.tick_params(length=2, pad=1)
        ax_emo.grid(axis="y", color="#EDEDED", linewidth=0.45, zorder=0)

        if col == 0:
            ax_stance.set_ylabel("Mean Stance", labelpad=2)
            ax_emo.set_ylabel("Cumulative ENI", labelpad=2)
        else:
            ax_stance.tick_params(labelleft=False)
            ax_emo.tick_params(labelleft=False)

    # Unified legend — one entry per unique strategy across all topics
    fig.text(0.535, 0.105, "Round", ha="center", va="center", fontsize=7.5)

    legend_handles = []
    legend_labels = []
    for strat in all_strats_ordered:
        s = _style_for(strat)
        h = plt.Line2D(
            [], [],
            color=s["color"], linestyle=s["ls"], linewidth=s["lw"],
            marker=s["marker"], markersize=s["ms"],
            markerfacecolor=s["markerfacecolor"],
            markeredgewidth=0.85, markeredgecolor=s["color"],
        )
        legend_handles.append(h)
        legend_labels.append(s["label"])

    leg = fig.legend(
        legend_handles, legend_labels,
        loc="lower center",
        ncol=len(all_strats_ordered),
        frameon=True,
        fancybox=False,
        edgecolor="#888888",
        facecolor="white",
        framealpha=1.0,
        borderpad=0.4,
        bbox_to_anchor=(0.5, 0.018),
        columnspacing=1.4,
        handlelength=2.0,
        handletextpad=0.5,
    )
    leg.get_frame().set_linewidth(0.6)

    out = OUTPUT_DIR / "fig_study1_trajectories"
    fig.savefig(f"{out}.pdf", pad_inches=0.01)
    fig.savefig(f"{out}.png", pad_inches=0.01)
    plt.close(fig)
    print(
        f"  [OK] {out.name}.pdf / .png  "
        f"(stance {y_stance_min:.2f} to {y_stance_max:.2f}, ENI 0-{y_emo:.0%})"
    )


if __name__ == "__main__":
    fig1_main_trajectories()
