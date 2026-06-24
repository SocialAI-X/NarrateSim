"""
Publication-quality network evolution figure for the 5000-agent scale experiment.

Layout: 1 × 3 panel grid  (Initial  →  Mid R5  →  Final R10)
  - Each panel: force-directed network coloured by agent stance (RdBu)
  - Malicious agents rendered as red diamonds at hub positions
  - Inset histogram showing stance distribution with shift annotation
  - Negative-ratio badge and summary statistics

Output:
  paper_figures/fig_scale5000_network_evolution.pdf
  paper_figures/fig_scale5000_network_evolution.png
"""
from __future__ import annotations

import json
import pathlib
from typing import Dict, List

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patheffects as pe
import networkx as nx
import numpy as np
from matplotlib.colors import Normalize, LinearSegmentedColormap, to_rgba
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = ROOT / "latex_paper" / "figures"
OUTPUT_DIR.mkdir(exist_ok=True)

RESULT_DIR = ROOT / "results" / "supplement_20260522" / "scale_experiments" / "scale_5000_agents"
LAYOUT_CACHE = ROOT / ".cache" / "scale5000_network_layout_seed17.npy"

STAGES = [
    (0, "Initial", "(a)"),
    (5, "Round 5", "(b)"),
    (10, "Final (Round 10)", "(c)"),
]

# ── Typography & rcParams ────────────────────────────────────────────────────
mpl.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 7.5,
    "axes.titlesize": 9.0,
    "axes.labelsize": 7.5,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "legend.fontsize": 7.0,
    "figure.dpi": 300,
    "savefig.dpi": 500,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
    "mathtext.fontset": "stix",
    "axes.unicode_minus": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

# ── Custom diverging colourmap (red=anti, blue=pro) ──────────────────────────
_CMAP_COLORS = [
    "#67001F", "#B2182B", "#D6604D", "#F4A582", "#FDDBC7",
    "#F7F7F7",
    "#D1E5F0", "#92C5DE", "#4393C3", "#2166AC", "#053061",
]
STANCE_CMAP = LinearSegmentedColormap.from_list("stance_rdbu", _CMAP_COLORS, N=512)
STANCE_NORM = Normalize(vmin=-5, vmax=5)

MAL_COLOR = "#C62828"
MAL_EDGE_COLOR = "#880E0E"
BG_COLOR = "#FDFDFE"
PANEL_BG = "#F6F7FA"


