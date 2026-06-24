"""Publication-quality visualization for top-venue papers.

Style: Okabe-Ito colorblind-safe palette, sans-serif font, 300 dpi.
Each function produces a standalone figure suitable for a paper.
"""

import json
import os
from typing import Dict, List, Optional, Tuple

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 7.5,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.8,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "lines.linewidth": 1.5,
    "lines.markersize": 5,
    "patch.linewidth": 0.5,
})

COLORS = {
    "orange": "#E69F00", "sky_blue": "#56B4E9", "green": "#009E73",
    "yellow": "#F0E442", "blue": "#0072B2", "vermillion": "#D55E00",
    "purple": "#CC79A7", "black": "#000000", "grey": "#999999",
}

STRATEGY_COLORS = {
    "baseline": COLORS["grey"],
    "pseudo_rational": COLORS["blue"],
    "victim_narrative": COLORS["orange"],
    "fear_appeal": COLORS["vermillion"],
    "conspiracy_theory": COLORS["purple"],
    "gaslighting": COLORS["green"],
    "emotional_flooding": "#E8751A",
    "authority_manipulation": COLORS["sky_blue"],
    "auto": COLORS["yellow"],
    "no_intervention": COLORS["vermillion"],
    "fact_check": COLORS["blue"],
    "inoculation": COLORS["green"],
    "community_report": COLORS["orange"],
    "metacognitive": COLORS["purple"],
    "sentiment_transparency": COLORS["sky_blue"],
    "independent": COLORS["blue"],
    "complementary": COLORS["orange"],
    "progressive": COLORS["purple"],
    "representative": COLORS["black"],
    "low_trust": COLORS["vermillion"],
    "high_analytical": COLORS["blue"],
    "high_moral": COLORS["orange"],
    "match_pseudo_lowtrust": COLORS["vermillion"],
    "mismatch_pseudo_highanalytical": COLORS["blue"],
    "match_victim_highmoral": COLORS["orange"],
    "mismatch_victim_highanalytical": COLORS["sky_blue"],
}

STRATEGY_LABELS = {
    "baseline": "Baseline",
    "pseudo_rational": "Pseudo-Rational",
    "victim_narrative": "Victim Narrative",
    "fear_appeal": "Fear Appeal",
    "conspiracy_theory": "Conspiracy Theory",
    "gaslighting": "Gaslighting",
    "emotional_flooding": "Emotional Flooding",
    "authority_manipulation": "Authority Manip.",
    "auto": "Adaptive",
    "no_intervention": "No Intervention",
    "fact_check": "Fact-Check",
    "inoculation": "Inoculation",
    "community_report": "Community Report",
    "metacognitive": "Metacognitive",
    "sentiment_transparency": "Sentiment Transp.",
    "independent": "Independent",
    "complementary": "Complementary",
    "progressive": "Progressive",
    "match_pseudo_lowtrust": "Pseudo-R. × Low Trust",
    "mismatch_pseudo_highanalytical": "Pseudo-R. × High Analyt.",
    "match_victim_highmoral": "Victim × High Moral",
    "mismatch_victim_highanalytical": "Victim × High Analyt.",
}

STRATEGY_MARKERS = {
    "baseline": "o", "pseudo_rational": "s", "victim_narrative": "^",
    "fear_appeal": "D", "conspiracy_theory": "v", "gaslighting": "P",
    "emotional_flooding": "X", "authority_manipulation": "d",
    "auto": "*",
    "no_intervention": "X", "fact_check": "s", "inoculation": "^",
    "community_report": "D", "metacognitive": "v", "sentiment_transparency": "P",
}

STRATEGY_LINESTYLES = {
    "baseline": "-", "pseudo_rational": "--", "victim_narrative": "-.",
    "fear_appeal": ":", "conspiracy_theory": (0, (3, 1, 1, 1)),
    "gaslighting": (0, (5, 2)), "emotional_flooding": (0, (1, 1)),
    "authority_manipulation": (0, (3, 2, 1, 2)),
    "auto": "-",
    "no_intervention": "-", "fact_check": "--", "inoculation": "-.",
    "community_report": ":", "metacognitive": (0, (3, 1, 1, 1)), "sentiment_transparency": "-",
}

EMOTION_CATS = ["anger", "fear", "sadness", "disgust", "trust", "anticipation", "surprise", "neutral"]
EMOTION_COLORS = [
    COLORS["vermillion"], "#E8751A", COLORS["blue"], COLORS["purple"],
    COLORS["green"], COLORS["yellow"], COLORS["sky_blue"], COLORS["grey"],
]


