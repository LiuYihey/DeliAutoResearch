#!/usr/bin/env python3
"""Scaffold a new AutoResearch task from templates."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
DEFAULT_TASKS = ROOT / "tasks"


def init_task(slug: str, topic: str = "", tasks_dir: Path | None = None) -> Path:
    tasks_dir = tasks_dir or DEFAULT_TASKS
    dest = tasks_dir / slug
    if dest.exists():
        raise SystemExit(f"Task already exists: {dest}")

    shutil.copytree(TEMPLATES / "task", dest)

    # Anti-hallucination v3 scaffolding: ensure paper/fulltext/ + retrieval_log.jsonl
    # + raw_results.jsonl + grounded_writes/ exist from day zero.
    paper_dir = dest / "paper"
    (paper_dir / "fulltext").mkdir(exist_ok=True)
    (paper_dir / "fulltext" / ".gitkeep").write_text("", encoding="utf-8")
    (paper_dir / "grounded_writes").mkdir(exist_ok=True)
    (paper_dir / "grounded_writes" / ".gitkeep").write_text("", encoding="utf-8")
    retrieval_log = paper_dir / "retrieval_log.jsonl"
    if not retrieval_log.exists():
        retrieval_log.write_text("", encoding="utf-8")
    raw_results = paper_dir / "raw_results.jsonl"
    if not raw_results.exists():
        raw_results.write_text("", encoding="utf-8")
    citation_plan = paper_dir / "citation_plan.jsonl"
    if not citation_plan.exists():
        citation_plan.write_text("", encoding="utf-8")

    spec_path = dest / "state" / "task_spec.md"
    text = spec_path.read_text(encoding="utf-8")
    text = text.replace("{{TOPIC}}", topic or slug.replace("-", " "))
    text = text.replace("{{SLUG}}", slug)
    spec_path.write_text(text, encoding="utf-8")

    topic_val = topic or slug.replace("-", " ")
    for path in dest.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".md", ".json", ".tex", ".bib"}:
            content = path.read_text(encoding="utf-8")
            if "{{" in content:
                content = content.replace("{{TOPIC}}", topic_val).replace("{{SLUG}}", slug)
                path.write_text(content, encoding="utf-8")

    progress = json.loads((dest / "state" / "progress.json").read_text(encoding="utf-8"))
    progress["task_slug"] = slug
    progress["topic"] = topic_val
    # Anti-hallucination tracking fields (initialised empty)
    progress.setdefault("anti_hallucination", {
        "retrieval_log_entries": 0,
        "fulltext_fetched": 0,
        "fulltext_missing": 0,
        "grounded_writes_verified": 0,
        "gates_passing": [],
        "gates_failing": [],
        "last_gate_check": None,
    })
    (dest / "state" / "progress.json").write_text(
        json.dumps(progress, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a new AutoResearch task")
    parser.add_argument("slug", help="Task directory name, e.g. continual-learning-survey")
    parser.add_argument("--topic", default="", help="Human-readable research topic")
    parser.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS)
    args = parser.parse_args()
    dest = init_task(args.slug, args.topic, args.tasks_dir)
    print(dest)


if __name__ == "__main__":
    main()
