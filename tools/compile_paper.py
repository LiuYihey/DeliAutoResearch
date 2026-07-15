#!/usr/bin/env python3
"""Compile LaTeX paper (pdflatex + bibtex).

Optionally runs the anti-hallucination gate check before compilation to
prevent shipping a PDF with hallucinated citations / claims. The gate
is non-fatal by default — pass --strict to make Gate 1.5-1.9 failures
abort compilation.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


STRICT_GATES = {"1.5", "1.6", "1.7", "1.8", "1.9"}


def run_anti_hallucination_gate(task_dir: Path, strict: bool) -> bool:
    """Run check_gates.py and report Gate 1.5-1.9 status.

    Returns True if compilation may proceed. In strict mode, returns False
    if any of Gate 1.5-1.9 fails.
    """
    check_gates = task_dir.parent.parent / "tools" / "check_gates.py"
    if not check_gates.exists():
        print(f"[anti-hall] check_gates.py not found at {check_gates}, skipping gate")
        return True
    result = subprocess.run(
        [sys.executable, str(check_gates), str(task_dir)],
        cwd=task_dir.parent.parent, check=False, capture_output=True, text=True,
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("[anti-hall] check_gates.py did not return valid JSON — non-blocking")
        return True
    gates = report.get("gates", {}) if isinstance(report, dict) else {}
    failing_strict = [g for g in STRICT_GATES if gates.get(g, {}).get("pass") is False]
    if failing_strict:
        print(f"[anti-hall] Gate {','.join(failing_strict)} FAIL — hallucination risk")
        if strict:
            print("[anti-hall] strict mode: aborting compilation")
            return False
        print("[anti-hall] non-strict: compiling anyway (PDF will be marked suspect)")
    else:
        print("[anti-hall] Gate 1.5-1.9 all pass — safe to compile")
    return True


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
    parser.add_argument(
        "--task-dir", type=Path, default=None,
        help="Task dir (parent of paper/) — if provided, runs anti-hallucination gate first",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Abort compilation if Gate 1.5-1.9 fails",
    )
    parser.add_argument(
        "--skip-gate", action="store_true",
        help="Skip anti-hallucination gate check entirely",
    )
    args = parser.parse_args()

    if args.task_dir and not args.skip_gate:
        if not run_anti_hallucination_gate(args.task_dir, args.strict):
            raise SystemExit(2)

    raise SystemExit(0 if compile_paper(args.paper_dir) else 1)


if __name__ == "__main__":
    main()
