#!/usr/bin/env python3
"""Detect stalls and recommend orchestrator actions for a loop workspace."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def count_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def detect(workspace: Path, stall_hours: float = 2.0) -> dict[str, Any]:
    state = workspace / "state"
    progress_path = state / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))

    findings_count = count_lines(state / "findings.jsonl")
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

    needs_work = (
        "nudge_work_agent" in actions
        or "inject_new_direction" in actions
        or "start_phase_0" in actions
        or status == "running"
    )

    return {
        "workspace": str(workspace.resolve()),
        "iteration": iteration,
        "phase": progress.get("phase", 0),
        "findings_total": findings_count,
        "new_findings_last_iter": new_findings,
        "stale_count": stale_count,
        "idle_hours": idle_h,
        "metric_value": progress.get("metric_value", 0),
        "target_metric_value": progress.get("target_metric_value", 0),
        "recommended_actions": actions,
        "needs_work_agent": needs_work and status not in ("done", "needs_human"),
        "status": status,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path, nargs="?", default=".")
    parser.add_argument("--stall-hours", type=float, default=2.0)
    parser.add_argument("--apply", action="store_true", help="Write stale_count back to progress.json")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    result = detect(workspace, args.stall_hours)

    if args.apply:
        progress_path = workspace / "state" / "progress.json"
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        progress["stale_count"] = result["stale_count"]
        progress_path.write_text(json.dumps(progress, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
