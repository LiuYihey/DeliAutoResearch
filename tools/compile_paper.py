#!/usr/bin/env python3
"""Compile LaTeX paper (pdflatex + bibtex)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def compile_paper(paper_dir: Path) -> bool:
    main = paper_dir / "main.tex"
    if not main.exists():
        print(f"Missing {main}")
        return False
    if not shutil.which("pdflatex"):
        print("pdflatex not found in PATH — install TeX Live or MiKTeX")
        return False

    cwd = paper_dir
    for _ in range(2):
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "main.tex"],
            cwd=cwd, check=False, capture_output=True, text=True,
        )
    if (paper_dir / "references.bib").exists() and shutil.which("bibtex"):
        subprocess.run(["bibtex", "main"], cwd=cwd, check=False, capture_output=True, text=True)
        for _ in range(2):
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "main.tex"],
                cwd=cwd, check=False, capture_output=True, text=True,
            )

    pdf = paper_dir / "main.pdf"
    if pdf.exists():
        print(f"OK: {pdf}")
        return True
    print("Compilation failed — check main.log")
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_dir", type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if compile_paper(args.paper_dir) else 1)


if __name__ == "__main__":
    main()