def _load_json(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_graph(results: dict) -> nx.Graph:
    cfg = results["config"]
    return nx.barabasi_albert_graph(cfg["n_agents"], cfg["network_m"],
                                    cfg.get("seed", cfg.get("random_seed", 42)))


def _initial_stances(results: dict) -> Dict[int, float]:
    return {int(a["agent_id"]): float(a["initial_stance"])
            for a in results.get("agents_initial", [])}


def _round_stances(results: dict, round_num: int) -> Dict[int, float]:
    if round_num == 0:
        return _initial_stances(results)
    rounds = results.get("rounds", [])
    return {int(rec["agent_id"]): float(rec["stance"])
            for rec in rounds[round_num - 1].get("records", [])
            if rec.get("stance") is not None and not rec.get("is_malicious", False)}


def _compute_layout(graph: nx.Graph, seed: int = 17) -> Dict[int, np.ndarray]:
    if LAYOUT_CACHE.exists():
        cached = np.load(LAYOUT_CACHE, allow_pickle=True).item()
        if len(cached) == graph.number_of_nodes():
            return {int(k): np.asarray(v, dtype=float) for k, v in cached.items()}

    n = graph.number_of_nodes()
    k = 2.2 / np.sqrt(n)
    pos = nx.spring_layout(graph, seed=seed, k=k, iterations=150, scale=1.0)
    np.save(LAYOUT_CACHE, pos, allow_pickle=True)
    return pos


def _edge_segments(graph: nx.Graph, pos: dict) -> np.ndarray:
    segs = np.empty((graph.number_of_edges(), 2, 2))
    for i, (u, v) in enumerate(graph.edges()):
        segs[i, 0] = pos[u]
        segs[i, 1] = pos[v]
    return segs


def _draw_network(
    ax, graph: nx.Graph, pos: dict,
    stances: Dict[int, float], initial_stances: Dict[int, float],
    malicious_ids: List[int],
):
    mal_set = set(malicious_ids)
    normal = [n for n in graph.nodes if n not in mal_set]
    degrees = dict(graph.degree())

    # ── Edges ────────────────────────────────────────────────────────────────
    all_segs = _edge_segments(graph, pos)
    lc = LineCollection(all_segs, linewidths=0.06, colors=to_rgba("#8896A0", 0.06), zorder=0)
    ax.add_collection(lc)

    hub_segs = []
    for u, v in graph.edges():
        if u in mal_set or v in mal_set:
            hub_segs.append([pos[u], pos[v]])
    if hub_segs:
        lc_h = LineCollection(hub_segs, linewidths=0.12, colors=to_rgba(MAL_COLOR, 0.07), zorder=1)
        ax.add_collection(lc_h)

    # ── Normal nodes ─────────────────────────────────────────────────────────
    xy = np.array([pos[n] for n in normal])
    vals = np.array([stances.get(n, initial_stances.get(n, 0.0)) for n in normal])
    colors = STANCE_CMAP(STANCE_NORM(vals))

    shifted = np.array([
        stances.get(n, initial_stances.get(n, 0)) < initial_stances.get(n, 0)
        for n in normal
    ])
    edge_c = np.where(shifted[:, None],
                       np.array(to_rgba("#1A1A1A", 0.70)),
                       np.array(to_rgba("#6B7C88", 0.20)))
    edge_w = np.where(shifted, 0.18, 0.05)
    sizes = np.array([1.5 + 0.5 * np.sqrt(degrees.get(n, 1)) for n in normal])

    ax.scatter(xy[:, 0], xy[:, 1], c=colors, s=sizes,
               linewidths=edge_w, edgecolors=edge_c,
               zorder=3, rasterized=True)

    # ── Malicious nodes: glow halo + diamond marker ────────────────────────
    mal_in = [m for m in malicious_ids if m in pos]
    if mal_in:
        mxy = np.array([pos[m] for m in mal_in])
        ax.scatter(mxy[:, 0], mxy[:, 1],
                   s=40, marker="o",
                   linewidths=0, edgecolors="none",
                   facecolors=[to_rgba(MAL_COLOR, 0.08)] * len(mal_in),
                   zorder=4, rasterized=True)
        ax.scatter(mxy[:, 0], mxy[:, 1],
                   c=MAL_COLOR, s=9, marker="D",
                   linewidths=0.2, edgecolors=MAL_EDGE_COLOR,
                   zorder=5, alpha=0.92, rasterized=False)

    pad = 0.05
    ax.set_xlim(xy[:, 0].min() - pad, xy[:, 0].max() + pad)
    ax.set_ylim(xy[:, 1].min() - pad, xy[:, 1].max() + pad)
    ax.set_axis_off()


def _draw_histogram(ax, stances: Dict[int, float], initial: Dict[int, float],
                    round_num: int):
    vals = np.array(list(stances.values()))
    init_vals = np.array(list(initial.values()))

    ax.set_facecolor(to_rgba("#FFFFFF", 0.92))

    bins = np.arange(-5.5, 6.5, 1)

    if round_num > 0:
        ax.hist(init_vals, bins=bins, color=to_rgba("#CFD8DC", 0.46),
                edgecolor="none", linewidth=0, rasterized=True)

    bar_colors = [STANCE_CMAP(STANCE_NORM(b + 0.5)) for b in range(-5, 6)]
    _, _, patches = ax.hist(vals, bins=bins,
                            edgecolor=to_rgba("#37474F", 0.35),
                            linewidth=0.25, rasterized=True)
    for p, c in zip(patches, bar_colors):
        p.set_facecolor(c)

    ax.axvline(0, color="#455A64", lw=0.35, ls="--", alpha=0.45)
    mean_v = np.mean(vals)
    ax.axvline(mean_v, color="#C62828", lw=0.70, alpha=0.85)

    ax.set_xlim(-5.5, 5.5)
    ax.set_xticks([-5, 0, 5])
    ax.set_xticklabels(["−5", "0", "+5"], fontsize=5.5)
    ax.tick_params(axis="y", left=False, labelleft=False)
    ax.tick_params(axis="x", length=1.5, pad=1.0)
    for sp in ax.spines.values():
        sp.set_linewidth(0.25)
        sp.set_color("#90A4AE")

    neg_pct = np.mean(vals < 0) * 100
    ax.text(0.97, 0.86, f"$\\mu$={mean_v:+.1f}  |  {neg_pct:.0f}% neg",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=5.4, color="#B71C1C", fontweight="bold")


def _add_stats_badge(ax, stances: Dict[int, float], initial: Dict[int, float]):
    vals = np.array(list(stances.values()))
    common = set(stances.keys()) & set(initial.keys())
    shifts = np.array([stances[k] - initial[k] for k in common])

    neg_r = np.mean(vals < 0)
    m_shift = np.mean(shifts) if len(shifts) else 0.0

    intensity = min(1.0, neg_r * 1.6)
    bg = to_rgba("#B71C1C", 0.06 + 0.22 * intensity)
    bd = to_rgba("#B71C1C", 0.30 + 0.35 * intensity)

    ax.text(0.98, 0.03,
            f"Neg. {neg_r:.0%}  |  $\\Delta$ = {m_shift:+.2f}",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=5.6, color="#4A0E0E", fontweight="medium",
            bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.10",
                      facecolor=bg, edgecolor=bd, linewidth=0.4))


