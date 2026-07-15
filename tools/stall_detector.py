#!/usr/bin/env python3
"""Detect stalls and recommend orchestrator actions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from log_util import read_json, read_jsonl
from retrieval_log import has_provenance  # consistent with check_gates.py Gate 1.5


def parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def hours_since(ts: str | None) -> float | None:
    dt = parse_ts(ts)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0


def count_findings(findings_path: Path) -> int:
    return len(read_jsonl(findings_path))


def detect_anti_hallucination_gaps(task_dir: Path) -> dict[str, Any]:
    """Detect A/B-level citations whose fulltext is missing, and orphan bib entries.

    Returns counts that feed into stall_detector recommendations:
    - fulltext_missing: # A/B cite_keys with no paper/fulltext/<cite_key>.txt
    - retrieval_log_orphans: # references.bib entries without retrieval_log provenance
    - raw_results_missing: True if experiment_design phase but no raw_results.jsonl lines
    - gates_failing (from progress.anti_hallucination.gates_failing if recorded)
    """
    paper_dir = task_dir / "paper"
    fulltext_dir = paper_dir / "fulltext"
    retrieval_log = paper_dir / "retrieval_log.jsonl"
    bib_path = paper_dir / "references.bib"
    plan_path = paper_dir / "citation_plan.jsonl"
    raw_results_path = paper_dir / "raw_results.jsonl"

    # A/B-level citations from citation_plan.jsonl
    ab_cites: set[str] = set()
    if plan_path.exists():
        for line in plan_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            level = str(entry.get("level", entry.get("depth", entry.get("priority", "")))).upper()
            if level in {"A", "B"}:
                ck = entry.get("cite_key", entry.get("key", "")).strip()
                if ck:
                    ab_cites.add(ck)

    fulltext_missing: list[str] = []
    if ab_cites:
        for ck in ab_cites:
            if not (fulltext_dir / f"{ck}.txt").exists():
                fulltext_missing.append(ck)

    # Orphan bib entries (in references.bib but no retrieval_log provenance)
    # Uses has_provenance() (DOI/title matching) — consistent with Gate 1.5 (check_gates.py).
    # Previous cite_key-based set-difference was a false-positive source: retrieval_log
    # entries key by source_id (doi:.../arxiv:...) not by bib cite_key.
    orphan_count = 0
    bib_count = 0
    if bib_path.exists():
        import re
        bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"@\w+\s*\{([^,]+),\s*(.*?)\n\}", bib_text, re.DOTALL):
            bib_count += 1
            body = m.group(2)
            doi_m = re.search(r'doi\s*=\s*[\{"]?(10\.\S+?)[\}"]?\s*[,\n]', body, re.IGNORECASE)
            title_m = re.search(r'title\s*=\s*[\{"]?(.+?)[\}"]?\s*[,\n]', body, re.IGNORECASE | re.DOTALL)
            doi = doi_m.group(1).strip().rstrip(".") if doi_m else ""
            title = title_m.group(1).strip().strip("{}") if title_m else ""
            if not (doi or title):
                orphan_count += 1
                continue
            if not retrieval_log.exists() or not has_provenance(
                task_dir, doi=doi or None, title=title or None
            ):
                orphan_count += 1

    raw_results_missing = False
    spec_path = paper_dir / "experiment_spec.json"
    if spec_path.exists():
        # Only flag raw_results missing if the spec actually declares an experiment
        # (hypothesis non-empty). Empty templates should not trigger the flag.
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            spec = {}
        if spec.get("hypothesis"):
            if raw_results_path.exists():
                n = sum(1 for ln in raw_results_path.read_text(encoding="utf-8").splitlines() if ln.strip())
                raw_results_missing = (n == 0)
            else:
                raw_results_missing = True

    return {
        "ab_citations": len(ab_cites),
        "fulltext_missing_count": len(fulltext_missing),
        "fulltext_missing": fulltext_missing[:20],  # cap for log readability
        "retrieval_log_orphans": orphan_count,
        "bib_entries": bib_count,
        "raw_results_missing": raw_results_missing,
    }


def detect(task_dir: Path, stall_hours: float = 2.0) -> dict[str, Any]:
    state = task_dir / "state"
    progress = read_json(state / "progress.json", default={}) or {}
    findings_count = count_findings(state / "findings.jsonl")
    last_seen = progress.get("last_seen")
    idle_h = hours_since(last_seen)

    stale_count = int(progress.get("stale_count", 0))
    iteration = int(progress.get("iteration", 0))
    last_findings = int(progress.get("last_iteration_findings", 0))
    new_findings = findings_count - last_findings

    anti_hall = detect_anti_hallucination_gaps(task_dir)

    actions: list[str] = []
    if new_findings <= 0 and iteration > 0:
        stale_count += 1
        actions.append("increment_stale_count")

    if stale_count >= 2:
        actions.append("pivot_structure")
    if stale_count >= 3:
        actions.append("inject_new_direction")
    if stale_count >= 4:
        actions.append("flag_human_attention")

    if idle_h is not None and idle_h >= stall_hours:
        actions.append("nudge_work_agent")

    # Anti-hallucination gap → force re-anchor / fetch / experiment actions
    if anti_hall["fulltext_missing_count"] > 0:
        actions.append("fetch_missing_fulltext")
    if anti_hall["retrieval_log_orphans"] > 0:
        actions.append("reanchor_orphan_citations")
    if anti_hall["raw_results_missing"]:
        actions.append("rerun_or_document_experiment")

    status = progress.get("status", "initialized")
    if status == "initialized" and iteration == 0:
        actions.append("start_phase_0")

    needs_work = (
        "nudge_work_agent" in actions
        or "inject_new_direction" in actions
        or "start_phase_0" in actions
        or iteration == 0
        or "fetch_missing_fulltext" in actions
        or "reanchor_orphan_citations" in actions
        or "rerun_or_document_experiment" in actions
    )

    return {
        "task_dir": str(task_dir),
        "iteration": iteration,
        "phase": progress.get("phase", 0),
        "findings_total": findings_count,
        "new_findings_last_iter": new_findings,
        "stale_count": stale_count,
        "idle_hours": idle_h,
        "current_score": progress.get("current_score", 0.0),
        "target_score": progress.get("target_score", 8.0),
        "recommended_actions": actions,
        "needs_work_agent": needs_work,
        "anti_hallucination": anti_hall,
    }


def scan_tasks(tasks_root: Path) -> list[dict[str, Any]]:
    if not tasks_root.exists():
        return []
    results = []
    for task_dir in sorted(tasks_root.iterdir()):
        if task_dir.is_dir() and (task_dir / "state" / "progress.json").exists():
            if task_dir.name.startswith("_"):
                continue
            results.append(detect(task_dir))
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, help="Task dir or tasks/ root")
    parser.add_argument("--scan", action="store_true", help="Scan all tasks under path")
    parser.add_argument("--stall-hours", type=float, default=2.0)
    args = parser.parse_args()
    root = args.path or Path(__file__).resolve().parents[1] / "tasks"
    if args.scan or root.name == "tasks":
        out = scan_tasks(root if root.name == "tasks" else root.parent)
    else:
        out = detect(root, args.stall_hours)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
