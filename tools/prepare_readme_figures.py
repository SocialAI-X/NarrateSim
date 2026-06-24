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

# README uses only these two figures
PDF_SOURCES = {
    "framework": ROOT / "latex_paper/figures/framework.pdf",
}

PNG_SOURCES = {
    "study1_trajectories": ROOT / "paper_figures/fig1_main_trajectories.png",
}


def pdf_to_png(src: Path, dest: Path, scale: float = 2.0):
    doc = fitz.open(src)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale))
    pix.save(dest)


def main():
    # Remove stale figures not used in README
    keep = {"README.md", "framework.png", "framework.pdf", "study1_trajectories.png", "study1_trajectories.pdf"}
    for f in FIG.iterdir():
        if f.is_file() and f.name not in keep:
            f.unlink()
            print(f"removed {f.name}")

    for name, src in PDF_SOURCES.items():
        if not src.exists():
            print(f"SKIP missing {src}")
            continue
        pdf_to_png(src, FIG / f"{name}.png")
        shutil.copy2(src, FIG / f"{name}.pdf")
        print(f"updated {name}.png / .pdf")

    traj_pdf = ROOT / "latex_paper/figures/fig_study1_trajectories.pdf"
    if traj_pdf.exists():
        shutil.copy2(traj_pdf, FIG / "study1_trajectories.pdf")

    for name, src in PNG_SOURCES.items():
        if not src.exists():
            print(f"SKIP missing {src}")
            continue
        dest = FIG / f"{name}.png"
        shutil.copy2(src, dest)
        print(f"updated {dest.name}")


if __name__ == "__main__":
    main()