def _label(key: str) -> str:
    return STRATEGY_LABELS.get(key, key.replace("_", " ").title())


def _color(key: str) -> str:
    return STRATEGY_COLORS.get(key, COLORS["grey"])


def save_figure(fig, filepath: str, formats=("pdf", "png")):
    base, _ = os.path.splitext(filepath)
    for fmt in formats:
        fig.savefig(f"{base}.{fmt}", format=fmt, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _get_per_agent_stances_per_round(results: Dict) -> np.ndarray:
    rounds = results.get("rounds", [])
    if not rounds:
        return np.array([])
    agent_ids = sorted(set(
        r["agent_id"] for rd in rounds for r in rd["records"] if not r.get("is_malicious")
    ))
    aid_to_idx = {aid: i for i, aid in enumerate(agent_ids)}
    n_agents = len(agent_ids)
    n_rounds = len(rounds)
    matrix = np.full((n_agents, n_rounds), np.nan)
    for rd_idx, rd in enumerate(rounds):
        for rec in rd["records"]:
            if rec.get("is_malicious") or rec.get("stance") is None:
                continue
            aid = rec["agent_id"]
            if aid in aid_to_idx:
                matrix[aid_to_idx[aid], rd_idx] = rec["stance"]
    return matrix


# ============================================================
# Time-series plots
# ============================================================

def plot_stance_trajectory_ci(results_dict, output_dir, title="Mean Stance Over Rounds"):
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    for key, results in results_dict.items():
        matrix = _get_per_agent_stances_per_round(results)
        if matrix.size == 0:
            continue
        rounds = np.arange(1, matrix.shape[1] + 1)
        means = np.nanmean(matrix, axis=0)
        sems = np.nanstd(matrix, axis=0) / np.sqrt(np.sum(~np.isnan(matrix), axis=0))
        ax.plot(rounds, means, color=_color(key), marker=STRATEGY_MARKERS.get(key, "o"),
                linestyle=STRATEGY_LINESTYLES.get(key, "-"), label=_label(key),
                markevery=2, markersize=4)
        ax.fill_between(rounds, means - 1.96 * sems, means + 1.96 * sems,
                        color=_color(key), alpha=0.12)
    ax.set_xlabel("Round")
    ax.set_ylabel("Mean Stance")
    ax.axhline(0, color=COLORS["grey"], ls=":", lw=0.5, alpha=0.5)
    ax.legend(loc="best", frameon=False)
    ax.set_title(title, fontsize=10)
    save_figure(fig, os.path.join(output_dir, "fig_stance_trajectory_ci"))


def plot_dispersion_trajectory(metrics_dict, output_dir, title="Stance Dispersion Over Rounds"):
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    for key, metrics in metrics_dict.items():
        disp = metrics.get("dispersion_trajectory", [])
        if not disp:
            continue
        rounds = list(range(1, len(disp) + 1))
        ax.plot(rounds, disp, color=_color(key), marker=STRATEGY_MARKERS.get(key, "o"),
                linestyle=STRATEGY_LINESTYLES.get(key, "-"), label=_label(key),
                markevery=2, markersize=4)
    ax.set_xlabel("Round")
    ax.set_ylabel("Stance Std. Dev. (Dispersion)")
    ax.legend(loc="best", frameon=False)
    ax.set_title(title, fontsize=10)
    save_figure(fig, os.path.join(output_dir, "fig_dispersion_trajectory"))


def plot_negative_emotion_trajectory_ci(emotion_data, output_dir, title="Negative Emotion Over Rounds"):
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    for key, data in emotion_data.items():
        neg = data.get("negative_ratio_per_round", {})
        if not neg:
            continue
        rounds = sorted(int(r) for r in neg.keys())
        vals = np.array([neg[str(r)] if str(r) in neg else neg.get(r, 0) for r in rounds])
        n_est = 100
        z = 1.96
        lo = (vals + z**2/(2*n_est) - z*np.sqrt(vals*(1-vals)/n_est + z**2/(4*n_est**2))) / (1 + z**2/n_est)
        hi = (vals + z**2/(2*n_est) + z*np.sqrt(vals*(1-vals)/n_est + z**2/(4*n_est**2))) / (1 + z**2/n_est)
        ax.plot(rounds, vals, color=_color(key), marker="o", markevery=2, markersize=4, label=_label(key))
        ax.fill_between(rounds, np.clip(lo, 0, 1), np.clip(hi, 0, 1), color=_color(key), alpha=0.12)
    ax.set_xlabel("Round")
    ax.set_ylabel("Negative Emotion Ratio")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(loc="best", frameon=False)
    ax.set_title(title, fontsize=10)
    save_figure(fig, os.path.join(output_dir, "fig_negative_emotion_ci"))


# ============================================================
# Bar charts
# ============================================================

def plot_stance_shift_bar(metrics_dict, output_dir, title="Stance Shift by Condition"):
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    keys = list(metrics_dict.keys())
    shifts = [metrics_dict[k]["stance_trajectory"]["change"]["mean_change"] for k in keys]
    colors = [_color(k) for k in keys]
    labels = [_label(k) for k in keys]
    bars = ax.bar(range(len(keys)), shifts, color=colors, width=0.6, edgecolor="white", lw=0.5)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=7)
    ax.set_ylabel("Mean Stance Shift")
    ax.axhline(0, color="grey", ls="-", lw=0.5)
    for bar, val in zip(bars, shifts):
        y = val - 0.08 if val < 0 else val + 0.02
        ax.text(bar.get_x() + bar.get_width()/2, y, f"{val:+.2f}",
                ha="center", va="top" if val < 0 else "bottom", fontsize=7)
    ax.set_title(title, fontsize=10)
    save_figure(fig, os.path.join(output_dir, "fig_stance_shift_bar"))


