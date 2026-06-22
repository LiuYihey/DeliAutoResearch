#!/usr/bin/env python3
"""Update loop workspace progress after an iteration or heartbeat."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def count_findings(workspace: Path) -> int:
    path = workspace / "state" / "findings.jsonl"
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--iteration", action="store_true")
    parser.add_argument("--phase", type=int)
    parser.add_argument("--status")
    parser.add_argument("--source", default="cli")
    parser.add_argument("--detail", default="")
    parser.add_argument("--metric-value", type=float)
    parser.add_argument("--event", default="")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    progress_path = workspace / "state" / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()

    progress["last_seen"] = now

    if args.phase is not None:
        progress["phase"] = args.phase
    if args.status:
        progress["status"] = args.status

    if args.iteration:
        findings = count_findings(workspace)
        last = int(progress.get("last_iteration_findings", 0))
        new = findings - last
        if new > 0:
            progress["stale_count"] = 0
        progress["last_iteration_findings"] = findings
        progress["total_findings"] = findings
        progress["iteration"] = int(progress.get("iteration", 0)) + 1
        if progress.get("status") == "initialized":
            progress["status"] = "running"

        iter_log = workspace / "state" / "iteration_log.jsonl"
        entry = {
            "ts": now,
            "iteration": progress["iteration"],
            "new_findings": new,
            "detail": args.detail,
            "source": args.source,
        }
        with iter_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if args.metric_value is not None:
        progress["metric_value"] = args.metric_value

    if args.event == "heartbeat":
        log_path = workspace / "logs" / f"{args.source}.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": now,
                        "source": args.source,
                        "level": "info",
                        "event": "heartbeat",
                        "detail": args.detail or "tick",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    progress_path.write_text(json.dumps(progress, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(progress, indent=2))


if __name__ == "__main__":
    main()
