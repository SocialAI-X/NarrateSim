"""Copy the paper figures into figures/ (PDF + PNG) for the README.

    python tools/prepare_readme_figures.py

Needs PyMuPDF (`pip install pymupdf`) and the local paper source folder.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "latex_paper_WWW2027" / "figures"
FIG = ROOT / "figures"

# figures/<name>.{pdf,png}  <-  paper figure
SOURCES = {
    "motivation": "fig_motivation.pdf",
    "framework": "framework.pdf",
    "attack_trajectories": "fig_attack_trajectories_col.pdf",
    "network_topology": "fig_network_topology.pdf",
    "micro_case": "fig_micro_case.pdf",
}


def pdf_to_png(src: Path, dest: Path, width: int = 1800) -> None:
    page = fitz.open(src)[0]
    scale = width / page.rect.width
    page.get_pixmap(matrix=fitz.Matrix(scale, scale)).save(dest)


def main() -> None:
    FIG.mkdir(exist_ok=True)
    keep = {"README.md"} | {f"{n}.{ext}" for n in SOURCES for ext in ("pdf", "png")}
    for f in FIG.iterdir():
        if f.is_file() and f.name not in keep:
            f.unlink()
            print(f"removed {f.name}")
    for name, pdf in SOURCES.items():
        src = SRC / pdf
        if not src.exists():
            print(f"SKIP missing {src}")
            continue
        shutil.copy2(src, FIG / f"{name}.pdf")
        pdf_to_png(src, FIG / f"{name}.png")
        print(f"updated {name}.pdf / .png")


if __name__ == "__main__":
    main()