def _draw_flow_arrow(fig, ax_l, ax_r, y=0.5):
    tr_l, tr_r = ax_l.transAxes, ax_r.transAxes
    inv = fig.transFigure.inverted()
    p1 = inv.transform(tr_l.transform((1.005, y)))
    p2 = inv.transform(tr_r.transform((-0.005, y)))
    arrow = FancyArrowPatch(
        p1, p2,
        arrowstyle="->,head_width=2.5,head_length=2.0",
        color="#90A4AE", linewidth=0.7,
        transform=fig.transFigure, zorder=100,
        mutation_scale=7,
    )
    fig.patches.append(arrow)


def main():
    print("Loading 5000-agent results ...")
    results = _load_json(RESULT_DIR / "results.json")
    summary = _load_json(RESULT_DIR / "summary.json")
    mal_ids = results["config"]["malicious"]["positions"]

    print("Building BA graph (n=5000, m=4) ...")
    G = _build_graph(results)
    print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    print("Computing force-directed layout ...")
    pos = _compute_layout(G, seed=17)
    print("  Layout done.")

    initial = _initial_stances(results)

    # ── Figure (wide appendix layout; histograms sit below panels) ───────────
    fig = plt.figure(figsize=(8.8, 4.35), facecolor=BG_COLOR)

    gs = gridspec.GridSpec(
        2, 3, figure=fig,
        height_ratios=[1.0, 0.19],
        left=0.006, right=0.935,
        top=0.900, bottom=0.115,
        hspace=0.020, wspace=0.030,
    )
    axes = [fig.add_subplot(gs[0, i]) for i in range(3)]
    hist_axes = [fig.add_subplot(gs[1, i]) for i in range(3)]

    for i, (rnd, label, pid) in enumerate(STAGES):
        ax = axes[i]
        ax.set_facecolor(PANEL_BG)

        print(f"  Drawing {label} ...")
        stances = _round_stances(results, rnd)
        if rnd == 0:
            stances = initial.copy()

        _draw_network(ax, G, pos, stances, initial, mal_ids)
        _add_stats_badge(ax, stances, initial)
        _draw_histogram(hist_axes[i], stances, initial, rnd)

        ax.set_title(f"{pid}  {label}", pad=4, fontsize=9.5,
                     fontweight="semibold", color="#263238")

        for sp in ax.spines.values():
            sp.set_visible(True)
            sp.set_linewidth(0.3)
            sp.set_color("#B0BEC5")

    # ── Narrow histogram axes: shrink to ~55 % of column width, centred ─────
    for hax in hist_axes:
        p = hax.get_position()
        new_w = p.width * 0.55
        new_x = p.x0 + (p.width - new_w) / 2
        hax.set_position([new_x, p.y0, new_w, p.height])

    _draw_flow_arrow(fig, axes[0], axes[1])
    _draw_flow_arrow(fig, axes[1], axes[2])

    # ── Colour bar ───────────────────────────────────────────────────────────
    cax = fig.add_axes([0.950, 0.270, 0.010, 0.500])
    sm = mpl.cm.ScalarMappable(norm=STANCE_NORM, cmap=STANCE_CMAP)
    cb = fig.colorbar(sm, cax=cax)
    cb.set_ticks([-5, -3, 0, 3, 5])
    cb.set_ticklabels(["\u22125\nanti", "\u22123", "0", "+3", "+5\npro"])
    cb.set_label("Agent stance", labelpad=3, fontsize=8)
    cb.ax.tick_params(length=2, pad=2, labelsize=6.5)
    cb.outline.set_linewidth(0.35)

    # ── Legend ───────────────────────────────────────────────────────────────
    handles = [
        Line2D([], [], marker="D", ls="", color=MAL_COLOR,
               markeredgecolor=MAL_EDGE_COLOR, markeredgewidth=0.3,
               markersize=5, label="Malicious agent ($n$=100)"),
        Line2D([], [], marker="o", ls="", color="#B2182B",
               markeredgecolor="#5A6B78", markeredgewidth=0.25,
               markersize=4, label="Anti-vaccine stance"),
        Line2D([], [], marker="o", ls="", color="#2166AC",
               markeredgecolor="#5A6B78", markeredgewidth=0.25,
               markersize=4, label="Pro-vaccine stance"),
        Line2D([], [], marker="o", ls="", color="#AAAAAA",
               markeredgecolor="#1A1A1A", markeredgewidth=0.5,
               markersize=4, label="Shifted negative"),
    ]
    fig.legend(handles=handles, loc="lower center",
               bbox_to_anchor=(0.470, 0.010),
               frameon=True, ncol=4,
               handletextpad=0.3, columnspacing=1.2,
               fancybox=True, framealpha=0.80,
               edgecolor="#CFD8DC", fontsize=6.8)

    # ── Title (concise, key info only) ───────────────────────────────────────
    fig.suptitle(
        "Opinion Evolution in a 5,000-Agent Barab\u00e1si\u2013Albert Network",
        fontsize=11.5, fontweight="bold", color="#1B2631", y=0.992,
    )

    # ── Save ─────────────────────────────────────────────────────────────────
    out = OUTPUT_DIR / "fig_scale5k_evolution"
    print(f"Saving to {out}.pdf ...")
    fig.savefig(f"{out}.pdf", facecolor=fig.get_facecolor())
    fig.savefig(f"{out}.png", facecolor=fig.get_facecolor())
    plt.close(fig)

    print(f"\n  [DONE] {out.name}.pdf / .png")
    print(f"  Malicious agents: {len(mal_ids)} at hub positions")
    print(f"  Summary: shift={summary['mean_shift']:+.3f}  "
          f"neg={summary['negativity_ratio']:.1%}  "
          f"flip={summary['flip_rate']:.1%}")


if __name__ == "__main__":
    main()
