#!/usr/bin/env python3
"""Detect stalls and recommend orchestrator actions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from log_util import read_json, read_jsonl


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

    status = progress.get("status", "initialized")
    if status == "initialized" and iteration == 0:
        actions.append("start_phase_0")

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
        "needs_work_agent": "nudge_work_agent" in actions
            or "inject_new_direction" in actions
            or "start_phase_0" in actions
            or iteration == 0,
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
