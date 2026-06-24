"""
Generate final Study 2 (population × strategy) figures for EMNLP.
Uses ONLY metrics already defined in the paper's main table:
  s̄_T, Δs̄, NSR, EV, ENI
Main text: single-column (3.25 in) ranking chart
Appendix candidates: multiple schemes for the user to pick
"""
from __future__ import annotations
import json, pathlib
from dataclasses import dataclass
from typing import Tuple
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
RESULTS = ROOT / "results" / "full_study_20260521_v3"
OUT = ROOT / "latex_paper" / "figures"
OUT.mkdir(exist_ok=True)

Z = 1.96; SMIN, SMAX = -5, 5

@dataclass(frozen=True)
class C:
    key: str; folder: str; bl_folder: str
    strategy: str; population: str
    short: str; color: str

CONDS: Tuple[C, ...] = (
    C("auth_manip_htrust", "pop_high_trust_authority_manipulation", "pop_high_trust_baseline",
      "Authority Manip.", "High-trust", "Auth.\u00d7H-Trust", "#882255"),
    C("victim_hanalyt", "pop_high_analytical_victim_narrative", "pop_high_analytical_baseline",
      "Victim Narrative", "High-analytical", "Victim\u00d7H-Analyt.", "#332288"),
    C("victim_hempathy", "pop_high_empathy_victim_narrative", "pop_high_empathy_baseline",
      "Victim Narrative", "High-empathy", "Victim\u00d7H-Empathy", "#D55E00"),
    C("pseudo_htrust", "pop_high_trust_pseudo_rational", "pop_high_trust_baseline",
      "Pseudo-Rational", "High-trust", "Pseudo\u00d7H-Trust", "#0072B2"),
    C("conspiracy_hanalyt", "pop_high_analytical_conspiracy_theory", "pop_high_analytical_baseline",
      "Conspiracy Theory", "High-analytical", "Conspir.\u00d7H-Analyt.", "#56B4E9"),
    C("pseudo_ltrust", "pop_low_trust_pseudo_rational", "pop_low_trust_baseline",
      "Pseudo-Rational", "Low-trust", "Pseudo\u00d7L-Trust", "#009E73"),
    C("fear_author", "pop_authoritarian_fear_appeal", "pop_authoritarian_baseline",
      "Fear Appeal", "Authoritarian", "Fear\u00d7Authorit.", "#CC79A7"),
    C("conspiracy_lanalyt", "pop_low_analytical_conspiracy_theory", "pop_low_analytical_baseline",
      "Conspiracy Theory", "Low-analytical", "Conspir.\u00d7L-Analyt.", "#E69F00"),
)

# ── Times New Roman + EMNLP style ──────────────────────────────────
mpl.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 7,
    "axes.titlesize": 7.5,
    "axes.labelsize": 7,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 5.8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.015,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.5,
    "xtick.major.width": 0.45,
    "ytick.major.width": 0.45,
    "xtick.major.size": 2.0,
    "ytick.major.size": 2.0,
    "xtick.major.pad": 1.5,
    "ytick.major.pad": 1.5,
    "axes.labelpad": 2.0,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

# ── helpers ─────────────────────────────────────────────────────────
def _lj(p): return json.load(open(p, encoding="utf-8"))

def load(c: C):
    base = RESULTS / c.folder
    return {"c": c, "res": _lj(base/"results.json"), "sum": _lj(base/"summary.json"),
            "emo": _lj(base/"emotion_analysis.json")}

def load_bl(c: C):
    base = RESULTS / c.bl_folder
    return {"res": _lj(base/"results.json"), "sum": _lj(base/"summary.json"),
            "emo": _lj(base/"emotion_analysis.json")}

def stance_mat(res):
    inits = {a["agent_id"]: a["initial_stance"] for a in res["agents_initial"]}
    aids = sorted(inits)
    idx = {a: i for i, a in enumerate(aids)}
    rounds = res["rounds"]
    mat = np.full((len(aids), len(rounds)+1), np.nan)
    for a in aids: mat[idx[a], 0] = inits[a]
    for t, rd in enumerate(rounds, 1):
        for rec in rd["records"]:
            if rec.get("is_malicious") or rec["agent_id"] not in idx:
                continue
            if rec.get("stance") is not None:
                mat[idx[rec["agent_id"]], t] = rec["stance"]
    for i in range(mat.shape[0]):
        last = mat[i, 0]
        for t in range(1, mat.shape[1]):
            if np.isnan(mat[i, t]):
                mat[i, t] = last
            else:
                last = mat[i, t]
    return np.arange(mat.shape[1]), mat, aids

