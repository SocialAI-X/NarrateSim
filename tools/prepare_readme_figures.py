"""Prepare curated figures/ for README embedding."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

PDF_SOURCES = {
    "framework": ROOT / "latex_paper/figures/framework.pdf",
    "motivation": ROOT / "latex_paper/figures/fig_motivation.pdf",
    "micro_case": ROOT / "latex_paper/figures/fig_micro_case.pdf",
    "study2_trait_response": ROOT / "latex_paper/figures/fig_trait_response.pdf",
}

PNG_SOURCES = {
    "study1_trajectories": ROOT / "paper_figures/fig1_main_trajectories.png",
    "study2_ranking": ROOT / "paper_figures/fig_study2_v3_MAIN_ranking.png",
    "intervention": ROOT / "paper_figures/fig3_intervention.png",
    "network_topology": ROOT / "paper_figures/fig_network_evolution.png",
    "scale5k_evolution": ROOT / "paper_figures/fig_scale5000_network_evolution.png",
}


def pdf_to_png(src: Path, dest: Path, scale: float = 2.0):
    doc = fitz.open(src)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale))
    pix.save(dest)


def main():
    for name, src in PDF_SOURCES.items():
        if not src.exists():
            print(f"SKIP missing {src}")
            continue
        dest = FIG / f"{name}.png"
        pdf_to_png(src, dest)
        print(f"converted {dest.name} ({dest.stat().st_size // 1024} KB)")

    for name, src in PNG_SOURCES.items():
        if not src.exists():
            print(f"SKIP missing {src}")
            continue
        dest = FIG / f"{name}.png"
        shutil.copy2(src, dest)
        print(f"copied {dest.name} ({dest.stat().st_size // 1024} KB)")

    # PDF copies for high-quality download (selected main figures)
    pdf_keep = {
        "framework": ROOT / "latex_paper/figures/framework.pdf",
        "study1_trajectories": ROOT / "latex_paper/figures/fig_study1_trajectories.pdf",
        "study2_ranking": ROOT / "latex_paper/figures/fig_study2_ranking.pdf",
    }
    for name, src in pdf_keep.items():
        if src.exists():
            dest = FIG / f"{name}.pdf"
            shutil.copy2(src, dest)
            print(f"copied {dest.name}")


if __name__ == "__main__":
    main()
