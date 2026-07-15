#!/usr/bin/env python3
"""Run quality gates on a paper-writing task (anti-hallucination v2).

Gate list (with mandatory anti-hallucination gates added):
- Gate 1: literature — citation count, arXiv ratio
- Gate 1.5: retrieval_provenance — all bib entries must have retrieval_log anchors (new, anti-hallucination core)
- Gate 1.6: numerical_claims — section numerical claims must be anchored to original text (new)
- Gate 2: experiment
- Gate 3: structure
- Gate 4: figures_tables
- Gate 5: final_review
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Allow importing same-directory modules from tools/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_log import read_log, has_provenance  # noqa: E402


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


def gate_retrieval_provenance(task_dir: Path) -> dict:
    """Gate 1.5 — All bib entries must have a retrieval_log anchor (anti-hallucination core).

    Entries without anchors = LLM filled from memory = potential hallucination.
    Threshold: 0 orphans (strict).
    """
    bib_path = task_dir / "paper" / "references.bib"
    if not bib_path.exists():
        return {"gate": 1.5, "name": "retrieval_provenance", "passed": False,
                "checks": {"bib_exists": False}, "orphans": []}
    text = bib_path.read_text(encoding="utf-8", errors="ignore")
    # Parse each entry's doi / title
    entries = []
    for m in re.finditer(r"@\w+\s*\{([^,]+),\s*(.*?)\n\}", text, re.DOTALL):
        key = m.group(1).strip()
        body = m.group(2)
        doi_m = re.search(r'doi\s*=\s*[\{"]?(10\.\S+?)[\}"]?\s*[,\n]', body, re.IGNORECASE)
        title_m = re.search(r'title\s*=\s*[\{"]?(.+?)[\}"]?\s*[,\n]', body, re.IGNORECASE | re.DOTALL)
        entries.append({
            "key": key,
            "doi": doi_m.group(1).strip().rstrip(".") if doi_m else "",
            "title": title_m.group(1).strip().strip("{}") if title_m else "",
        })
    orphans = []
    for e in entries:
        if not (e["doi"] or e["title"]):
            orphans.append({"key": e["key"], "reason": "no_doi_no_title"})
            continue
        ok = has_provenance(task_dir, doi=e["doi"] or None, title=e["title"] or None)
        if not ok:
            orphans.append({"key": e["key"], "doi": e["doi"], "title": e["title"][:60],
                            "reason": "no_retrieval_log_anchor"})
    log_stats = read_log(task_dir)
    checks = {
        "bib_exists": True,
        "retrieval_log_exists": len(log_stats) > 0,
        "zero_orphans": len(orphans) == 0,
    }
    return {"gate": 1.5, "name": "retrieval_provenance", "passed": all(checks.values()),
            "metrics": {"total_bib": len(entries), "orphans": len(orphans),
                        "retrieval_log_entries": len(log_stats)},
            "checks": checks, "orphans": orphans[:50]}


def gate_numerical_claims(task_dir: Path) -> dict:
    """Gate 1.6 — Section numerical claims must be anchored to the original text in retrieval_log.

    Calls check_numerical_claims.py internal functions to avoid subprocess overhead.
    """
    try:
        from check_numerical_claims import scan_sections, anchor_claim
    except ImportError:
        return {"gate": 1.6, "name": "numerical_claims", "passed": False,
                "checks": {"tool_available": False}, "unanchored": []}
    sections_dir = task_dir / "paper" / "sections"
    if not sections_dir.exists():
        return {"gate": 1.6, "name": "numerical_claims", "passed": True,
                "metrics": {"total_claims": 0, "unanchored": 0},
                "checks": {"sections_exist": False}, "unanchored": []}
    claims = scan_sections(sections_dir)
    anchored = [anchor_claim(c, task_dir) for c in claims]
    unanchored = [c for c in anchored if not c["anchored"]]
    checks = {
        "sections_exist": True,
        "all_anchored": len(unanchored) == 0,
    }
    return {"gate": 1.6, "name": "numerical_claims",
            "passed": all(checks.values()) or len(claims) == 0,
            "metrics": {"total_claims": len(claims), "unanchored": len(unanchored)},
            "checks": checks, "unanchored": unanchored[:30]}


def gate_factual_claims(task_dir: Path) -> dict:
    """Gate 1.7 — Section factual claims must be anchored to full text (anti-hallucination v3 — solid)."""
    try:
        from check_factual_claims import scan_sections, anchor_factual_claim
    except ImportError:
        return {"gate": 1.7, "name": "factual_claims", "passed": False,
                "checks": {"tool_available": False}, "unanchored": []}
    sections_dir = task_dir / "paper" / "sections"
    if not sections_dir.exists():
        return {"gate": 1.7, "name": "factual_claims", "passed": True,
                "metrics": {"total_claims": 0}, "checks": {"sections_exist": False},
                "unanchored": []}
    claims = scan_sections(sections_dir)
    anchored = [anchor_factual_claim(c, task_dir) for c in claims]
    unanchored = [c for c in anchored if c.get("match_strength") in ("loose", "none")]
    checks = {
        "sections_exist": True,
        "all_claims_grounded": len(unanchored) == 0,
    }
    return {"gate": 1.7, "name": "factual_claims",
            "passed": all(checks.values()) or len(claims) == 0,
            "metrics": {"total_claims": len(claims), "unanchored": len(unanchored)},
            "checks": checks, "unanchored": unanchored[:30]}


def gate_conclusion_grounding(task_dir: Path) -> dict:
    """Gate 1.8 — Conclusion claims must be based on experimental data or cited papers' real results (anti-hallucination v3 — solid)."""
    try:
        from verify_conclusions import extract_claims_from_conclusion, anchor_conclusion_claim, load_raw_results
    except ImportError:
        return {"gate": 1.8, "name": "conclusion_grounding", "passed": False,
                "checks": {"tool_available": False}, "unanchored": []}
    sections_dir = task_dir / "paper" / "sections"
    conclusion_files = [f for f in sections_dir.glob("*.tex")
                        if "conclusion" in f.name.lower() or "06" in f.name or "07" in f.name]
    if not conclusion_files:
        return {"gate": 1.8, "name": "conclusion_grounding", "passed": True,
                "checks": {"conclusion_section_exists": False}, "unanchored": []}
    raw_results = load_raw_results(task_dir)
    all_claims = []
    for f in conclusion_files:
        all_claims.extend(extract_claims_from_conclusion(f))
    anchored = [anchor_conclusion_claim(c, task_dir, raw_results) for c in all_claims]
    unanchored = [c for c in anchored if not c["anchored"]]
    checks = {
        "conclusion_section_exists": True,
        "all_claims_grounded": len(unanchored) == 0,
        "has_raw_results": len(raw_results) > 0,
    }
    return {"gate": 1.8, "name": "conclusion_grounding",
            "passed": all(checks.values()) or len(all_claims) == 0,
            "metrics": {"total_claims": len(all_claims), "unanchored": len(unanchored),
                        "raw_results_count": len(raw_results)},
            "checks": checks, "unanchored": unanchored[:30]}


