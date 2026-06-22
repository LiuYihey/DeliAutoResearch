#!/usr/bin/env python3
"""Update task progress after an orchestrator or work iteration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from log_util import append_jsonl, read_json, read_jsonl, utc_now, write_json


def update(
    task_dir: Path,
    *,
    iteration_delta: int = 0,
    new_direction: str | None = None,
    phase: int | None = None,
    current_score: float | None = None,
    status: str | None = None,
    event: str = "iteration_complete",
    detail: str = "",
    source: str = "orchestrator",
    level: str = "info",
    touch_heartbeat: bool = True,
) -> dict:
    state = task_dir / "state"
    logs = task_dir / "logs"
    progress_path = state / "progress.json"
    progress = read_json(progress_path, default={}) or {}

    findings_count = len(read_jsonl(state / "findings.jsonl"))
    last_findings = int(progress.get("last_iteration_findings", 0))
    new_findings = findings_count - last_findings

    if iteration_delta:
        progress["iteration"] = int(progress.get("iteration", 0)) + iteration_delta
        progress["last_iteration_findings"] = findings_count
        if new_findings <= 0 and progress["iteration"] > 0:
            progress["stale_count"] = int(progress.get("stale_count", 0)) + 1
        elif new_findings > 0:
            progress["stale_count"] = 0

    progress["total_findings"] = findings_count
    if phase is not None:
        progress["phase"] = phase
    if current_score is not None:
        progress["current_score"] = current_score
    if status:
        progress["status"] = status
    if touch_heartbeat:
        progress["last_seen"] = utc_now()

    if new_direction:
        directions_path = state / "directions_tried.json"
        directions = read_json(directions_path, default=[]) or []
        if new_direction not in directions:
            directions.append(new_direction)
            write_json(directions_path, directions)

    write_json(progress_path, progress)

    append_jsonl(
        state / "iteration_log.jsonl",
        {
            "source": source,
            "level": level,
            "event": event,
            "detail": detail,
            "iteration": progress.get("iteration"),
            "new_findings": new_findings,
            "stale_count": progress.get("stale_count"),
        },
    )
    log_name = "orchestrator.jsonl" if source == "orchestrator" else "work.jsonl"
    append_jsonl(logs / log_name, {"source": source, "level": level, "event": event, "detail": detail})

    return progress


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--iteration", action="store_true", help="Bump iteration counter")
    parser.add_argument("--direction", default=None)
    parser.add_argument("--phase", type=int, default=None)
    parser.add_argument("--score", type=float, default=None)
    parser.add_argument("--status", default=None)
    parser.add_argument("--event", default="iteration_complete")
    parser.add_argument("--detail", default="")
    parser.add_argument("--source", default="orchestrator")
    args = parser.parse_args()
    out = update(
        args.task_dir,
        iteration_delta=1 if args.iteration else 0,
        new_direction=args.direction,
        phase=args.phase,
        current_score=args.score,
        status=args.status,
        event=args.event,
        detail=args.detail,
        source=args.source,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
