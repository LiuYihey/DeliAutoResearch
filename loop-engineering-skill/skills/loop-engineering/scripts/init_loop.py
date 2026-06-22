#!/usr/bin/env python3
"""Bootstrap an isolated loop workspace from skill templates."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = SKILL_ROOT / "templates"


def _replace(content: str, mapping: dict[str, str]) -> str:
    for key, val in mapping.items():
        content = content.replace(f"{{{{{key}}}}}", val)
    return content


def init_loop(
    slug: str,
    goal: str,
    workspace_parent: Path,
    archetype: str = "code-build",
    cadence: str = "2h",
    primary_metric: str = "items_done",
    target_metric: int = 100,
) -> Path:
    dest = workspace_parent / slug
    if dest.exists():
        raise SystemExit(f"Loop workspace already exists: {dest}")

    dirs = [
        "orchestrator",
        "prompts",
        "state",
        "artifacts",
        "logs",
        "scripts",
    ]
    for d in dirs:
        (dest / d).mkdir(parents=True)

    mapping = {
        "SLUG": slug,
        "GOAL": goal,
        "WORKSPACE_ROOT": str(dest.resolve()),
        "CADENCE": cadence,
        "ARCHETYPE": archetype,
        "PRIMARY_METRIC": primary_metric,
        "TARGET_METRIC": str(target_metric),
        "PHASE_0_EXIT": "intake complete",
        "PHASE_1_EXIT": "first deliverable shipped",
        "PHASE_2_EXIT": "quality gates pass",
        "PHASE_3_EXIT": "success criteria met",
        "SUB_SKILL_1": "plan",
        "SUB_SKILL_2": "implement",
        "SUB_SKILL_3": "verify",
        "OUTPUT_1": "state/loop_design.md",
        "OUTPUT_2": "artifacts/",
        "OUTPUT_3": "gate report",
        "WEAKNESS_1": "gate failure",
        "ROUTE_1": "fix",
        "WEAKNESS_2": "metric plateau",
        "ROUTE_2": "pivot",
        "WEAKNESS_3": "external block",
        "ROUTE_3": "escalate",
        "SUB_SKILL": "implement",
        "DIRECTION": "initial",
    }

    tpl_copies = [
        ("LOOP_WORKSPACE.md.tpl", "LOOP.md"),
        ("task_spec.md.tpl", "state/intake_brief.md"),
        ("progress.json.tpl", "state/progress.json"),
        ("loop_prompt.md.tpl", "orchestrator/loop_prompt.md"),
        ("router.md.tpl", "orchestrator/router.md"),
        ("direction_generator.md.tpl", "orchestrator/direction_generator.md"),
        ("work_agent.md.tpl", "prompts/work_agent.md"),
        ("watchdog.md.tpl", "orchestrator/watchdog.md"),
        ("check_gates.sh.tpl", "scripts/check_gates.sh"),
    ]

    for src_name, rel_dest in tpl_copies:
        src = TEMPLATES / src_name
        out = dest / rel_dest
        text = _replace(src.read_text(encoding="utf-8"), mapping)
        out.write_text(text, encoding="utf-8")

    # Static seed files
    (dest / "state" / "findings.jsonl").write_text("", encoding="utf-8")
    (dest / "state" / "iteration_log.jsonl").write_text("", encoding="utf-8")
    (dest / "state" / "directions_tried.json").write_text(
        json.dumps({"directions": []}, indent=2) + "\n", encoding="utf-8"
    )
    (dest / "state" / "loop_design.md").write_text(
        f"# Loop Design — {slug}\n\nArchetype: {archetype}\n\n## Phases\n\n(Customize)\n",
        encoding="utf-8",
    )

    for log in ("work", "orchestrator", "heartbeat"):
        (dest / "logs" / f"{log}.jsonl").write_text("", encoding="utf-8")

    # Copy helper scripts
    for script in ("stall_scan.py", "update_progress.py"):
        shutil.copy2(SKILL_ROOT / "scripts" / script, dest / "scripts" / script)

    now = datetime.now(timezone.utc).isoformat()
    progress = json.loads((dest / "state" / "progress.json").read_text(encoding="utf-8"))
    progress["last_seen"] = now
    (dest / "state" / "progress.json").write_text(
        json.dumps(progress, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a loop-engineering workspace")
    parser.add_argument("slug", help="kebab-case workspace name")
    parser.add_argument("--goal", required=True, help="One-line goal")
    parser.add_argument("--workspace", type=Path, default=Path("loops"))
    parser.add_argument("--archetype", default="code-build")
    parser.add_argument("--cadence", default="2h")
    parser.add_argument("--metric", default="items_done")
    parser.add_argument("--target", type=int, default=100)
    args = parser.parse_args()

    dest = init_loop(
        args.slug,
        args.goal,
        args.workspace.resolve(),
        archetype=args.archetype,
        cadence=args.cadence,
        primary_metric=args.metric,
        target_metric=args.target,
    )
    print(dest)


if __name__ == "__main__":
    main()