def traj_stats(mat):
    m = np.nanmean(mat, 0)
    n = np.sum(~np.isnan(mat), 0)
    sem = np.nanstd(mat, 0, ddof=1) / np.sqrt(n)
    return m, m - Z * sem, m + Z * sem

def paper_metrics(d):
    """Return the 5 metrics exactly matching the paper's main table."""
    s = d["sum"]; e = d["emo"]
    pos_r = e.get("positive_ratio", 0)
    neg_r = e.get("negative_ratio", 0)
    denom = pos_r + neg_r
    ev = (pos_r - neg_r) / denom if denom > 0 else 0.0
    eni = neg_r / denom * 100 if denom > 0 else 0.0
    return {
        "s_T": s["final_mean"],          # s̄_T
        "delta_s": s["mean_shift"],      # Δs̄
        "nsr": s["neg_shift_rate"] * 100, # NSR (%)
        "ev": ev,                         # EV
        "eni": eni,                       # ENI (%)
    }

def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png")
    plt.close(fig)
    print(f"  [saved] {name}")

def neg_per_round(emo, n=15):
    nr = emo.get("negative_ratio_per_round", {})
    return np.array([nr.get(str(r), nr.get(r, 0)) for r in range(1, n+1)])

def sorted_data():
    data = []
    for c in CONDS:
        d = load(c); bl = load_bl(c)
        data.append((c, d, bl))
    data.sort(key=lambda x: x[1]["sum"]["mean_shift"])
    return data


# ═══════════════════════════════════════════════════════════════════
# MAIN TEXT — single-column (3.25 in)
# Panel (a): Δs̄ ranking, (b): NSR ranking
# Both are already defined in the main table — no new metrics needed
# ═══════════════════════════════════════════════════════════════════
def fig_main(sd):
    W = 3.25
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(W, 2.35),
        gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.35})

    y = np.arange(len(sd))[::-1]
    colors = [c.color for c, _, _ in sd]
    labels = [f"{c.strategy}\n{c.population}" for c, _, _ in sd]

    shifts = [d["sum"]["mean_shift"] for _, d, _ in sd]
    nsrs = [d["sum"]["neg_shift_rate"] for _, d, _ in sd]

    # (a) Δs̄
    ax1.barh(y, shifts, height=0.58, color=colors, edgecolor="white", lw=0.25)
    for yi, v in zip(y, shifts):
        ax1.text(0.04, yi, f"{v:+.2f}", va="center", ha="left",
                 fontsize=5.2)
    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontsize=5.5)
    ax1.set_xlabel(r"Mean stance shift ($\Delta\bar{s}$)", fontsize=6.5)
    ax1.set_title(r"(a) $\Delta\bar{s}$  ranking", fontsize=7, pad=3)
    ax1.set_xlim(min(shifts) * 1.15, 0.55)
    ax1.axvline(0, color="#AAAAAA", lw=0.4)
    ax1.grid(axis="x", color="#EFEFEF", lw=0.3)

    # (b) NSR
    ax2.barh(y, nsrs, height=0.58, color=colors, edgecolor="white", lw=0.25)
    for yi, v in zip(y, nsrs):
        ax2.text(v + 0.008, yi, f"{v:.0%}", va="center", fontsize=5.2)
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.set_xlabel("Negative shift rate (NSR)", fontsize=6.5)
    ax2.set_title("(b) NSR ranking", fontsize=7, pad=3)
    ax2.set_xlim(0, max(nsrs) * 1.20)
    ax2.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax2.grid(axis="x", color="#EFEFEF", lw=0.3)

    fig.subplots_adjust(left=0.32, right=0.97, top=0.91, bottom=0.16)
    save(fig, "fig_study2_ranking")