def plot_metrics_grouped_bar(metrics_dict, emotion_data, output_dir, title="Multi-Metric Comparison"):
    """Grouped bar: stance shift + negative emotion + dispersion."""
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.5))
    keys = list(metrics_dict.keys())
    labels = [_label(k) for k in keys]
    colors = [_color(k) for k in keys]
    x = np.arange(len(keys))

    shifts = [metrics_dict[k]["stance_trajectory"]["change"]["mean_change"] for k in keys]
    axes[0].bar(x, shifts, color=colors, width=0.6, edgecolor="white", lw=0.5)
    axes[0].axhline(0, color="grey", ls="-", lw=0.5)
    axes[0].set_ylabel("Stance Shift")
    axes[0].set_title("(a) Stance Shift", fontsize=9)
    for i, v in enumerate(shifts):
        axes[0].text(i, v + (0.02 if v >= 0 else -0.08), f"{v:+.2f}",
                     ha="center", va="bottom" if v >= 0 else "top", fontsize=6)

    if emotion_data:
        neg = [emotion_data.get(k, {}).get("negative_ratio", 0) for k in keys]
        axes[1].bar(x, neg, color=colors, width=0.6, edgecolor="white", lw=0.5)
        axes[1].set_ylabel("Negative Emotion %")
        axes[1].set_title("(b) Negative Emotion", fontsize=9)
        axes[1].set_ylim(0, max(neg) * 1.25 + 0.01)
        for i, v in enumerate(neg):
            axes[1].text(i, v + 0.005, f"{v:.1%}", ha="center", va="bottom", fontsize=6)

    disp = [metrics_dict[k].get("dispersion_final", metrics_dict[k]["stance_trajectory"]["final"]["std_stance"])
            for k in keys]
    axes[2].bar(x, disp, color=colors, width=0.6, edgecolor="white", lw=0.5)
    axes[2].set_ylabel("Stance Dispersion (Std)")
    axes[2].set_title("(c) Opinion Dispersion", fontsize=9)
    for i, v in enumerate(disp):
        axes[2].text(i, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=6)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=6.5)

    fig.suptitle(title, fontsize=10, y=1.02)
    fig.tight_layout()
    save_figure(fig, os.path.join(output_dir, "fig_metrics_grouped"))


# ============================================================
# Emotion plots
# ============================================================

def plot_emotion_category_stacked(emotion_data, output_dir, title="Emotion Distribution"):
    fig, ax = plt.subplots(figsize=(6, 3.5))
    keys = list(emotion_data.keys())
    labels = [_label(k) for k in keys]
    data = []
    for k in keys:
        dist = emotion_data[k].get("category_distribution", {})
        total = sum(dist.values()) if dist else 1
        data.append([dist.get(c, 0) / total for c in EMOTION_CATS])
    data = np.array(data)
    x = np.arange(len(keys))
    bottom = np.zeros(len(keys))
    for i, (cat, col) in enumerate(zip(EMOTION_CATS, EMOTION_COLORS)):
        ax.bar(x, data[:, i], 0.6, bottom=bottom, label=cat.capitalize(),
               color=col, edgecolor="white", lw=0.3)
        bottom += data[:, i]
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, rotation=20, ha="right")
    ax.set_ylabel("Proportion")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper right", fontsize=6, frameon=False, ncol=2)
    ax.set_title(title, fontsize=10)
    save_figure(fig, os.path.join(output_dir, "fig_emotion_categories"))


