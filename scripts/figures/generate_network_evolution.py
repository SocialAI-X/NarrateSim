"""
Generate a compact network-level evolution figure.

The figure is a condition x stage matrix:
  rows: network-level conditions
  columns: initial, middle, final discussion stages

Outputs:
  paper_figures/fig_network_evolution.pdf
  paper_figures/fig_network_evolution.png
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Dict, Iterable, List

import matplotlib as mpl
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.colors import Normalize, to_rgba


ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = ROOT / "figures"
OUTPUT_DIR.mkdir(exist_ok=True)

STAGES = [
    (0, "Initial"),
    (8, "Middle (R8)"),
    (15, "Final (R15)"),
]


@dataclass(frozen=True)
class NetworkCondition:
    key: str
    label: str
    result_dir: pathlib.Path


CONDITIONS = [
    NetworkCondition(
        key="net_sparse_random",
        label="Sparse random\nBA m=2",
        result_dir=(
            ROOT
            / "results"
            / "full_study_20260521_v3"
            / "net_sparse_random"
        ),
    ),
    NetworkCondition(
        key="net_dense_random",
        label="Dense random\nBA m=5",
        result_dir=(
            ROOT
            / "results"
            / "full_study_20260521_v3"
            / "net_dense_random"
        ),
    ),
    NetworkCondition(
        key="net_dense_hub",
        label="Dense hub\nBA m=5",
        result_dir=(
            ROOT
            / "results"
            / "full_study_20260521_v3"
            / "net_dense_hub"
        ),
    ),
]


mpl.rcParams.update(
    {
        "font.family": "Times New Roman",
        "font.serif": ["Times New Roman"],
        "font.size": 8.0,
        "axes.titlesize": 8.6,
        "axes.labelsize": 8.0,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "legend.fontsize": 7.2,
        "figure.dpi": 300,
        "savefig.dpi": 450,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.01,
        "mathtext.fontset": "stix",
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


def _load_json(path: pathlib.Path) -> Dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _config_value(results: Dict, key: str, fallback_key: str | None = None):
    cfg = results["config"]
    if key in cfg:
        return cfg[key]
    if fallback_key and fallback_key in cfg:
        return cfg[fallback_key]
    raise KeyError(key)


def _build_graph(results: Dict) -> nx.Graph:
    return nx.barabasi_albert_graph(
        _config_value(results, "n_agents"),
        _config_value(results, "network_m"),
        _config_value(results, "seed", "random_seed"),
    )


def _initial_stances(results: Dict) -> Dict[int, float]:
    return {
        int(agent["agent_id"]): float(agent["initial_stance"])
        for agent in results.get("agents_initial", [])
    }


def _round_stances(results: Dict, round_num: int) -> Dict[int, float]:
    if round_num == 0:
        return _initial_stances(results)

    rounds = results.get("rounds", [])
    if round_num < 1 or round_num > len(rounds):
        raise ValueError(f"Round {round_num} is outside available range 1..{len(rounds)}")

    return {
        int(rec["agent_id"]): float(rec["stance"])
        for rec in rounds[round_num - 1].get("records", [])
        if rec.get("stance") is not None and not rec.get("is_malicious", False)
    }


def _negative_stance_ratio(stances: Dict[int, float]) -> float:
    vals = list(stances.values())
    if not vals:
        return 0.0
    return sum(1 for value in vals if value < 0) / len(vals)


def _condition_data(condition: NetworkCondition) -> Dict:
    results = _load_json(condition.result_dir / "results.json")
    summary = _load_json(condition.result_dir / "summary.json")
    graph = _build_graph(results)
    return {
        "condition": condition,
        "results": results,
        "summary": summary,
        "graph": graph,
        "malicious_ids": results["config"]["malicious"]["positions"],
    }


def _valid_malicious_records(results: Dict) -> List[int]:
    return sorted(
        {
            int(rec["agent_id"])
            for rd in results.get("rounds", [])
            for rec in rd.get("records", [])
            if rec.get("is_malicious")
        }
    )


def _draw_hub_edges(
    ax,
    graph: nx.Graph,
    pos: Dict[int, np.ndarray],
    malicious_ids: Iterable[int],
):
    hub_edges = [
        edge
        for edge in graph.edges
        if edge[0] in malicious_ids or edge[1] in malicious_ids
    ]
    nx.draw_networkx_edges(
        graph,
        pos,
        edgelist=hub_edges,
        ax=ax,
        width=0.46,
        edge_color="#E41A1C",
        alpha=0.28,
    )


def _draw_malicious_nodes(
    ax,
    graph: nx.Graph,
    pos: Dict[int, np.ndarray],
    malicious_ids: List[int],
):
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=malicious_ids,
        node_color="#E41A1C",
        node_shape="^",
        node_size=74,
        linewidths=0.0,
        edgecolors="#E41A1C",
        ax=ax,
    )


def _draw_network_snapshot(
    ax,
    graph: nx.Graph,
    pos: Dict[int, np.ndarray],
    stances: Dict[int, float],
    initial_stances: Dict[int, float],
    malicious_ids: List[int],
    cmap,
    norm,
):
    malicious = set(malicious_ids)
    normal_nodes = [n for n in graph.nodes if n not in malicious]
    degrees = dict(graph.degree())

    node_values = [stances.get(n, np.nan) for n in normal_nodes]
    node_colors = [
        cmap(norm(v)) if not np.isnan(v) else (0.88, 0.88, 0.88, 1.0)
        for v in node_values
    ]
    moved_negative = [
        stances.get(n, initial_stances.get(n, 0.0)) < initial_stances.get(n, 0.0)
        for n in normal_nodes
    ]
    edge_colors = [
        to_rgba("#111111", 0.92) if moved else to_rgba("#38464F", 0.46)
        for moved in moved_negative
    ]
    edge_widths = [0.55 if moved else 0.30 for moved in moved_negative]
    node_sizes = [13.5 + 2.1 * np.sqrt(degrees[n]) for n in normal_nodes]

    nx.draw_networkx_edges(
        graph,
        pos,
        ax=ax,
        width=0.24,
        edge_color="#9CA7AD",
        alpha=0.18,
    )
    _draw_hub_edges(ax, graph, pos, malicious_ids)
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=normal_nodes,
        node_color=node_colors,
        node_size=node_sizes,
        linewidths=edge_widths,
        edgecolors=edge_colors,
        ax=ax,
    )
    _draw_malicious_nodes(ax, graph, pos, malicious_ids)
    ax.set_axis_off()


def _add_negative_ratio_badge(ax, ratio: float) -> None:
    accent = to_rgba("#B2182B", 0.15 + 0.35 * ratio)
    ax.text(
        0.05,
        0.05,
        f"Opp. {ratio:.0%}",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=7.2,
        color="#5A0B14",
        bbox={
            "boxstyle": "round,pad=0.20,rounding_size=0.10",
            "facecolor": accent,
            "edgecolor": to_rgba("#B2182B", 0.55),
            "linewidth": 0.45,
        },
    )


def fig_network_evolution() -> None:
    datasets = [_condition_data(condition) for condition in CONDITIONS]
    cmap = plt.get_cmap("RdBu")
    norm = Normalize(vmin=-5, vmax=5)

    fig, axes = plt.subplots(
        len(datasets),
        len(STAGES),
        figsize=(6.85, 4.36),
        squeeze=False,
        gridspec_kw={
            "left": 0.105,
            "right": 0.985,
            "top": 0.860,
            "bottom": 0.085,
            "hspace": 0.00,
            "wspace": 0.00,
        },
    )

    for row, data in enumerate(datasets):
        graph = data["graph"]
        pos = nx.spring_layout(
            graph,
            seed=11,
            k=0.42 if _config_value(data["results"], "network_m") == 3 else 0.34,
            iterations=350,
        )
        initial = _initial_stances(data["results"])
        condition = data["condition"]
        axes[row, 0].text(
            -0.068,
            0.50,
            condition.label,
            transform=axes[row, 0].transAxes,
            ha="right",
            va="center",
            fontsize=8.0,
            linespacing=1.15,
        )

        for col, (round_num, stage_label) in enumerate(STAGES):
            ax = axes[row, col]
            stances = _round_stances(data["results"], round_num)
            _draw_network_snapshot(
                ax,
                graph,
                pos,
                stances,
                initial,
                data["malicious_ids"],
                cmap,
                norm,
            )

            if row == 0:
                ax.set_title(stage_label, pad=2.0, fontsize=8.6, fontweight="medium")

            _add_negative_ratio_badge(ax, _negative_stance_ratio(stances))

    cax = fig.add_axes([0.38, 0.955, 0.30, 0.018])
    sm = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.set_ticks([-5, 0, 5])
    cb.set_ticklabels(["anti -5", "0", "pro +5"])
    cb.ax.set_title("Agent stance", pad=2.0, fontsize=8.0)
    cb.ax.tick_params(length=2, pad=1)

    malicious_handle = plt.Line2D(
        [],
        [],
        marker="^",
        linestyle="",
        color="#E41A1C",
        markeredgecolor="#E41A1C",
        markeredgewidth=0.0,
        markersize=6.3,
        label="malicious agent",
    )
    shifted_handle = plt.Line2D(
        [],
        [],
        marker="o",
        linestyle="",
        color="#1F1F1F",
        markerfacecolor="#FFFFFF",
        markeredgewidth=0.6,
        markersize=4.2,
        label="shifted negative",
    )
    fig.legend(
        handles=[malicious_handle, shifted_handle],
        loc="lower center",
        bbox_to_anchor=(0.53, 0.005),
        frameon=False,
        ncol=2,
        handletextpad=0.35,
        columnspacing=1.0,
    )

    out = OUTPUT_DIR / "fig_network_topology"
    fig.savefig(f"{out}.pdf")
    fig.savefig(f"{out}.png")
    plt.close(fig)

    print(f"  [OK] {out.name}.pdf / .png")
    for data in datasets:
        configured = data["malicious_ids"]
        recorded = _valid_malicious_records(data["results"])
        print(f"  {data['condition'].key}: configured malicious nodes={configured}; records={recorded}")


if __name__ == "__main__":
    fig_network_evolution()