# ═══════════════════════════════════════════════════════════════════
# APPENDIX OPTION 1: Paired barbell — strategy Δs̄ vs baseline Δs̄
# Shows how much worse each pairing is compared to its own baseline
# ═══════════════════════════════════════════════════════════════════
def fig_appendix_opt1(sd):
    """Paired comparison: strategy vs baseline for Δs̄, using connecting lines."""
    W = 6.75
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(W, 2.8),
        gridspec_kw={"width_ratios": [1.2, 1, 1], "wspace": 0.22})

    y = np.arange(len(sd))[::-1]
    colors = [c.color for c, _, _ in sd]
    labels = [f"{c.strategy}\n{c.population}" for c, _, _ in sd]

    # Panel (a): Paired Δs̄ — strategy (dot) vs baseline (gray dot) with connecting line
    for i, (c, d, bl) in enumerate(sd):
        sv = d["sum"]["mean_shift"]
        bv = bl["sum"]["mean_shift"]
        yi = y[i]
        ax1.plot([bv, sv], [yi, yi], color="#CCCCCC", lw=2.8, solid_capstyle="round", zorder=1)
        ax1.scatter(bv, yi, s=24, color="#999999", zorder=3, edgecolor="white", lw=0.3)
        ax1.scatter(sv, yi, s=32, color=c.color, zorder=4, edgecolor="white", lw=0.3)
    ax1.axvline(0, color="#B0B0B0", lw=0.4, ls=":")
    ax1.set_yticks(y); ax1.set_yticklabels(labels, fontsize=5.8)
    ax1.set_xlabel(r"$\Delta\bar{s}$", fontsize=7)
    ax1.set_title(r"(a) $\Delta\bar{s}$: strategy vs. baseline", fontsize=7, pad=3)
    ax1.set_xlim(-2.5, 1.1)
    ax1.grid(axis="x", color="#F0F0F0", lw=0.3)
    h = [Line2D([], [], marker="o", color="#999", lw=0, ms=4, label="Baseline"),
         Line2D([], [], marker="o", color="#333", lw=0, ms=4.5, label="Strategy")]
    ax1.legend(handles=h, loc="lower left", frameon=False, fontsize=5.5)

    # Panel (b): EV
    evs_s = [paper_metrics(d)["ev"] for _, d, _ in sd]
    evs_b = [paper_metrics(bl)["ev"] for _, _, bl in sd]
    for i, (c, d, bl) in enumerate(sd):
        yi = y[i]
        ax2.plot([evs_b[i], evs_s[i]], [yi, yi], color="#CCCCCC", lw=2.8, solid_capstyle="round", zorder=1)
        ax2.scatter(evs_b[i], yi, s=24, color="#999999", zorder=3, edgecolor="white", lw=0.3)
        ax2.scatter(evs_s[i], yi, s=32, color=c.color, zorder=4, edgecolor="white", lw=0.3)
    ax2.axvline(0, color="#B0B0B0", lw=0.4, ls=":")
    ax2.set_yticks(y); ax2.set_yticklabels([])
    ax2.set_xlabel("EV", fontsize=7)
    ax2.set_title("(b) EV: strategy vs. baseline", fontsize=7, pad=3)
    ax2.set_xlim(-1.1, 1.1)
    ax2.grid(axis="x", color="#F0F0F0", lw=0.3)

    # Panel (c): ENI
    enis_s = [paper_metrics(d)["eni"] for _, d, _ in sd]
    enis_b = [paper_metrics(bl)["eni"] for _, _, bl in sd]
    for i, (c, d, bl) in enumerate(sd):
        yi = y[i]
        ax3.plot([enis_b[i], enis_s[i]], [yi, yi], color="#CCCCCC", lw=2.8, solid_capstyle="round", zorder=1)
        ax3.scatter(enis_b[i], yi, s=24, color="#999999", zorder=3, edgecolor="white", lw=0.3)
        ax3.scatter(enis_s[i], yi, s=32, color=c.color, zorder=4, edgecolor="white", lw=0.3)
    ax3.set_yticks(y); ax3.set_yticklabels([])
    ax3.set_xlabel("ENI (%)", fontsize=7)
    ax3.set_title("(c) ENI: strategy vs. baseline", fontsize=7, pad=3)
    ax3.set_xlim(0, 105)
    ax3.grid(axis="x", color="#F0F0F0", lw=0.3)

    fig.subplots_adjust(left=0.17, right=0.98, top=0.90, bottom=0.15)
    save(fig, "fig_study2_v3_APPENDIX_opt1_paired")


