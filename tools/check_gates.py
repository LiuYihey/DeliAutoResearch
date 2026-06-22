#!/usr/bin/env python3
"""Run quality gates on a paper-writing task."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def count_bib_entries(bib_path: Path) -> int:
    if not bib_path.exists():
        return 0
    return len(re.findall(r"@\w+\s*\{", bib_path.read_text(encoding="utf-8", errors="ignore")))


def count_arxiv_only(bib_path: Path) -> tuple[int, int]:
    if not bib_path.exists():
        return 0, 0
    text = bib_path.read_text(encoding="utf-8", errors="ignore")
    entries = re.split(r"(?=@\w+\s*\{)", text)
    total = 0
    arxiv_only = 0
    for e in entries:
        if not e.strip():
            continue
        total += 1
        if "journal" not in e.lower() and "booktitle" not in e.lower():
            if "arxiv" in e.lower() or "eprint" in e.lower():
                arxiv_only += 1
    return arxiv_only, total


def gate_literature(paper_dir: Path, pages: int = 50) -> dict:
    bib = paper_dir / "references.bib"
    plan = paper_dir / "citation_plan.jsonl"
    n_cites = count_bib_entries(bib)
    arxiv_only, total = count_arxiv_only(bib)
    arxiv_ratio = arxiv_only / total if total else 1.0
    plan_lines = len(plan.read_text(encoding="utf-8").splitlines()) if plan.exists() else 0
    checks = {
        "citations_min_draft": n_cites >= 80,
        "citations_min_final": n_cites >= pages * 3,
        "arxiv_only_ratio": arxiv_ratio <= 0.60,
        "citation_plan_exists": plan_lines > 0,
    }
    return {"gate": 1, "name": "literature", "passed": all(checks.values()), "metrics": {
        "citations": n_cites, "arxiv_only_ratio": round(arxiv_ratio, 3), "plan_entries": plan_lines
    }, "checks": checks}


def gate_experiment(paper_dir: Path) -> dict:
    results = paper_dir / "results.json"
    summary = paper_dir / "experiment_summary.md"
    spec = paper_dir / "experiment_spec.json"
    data = {}
    if results.exists():
        data = json.loads(results.read_text(encoding="utf-8"))
    checks = {
        "results_exist": results.exists(),
        "summary_exist": summary.exists(),
        "hypothesis_preregistered": spec.exists(),
        "has_trials": data.get("trials", 0) >= 3 if data else False,
    }
    return {"gate": 2, "name": "experiment", "passed": all(checks.values()), "checks": checks}


def gate_structure(paper_dir: Path) -> dict:
    sections = list((paper_dir / "sections").glob("*.tex")) if (paper_dir / "sections").exists() else []
    long_files = [s.name for s in sections if len(s.read_text(encoding="utf-8").splitlines()) > 300]
    main = paper_dir / "main.tex"
    checks = {
        "main_tex_exists": main.exists(),
        "sections_count": len(sections) >= 3,
        "no_long_sections": len(long_files) == 0,
    }
    return {"gate": 3, "name": "structure", "passed": all(checks.values()), "checks": checks,
            "long_files": long_files}


def gate_figures(paper_dir: Path, full_survey: bool = True) -> dict:
    tables = list(paper_dir.glob("tables/*.tex")) if (paper_dir / "tables").exists() else []
    figures = list(paper_dir.glob("figures/*")) if (paper_dir / "figures").exists() else []
    min_tables, min_figs = (10, 6) if full_survey else (5, 3)
    checks = {
        "tables_enough": len(tables) >= min_tables,
        "figures_enough": len(figures) >= min_figs,
    }
    return {"gate": 4, "name": "figures_tables", "passed": all(checks.values()),
            "metrics": {"tables": len(tables), "figures": len(figures)}, "checks": checks}


def gate_review(task_dir: Path) -> dict:
    progress_path = task_dir / "state" / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
    phase = int(progress.get("phase", 0))
    targets = {0: 0.0, 1: 6.0, 2: 7.5, 3: 8.5}
    target = float(progress.get("target_score", targets.get(phase, 8.0)))
    score = float(progress.get("current_score", 0.0))
    pdf = task_dir / "paper" / "main.pdf"
    checks = {"pdf_exists": pdf.exists(), "score_meets_target": score >= target}
    return {"gate": 5, "name": "final_review", "passed": all(checks.values()),
            "metrics": {"current_score": score, "target_score": target}, "checks": checks}


def run_all(task_dir: Path) -> dict:
    paper_dir = task_dir / "paper"
    gates = [
        gate_literature(paper_dir),
        gate_experiment(paper_dir),
        gate_structure(paper_dir),
        gate_figures(paper_dir),
        gate_review(task_dir),
    ]
    return {
        "task_dir": str(task_dir),
        "all_passed": all(g["passed"] for g in gates),
        "gates": gates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    report = run_all(args.task_dir)
    out = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    print(out)
    raise SystemExit(0 if report["all_passed"] else 1)


if __name__ == "__main__":
    main()