def gate_metadata_cross_validated(task_dir: Path) -> dict:
    """Gate 1.9 — Bib metadata must be consistent across CrossRef/DBLP/S2 (anti-hallucination v3 — solid)."""
    try:
        from cross_validate_metadata import cross_validate_entry
        from verify_citations import parse_bib
    except ImportError:
        return {"gate": 1.9, "name": "metadata_cross_validated", "passed": False,
                "checks": {"tool_available": False}, "diffs": []}
    bib = task_dir / "paper" / "references.bib"
    if not bib.exists():
        return {"gate": 1.9, "name": "metadata_cross_validated", "passed": False,
                "checks": {"bib_exists": False}, "diffs": []}
    # Gate only checks the first N entries to avoid blocking on many API calls
    entries = parse_bib(bib)[:20]
    fails = []
    warns = []
    for e in entries:
        r = cross_validate_entry(e, task_dir)
        if r["verdict"] == "FAIL":
            fails.append(r)
        elif r["verdict"] == "WARN":
            warns.append(r)
    checks = {
        "bib_exists": True,
        "no_fail": len(fails) == 0,
    }
    return {"gate": 1.9, "name": "metadata_cross_validated",
            "passed": all(checks.values()),
            "metrics": {"checked": len(entries), "fails": len(fails), "warns": len(warns)},
            "checks": checks, "fails": fails[:10], "warns": warns[:10]}


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
        gate_retrieval_provenance(task_dir),    # anti-hallucination v2: anchor check
        gate_numerical_claims(task_dir),        # anti-hallucination v2: numerical claim anchoring
        gate_factual_claims(task_dir),          # anti-hallucination v3: factual claims anchored to full text
        gate_conclusion_grounding(task_dir),    # anti-hallucination v3: conclusion must be based on experimental data
        gate_metadata_cross_validated(task_dir),  # anti-hallucination v3: three-way metadata cross-validation
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