# ═══════════════════════════════════════════════════════════════════
# APPENDIX OPTION 2: Top-4 trajectory + emotion 2×2×2
# Compact: 2 rows, each row = trajectory left, emotion right
# ═══════════════════════════════════════════════════════════════════
def fig_appendix_opt2(sd):
    """Top-4 conditions: trajectory + emotion dynamics side by side."""
    W = 6.75
    top4 = sd[:4]
    fig = plt.figure(figsize=(W, 4.8))
    gs = gridspec.GridSpec(2, 4, figure=fig, hspace=0.36, wspace=0.10,
        left=0.065, right=0.985, top=0.94, bottom=0.09)

    for i, (c, d, bl) in enumerate(top4):
        row, col_base = i // 2, (i % 2) * 2

        # Trajectory panel
        ax_t = fig.add_subplot(gs[row, col_base])
        rounds, mat, _ = stance_mat(d["res"])
        m, lo, hi = traj_stats(mat)
        _, bmat, _ = stance_mat(bl["res"])
        bm, _, _ = traj_stats(bmat)

        ax_t.fill_between(rounds, lo, hi, color=c.color, alpha=0.12, lw=0)
        ax_t.plot(rounds, m, color=c.color, lw=1.5)
        ax_t.plot(rounds, bm, color="#888", lw=1.0, ls="--")
        ax_t.axhline(0, color="#C0C0C0", lw=0.4, ls=":")
        ax_t.set_xlim(-0.2, 15.2); ax_t.set_ylim(-3.5, 3.5)
        ax_t.set_xticks([0, 5, 10, 15]); ax_t.set_yticks([-3, -1, 1, 3])
        ax_t.grid(axis="y", color="#F0F0F0", lw=0.25)
        if row == 1: ax_t.set_xlabel("Round")
        else: ax_t.tick_params(labelbottom=False)
        if col_base == 0: ax_t.set_ylabel("Mean stance")
        else: ax_t.tick_params(labelleft=False)
        pm = paper_metrics(d)
        ax_t.text(0.03, 0.96, f"({chr(97 + i*2)}) {c.strategy}\n{c.population}",
                  transform=ax_t.transAxes, va="top", fontweight="bold", fontsize=6)
        ax_t.text(0.97, 0.05,
                  f"$\\Delta\\bar{{s}}$={pm['delta_s']:+.2f}\nNSR={pm['nsr']:.1f}%",
                  transform=ax_t.transAxes, ha="right", va="bottom", fontsize=5,
                  bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#D8D8D8", lw=0.3, alpha=0.92))

        # Emotion panel
        ax_e = fig.add_subplot(gs[row, col_base + 1])
        neg = np.concatenate([[0], neg_per_round(d["emo"])])
        bl_neg = np.concatenate([[0], neg_per_round(bl["emo"])])
        rnds = np.arange(16)
        ax_e.fill_between(rnds, neg, color=c.color, alpha=0.15, lw=0)
        ax_e.plot(rnds, neg, color=c.color, lw=1.3)
        ax_e.plot(rnds, bl_neg, color="#888", lw=0.9, ls="--")
        ax_e.set_xlim(-0.2, 15.2); ax_e.set_ylim(0, 0.65)
        ax_e.set_xticks([0, 5, 10, 15])
        ax_e.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
        ax_e.grid(axis="y", color="#F0F0F0", lw=0.25)
        if row == 1: ax_e.set_xlabel("Round")
        else: ax_e.tick_params(labelbottom=False)
        ax_e.tick_params(labelleft=True)
        ax_e.set_ylabel("Neg. share", labelpad=1)
        ax_e.text(0.03, 0.96, f"({chr(97 + i*2 + 1)})",
                  transform=ax_e.transAxes, va="top", fontweight="bold", fontsize=6)
        ax_e.text(0.97, 0.88, f"ENI={pm['eni']:.1f}%",
                  transform=ax_e.transAxes, ha="right", fontsize=5.5, color=c.color)

    h_t = [Line2D([], [], color="#333", lw=1.4, label="Strategy mean \u00b1 CI"),
           Line2D([], [], color="#888", lw=1.0, ls="--", label="Baseline")]
    fig.legend(handles=h_t, loc="upper center", bbox_to_anchor=(0.5, 0.99),
               ncol=2, frameon=False, handlelength=2.0, columnspacing=1.2)
    save(fig, "fig_study2_v3_APPENDIX_opt2_traj_emo")


# ═══════════════════════════════════════════════════════════════════
# APPENDIX OPTION 3: Flow diagram (initial→final) for all 8 conditions
# Each panel shows individual agent flows, clear evidence of stance shifts
# ═══════════════════════════════════════════════════════════════════
def fig_appendix_opt3(sd):
    """Full 4×2 flow diagrams: initial→final stance for every agent."""
    W = 6.75
    n = len(sd); nrows, ncols = 4, 2
    fig = plt.figure(figsize=(W, 7.2))
    gs = gridspec.GridSpec(nrows, ncols, figure=fig, hspace=0.28, wspace=0.10,
        left=0.065, right=0.985, top=0.965, bottom=0.035)
    rng = np.random.default_rng(42)

    for i, (c, d, bl) in enumerate(sd):
        ax = fig.add_subplot(gs[i // ncols, i % ncols])
        _, mat, _ = stance_mat(d["res"])
        init, final = mat[:, 0], mat[:, -1]
        x0 = rng.normal(0, 0.015, len(init))
        x1 = rng.normal(1, 0.015, len(final))
        for y0, y1, j0, j1 in zip(init, final, x0, x1):
            if y1 < y0 - 0.5:
                col, a, lw, z = "#B4162E", 0.40, 0.6, 3
            elif y1 > y0 + 0.5:
                col, a, lw, z = "#0072B2", 0.35, 0.5, 3
            else:
                col, a, lw, z = "#8A8A8A", 0.15, 0.4, 1
            ax.plot([j0, j1], [y0, y1], color=col, alpha=a, lw=lw, zorder=z)
        ax.scatter(x0, init, s=6, color="#2F2F2F", alpha=0.30, lw=0, zorder=4)
        ax.scatter(x1, final, s=7, color=c.color, alpha=0.60, lw=0, zorder=5)
        ax.plot([0, 1], [np.mean(init), np.mean(final)], color="black", lw=1.8, zorder=6)
        ax.axhline(0, color="#C0C0C0", lw=0.4, ls=":")
        ax.set_xlim(-0.15, 1.15); ax.set_ylim(SMIN - 0.3, SMAX + 0.3)
        ax.set_xticks([0, 1]); ax.set_xticklabels(["Initial", "Final"])
        ax.set_yticks([-5, -3, -1, 1, 3, 5])
        if i % ncols == 0: ax.set_ylabel("Stance")
        else: ax.tick_params(labelleft=False)
        pm = paper_metrics(d)
        ax.text(0.03, 0.96, f"({chr(97+i)}) {c.strategy}\n{c.population}",
                transform=ax.transAxes, va="top", fontweight="bold", fontsize=6.5)
        ax.text(0.97, 0.04,
                f"$\\Delta\\bar{{s}}$={pm['delta_s']:+.2f}  NSR={pm['nsr']:.1f}%",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=5.2,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="#D8D8D8", lw=0.3, alpha=0.92))

    h = [Line2D([], [], color="#B4162E", lw=0.9, alpha=0.6, label="Stance decreased"),
         Line2D([], [], color="#0072B2", lw=0.9, alpha=0.6, label="Stance increased"),
         Line2D([], [], color="black", lw=1.8, label="Group mean")]
    fig.legend(handles=h, loc="upper center", bbox_to_anchor=(0.525, 0.996),
               ncol=3, frameon=False, handlelength=1.8, columnspacing=1.0, fontsize=6)
    save(fig, "fig_study2_v3_APPENDIX_opt3_flow")


# ═══════════════════════════════════════════════════════════════════
# APPENDIX OPTION 4: Composition area (stacked) for all 8 conditions
# ═══════════════════════════════════════════════════════════════════
def fig_appendix_opt4(sd):
    """Full 4×2 stacked area: stance composition over rounds."""
    W = 6.75
    n = len(sd); nrows, ncols = 4, 2
    fig = plt.figure(figsize=(W, 7.2))
    gs = gridspec.GridSpec(nrows, ncols, figure=fig, hspace=0.28, wspace=0.10,
        left=0.065, right=0.985, top=0.955, bottom=0.055)

    bands = [
        ("Strong anti (\u22643)", lambda v: v <= -3, "#8C1D18"),
        ("Mild anti (\u22122~\u22121)", lambda v: (v >= -2) & (v <= -1), "#E69F00"),
        ("Neutral (0)", lambda v: v == 0, "#D9D9D9"),
        ("Mild pro (+1~+2)", lambda v: (v >= 1) & (v <= 2), "#56B4E9"),
        ("Strong pro (\u22653)", lambda v: v >= 3, "#0072B2"),
    ]

    for i, (c, d, bl) in enumerate(sd):
        ax = fig.add_subplot(gs[i // ncols, i % ncols])
        rounds, mat, _ = stance_mat(d["res"])
        shares = np.vstack([np.mean(fn(mat), axis=0) for _, fn, _ in bands])
        ax.stackplot(rounds, shares, colors=[co for _, _, co in bands], alpha=0.90, lw=0)
        ax.set_xlim(0, 15); ax.set_ylim(0, 1)
        ax.set_xticks([0, 5, 10, 15])
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
        ax.grid(axis="y", color="white", lw=0.35, alpha=0.6)
        if i >= n - 2: ax.set_xlabel("Round")
        if i % ncols == 0: ax.set_ylabel("Agent share")
        else: ax.tick_params(labelleft=False)
        if i < n - 2: ax.tick_params(labelbottom=False)
        pm = paper_metrics(d)
        ax.text(0.025, 0.96, f"({chr(97+i)}) {c.strategy}\n{c.population}",
                transform=ax.transAxes, va="top", fontweight="bold", fontsize=6.3,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.75))

    handles = [mpatches.Patch(color=co, label=lb) for lb, _, co in bands]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.525, 0.005),
               ncol=5, frameon=False, handlelength=1.2, columnspacing=0.8, fontsize=5.8)
    save(fig, "fig_study2_v3_APPENDIX_opt4_composition")


# ═══════════════════════════════════════════════════════════════════
# APPENDIX OPTION 5: Grouped bar chart — strategy vs baseline for
# Δs̄ and ENI side by side, compact and publication-ready
# ═══════════════════════════════════════════════════════════════════
def fig_appendix_opt5(sd):
    """Grouped bars: strategy vs baseline for Δs̄ and ENI."""
    W = 6.75
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(W, 3.0),
        gridspec_kw={"wspace": 0.30})

    n = len(sd)
    x = np.arange(n)
    bw = 0.36
    labels = [f"{c.strategy}\n{c.population}" for c, _, _ in sd]
    colors = [c.color for c, _, _ in sd]

    # (a) Δs̄ grouped bar
    sv = [d["sum"]["mean_shift"] for _, d, _ in sd]
    bv = [bl["sum"]["mean_shift"] for _, _, bl in sd]
    bars_b = ax1.bar(x - bw/2, bv, bw, color="#CCCCCC", edgecolor="white", lw=0.3, label="Baseline")
    bars_s = ax1.bar(x + bw/2, sv, bw, color=colors, edgecolor="white", lw=0.3, label="Strategy")
    ax1.set_xticks(x); ax1.set_xticklabels(labels, fontsize=5.2, rotation=30, ha="right")
    ax1.set_ylabel(r"$\Delta\bar{s}$")
    ax1.set_title(r"(a) Mean stance shift ($\Delta\bar{s}$)", fontsize=7.5, pad=3)
    ax1.axhline(0, color="#AAAAAA", lw=0.4)
    ax1.grid(axis="y", color="#F0F0F0", lw=0.3)
    ax1.legend(handles=[
        mpatches.Patch(color="#CCCCCC", label="Baseline"),
        mpatches.Patch(color="#888888", label="Strategy"),
    ], loc="upper right", frameon=False, fontsize=5.5)

    # (b) ENI grouped bar
    eni_s = [paper_metrics(d)["eni"] for _, d, _ in sd]
    eni_b = [paper_metrics(bl)["eni"] for _, _, bl in sd]
    ax2.bar(x - bw/2, eni_b, bw, color="#CCCCCC", edgecolor="white", lw=0.3)
    ax2.bar(x + bw/2, eni_s, bw, color=colors, edgecolor="white", lw=0.3)
    ax2.set_xticks(x); ax2.set_xticklabels(labels, fontsize=5.2, rotation=30, ha="right")
    ax2.set_ylabel("ENI (%)")
    ax2.set_title("(b) Emotional negativity index (ENI)", fontsize=7.5, pad=3)
    ax2.grid(axis="y", color="#F0F0F0", lw=0.3)

    fig.subplots_adjust(left=0.065, right=0.98, top=0.90, bottom=0.28)
    save(fig, "fig_study2_v3_APPENDIX_opt5_grouped")


# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    sd = sorted_data()
    print("=== Generating final EMNLP-polished figures ===")
    print("  Conditions ranked by delta-s:")
    for i, (c, d, bl) in enumerate(sd):
        pm = paper_metrics(d)
        pm_bl = paper_metrics(bl)
        print(f"    {i+1}. {c.strategy:20s} x {c.population:16s}  "
              f"ds={pm['delta_s']:+.2f} (bl {pm_bl['delta_s']:+.2f})  "
              f"NSR={pm['nsr']:.1f}%  EV={pm['ev']:+.2f}  ENI={pm['eni']:.1f}%")
    print()
    fig_main(sd)
    fig_appendix_opt1(sd)
    fig_appendix_opt2(sd)
    fig_appendix_opt3(sd)
    fig_appendix_opt4(sd)
    fig_appendix_opt5(sd)
    print("=== Done ===")