def plot_emotion_heatmap(emotion_data, output_dir, title="Emotion Heatmap"):
    fig, ax = plt.subplots(figsize=(7, max(3, len(emotion_data) * 0.55 + 1)))
    keys = list(emotion_data.keys())
    matrix = []
    for k in keys:
        dist = emotion_data[k].get("category_distribution", {})
        total = sum(dist.values()) if dist else 1
        matrix.append([dist.get(c, 0) / total for c in EMOTION_CATS])
    matrix = np.array(matrix)
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto", vmin=0)
    ax.set_xticks(range(len(EMOTION_CATS)))
    ax.set_xticklabels([c.capitalize() for c in EMOTION_CATS], rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([_label(k) for k in keys], fontsize=8)
    for i in range(len(keys)):
        for j in range(len(EMOTION_CATS)):
            v = matrix[i, j]
            ax.text(j, i, f"{v:.1%}", ha="center", va="center",
                    fontsize=6, color="white" if v > 0.25 else "black")
    plt.colorbar(im, ax=ax, shrink=0.8, label="Proportion")
    ax.set_title(title, fontsize=10)
    save_figure(fig, os.path.join(output_dir, "fig_emotion_heatmap"))


# ============================================================
# Cross-topic heatmap (Study 1 overview)
# ============================================================

def plot_cross_topic_heatmap(
    study1_data: Dict[str, Dict],
    metric_key: str = "negative_ratio",
    output_dir: str = ".",
    title: str = "Strategy × Topic",
):
    """Heatmap: rows=strategies, cols=topics, cells=metric value.

    study1_data: {topic: {strategy: {metric_key: value, ...}, ...}, ...}
    """
    topics = sorted(study1_data.keys())
    all_strats = set()
    for t in topics:
        all_strats.update(study1_data[t].keys())
    strategies = [s for s in ["baseline", "pseudo_rational", "victim_narrative",
                              "fear_appeal", "polarization"] if s in all_strats]

    matrix = np.full((len(strategies), len(topics)), np.nan)
    for j, topic in enumerate(topics):
        for i, strat in enumerate(strategies):
            val = study1_data[topic].get(strat, {}).get(metric_key)
            if val is not None:
                matrix[i, j] = val

    fig, ax = plt.subplots(figsize=(max(4, len(topics) * 1.3 + 1), len(strategies) * 0.7 + 1.5))
    cmap = "RdYlGn_r" if "negative" in metric_key or "anger" in metric_key else "RdBu_r"
    vmin = np.nanmin(matrix) if not np.all(np.isnan(matrix)) else 0
    vmax = np.nanmax(matrix) if not np.all(np.isnan(matrix)) else 1

    if metric_key in ("negative_ratio", "anger_ratio", "fear_ratio", "sadness_ratio"):
        vmin, vmax = 0, min(np.nanmax(matrix) * 1.2, 1.0) if not np.all(np.isnan(matrix)) else 0.5

    im = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=vmin, vmax=vmax)
    ax.set_xticks(range(len(topics)))
    ax.set_xticklabels([t.replace("_", " ").title() for t in topics], fontsize=8, rotation=20, ha="right")
    ax.set_yticks(range(len(strategies)))
    ax.set_yticklabels([_label(s) for s in strategies], fontsize=8)

    fmt = ".1%" if "ratio" in metric_key else "+.2f"
    for i in range(len(strategies)):
        for j in range(len(topics)):
            v = matrix[i, j]
            if not np.isnan(v):
                txt = f"{v:{fmt}}"
                ax.text(j, i, txt, ha="center", va="center", fontsize=7,
                        color="white" if abs(v - vmin) > 0.6 * (vmax - vmin) else "black")

    plt.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title(title, fontsize=10)
    save_figure(fig, os.path.join(output_dir, f"fig_heatmap_{metric_key}"))


# ============================================================
# Scatter plots
# ============================================================

def plot_stance_shift_scatter(results_dict, output_dir, title="Initial vs Final Stance"):
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    for key, results in results_dict.items():
        initial = {a["agent_id"]: a["initial_stance"] for a in results["agents_initial"]}
        final = {a["agent_id"]: a["final_stance"] for a in results["agents_final"]}
        common = set(initial) & set(final)
        x = [initial[a] for a in common]
        y = [final[a] for a in common]
        ax.scatter(x, y, c=_color(key), marker=STRATEGY_MARKERS.get(key, "o"),
                   label=_label(key), alpha=0.4, s=15, edgecolors="none")
    ax.plot([-5, 5], [-5, 5], "k--", lw=0.8, alpha=0.3, label="No change")
    ax.set_xlabel("Initial Stance")
    ax.set_ylabel("Final Stance")
    ax.set_xlim(-5.5, 5.5)
    ax.set_ylim(-5.5, 5.5)
    ax.set_aspect("equal")
    ax.legend(loc="upper left", frameon=False, fontsize=6, markerscale=1.5)
    ax.set_title(title, fontsize=10)
    save_figure(fig, os.path.join(output_dir, "fig_stance_scatter"))


# ============================================================
# Violin plot
# ============================================================

def plot_stance_distribution_violin(results_dict, output_dir, title="Final Stance Distribution"):
    try:
        import seaborn as sns
        import pandas as pd
    except ImportError:
        return

    records = []
    order = []
    for key, results in results_dict.items():
        lbl = _label(key)
        order.append(lbl)
        for a in results["agents_final"]:
            records.append({"Condition": lbl, "Final Stance": a["final_stance"]})

    if not records:
        return

    df = pd.DataFrame(records)
    palette = {_label(k): _color(k) for k in results_dict}
    fig, ax = plt.subplots(figsize=(max(5, len(results_dict) * 1.2), 3.8))
    sns.violinplot(data=df, x="Condition", y="Final Stance", hue="Condition",
                   palette=palette, order=order, inner="quartile", ax=ax,
                   cut=0, density_norm="width", legend=False)
    ax.set_xticklabels(order, rotation=25, ha="right", fontsize=7)
    ax.set_ylabel("Final Stance")
    ax.set_xlabel("")
    ax.axhline(0, color=COLORS["grey"], ls=":", lw=0.5, alpha=0.5)
    sns.despine()
    ax.set_title(title, fontsize=10)
    save_figure(fig, os.path.join(output_dir, "fig_stance_violin"))


# ============================================================
# Ablation / sensitivity plot
# ============================================================

def plot_ablation_line(
    x_values: List,
    y_metrics: Dict[str, List],
    x_label: str,
    output_dir: str,
    title: str = "Parameter Sensitivity",
):
    """Line plot for ablation studies: x = parameter, y = multiple metrics."""
    fig, ax = plt.subplots(figsize=(5, 3.5))
    metric_colors = {
        "stance_shift": COLORS["blue"],
        "negative_ratio": COLORS["vermillion"],
        "dispersion_final": COLORS["purple"],
        "extreme_ratio": COLORS["orange"],
    }
    metric_labels = {
        "stance_shift": "Stance Shift",
        "negative_ratio": "Neg. Emotion %",
        "dispersion_final": "Dispersion",
        "extreme_ratio": "Extreme %",
    }
    for metric_name, values in y_metrics.items():
        c = metric_colors.get(metric_name, COLORS["grey"])
        lbl = metric_labels.get(metric_name, metric_name)
        ax.plot(x_values, values, color=c, marker="o", label=lbl, markersize=6)

    ax.set_xlabel(x_label)
    ax.set_ylabel("Metric Value")
    ax.legend(frameon=False)
    ax.set_title(title, fontsize=10)
    save_figure(fig, os.path.join(output_dir, f"fig_ablation_{x_label.lower().replace(' ', '_')}"))


# ============================================================
# Master generator
# ============================================================

def generate_all_plots(results_dict, metrics_dict, output_dir, emotion_data=None):
    os.makedirs(output_dir, exist_ok=True)
    plot_stance_trajectory_ci(results_dict, output_dir)
    plot_dispersion_trajectory(metrics_dict, output_dir)
    plot_stance_shift_bar(metrics_dict, output_dir)
    plot_stance_shift_scatter(results_dict, output_dir)
    plot_stance_distribution_violin(results_dict, output_dir)

    if emotion_data:
        plot_negative_emotion_trajectory_ci(emotion_data, output_dir)
        plot_emotion_category_stacked(emotion_data, output_dir)
        plot_emotion_heatmap(emotion_data, output_dir)
        plot_metrics_grouped_bar(metrics_dict, emotion_data, output_dir)
