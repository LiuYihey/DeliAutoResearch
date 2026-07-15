#!/usr/bin/env python3
"""Unified API call logging tool — mandatory dependency for all retrieval tools.

Design goals:
- Any entry written to references.bib must have a corresponding API call record in retrieval_log.jsonl
- Entries without an anchor are considered fabricated and are blocked by Gate 1.5
- Supports post-hoc audit: given a bib entry, trace back to the original query and API response

Calling convention:
    from retrieval_log import log_hit, has_provenance, find_by_doi
    log_hit(paper_dir, tool="search_arxiv", query="all:transformer attention",
            hit=record_dict, source_id="arxiv:1234.5678")
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOG_FILENAME = "retrieval_log.jsonl"
LOG_DIRNAME = "paper"  # relative to task_dir


def _log_path(task_dir: Path) -> Path:
    """Return task_dir/paper/retrieval_log.jsonl, creating parent directory if it does not exist."""
    p = task_dir / LOG_DIRNAME / LOG_FILENAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _stable_id(record: dict) -> str:
    """Generate a stable hash based on source + source_id to avoid duplicate records."""
    raw = f"{record.get('source','')}|{record.get('source_id','')}|{record.get('title','')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def log_hit(
    task_dir: Path,
    *,
    tool: str,
    query: str,
    hit: dict,
    source: str,
    source_id: str,
    extra: dict | None = None,
) -> dict:
    """Log an API hit. Returns the written record.

    Args:
        task_dir: task root directory (containing paper/ subdirectory)
        tool: calling tool name, e.g. "search_arxiv" / "search_crossref"
        query: original query terms (for audit traceability)
        hit: normalized metadata dict returned by API (at least containing title/authors/year)
        source: source database, e.g. "arxiv" / "crossref" / "dblp" / "semantic_scholar"
        source_id: stable ID within the database, e.g. "arxiv:1234.5678" / "doi:10.xxx/yyy"
        extra: extra fields (citation_count, venue_tier, etc.)

    Note:
        - The same source+source_id+title is only written once (deduplicated by stable_id)
        - The caller is responsible for normalizing hit fields to the unified schema:
          title, authors(list[str]), year(int), venue, doi, url
    """
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": tool,
        "query": query,
        "source": source,
        "source_id": source_id,
        "stable_id": _stable_id({"source": source, "source_id": source_id, "title": hit.get("title", "")}),
        "title": hit.get("title", ""),
        "authors": hit.get("authors", []),
        "year": hit.get("year"),
        "venue": hit.get("venue", ""),
        "doi": hit.get("doi", ""),
        "url": hit.get("url", ""),
        "extra": extra or {},
    }
    log_path = _log_path(task_dir)
    # Deduplication: do not write again if the same stable_id already exists
    existing_ids: set[str] = set()
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                existing_ids.add(rec.get("stable_id", ""))
            except json.JSONDecodeError:
                continue
    if record["stable_id"] not in existing_ids:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_log(task_dir: Path) -> list[dict]:
    """Read all retrieval_log records."""
    log_path = _log_path(task_dir)
    if not log_path.exists():
        return []
    out = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def has_provenance(task_dir: Path, *, doi: str = None, source_id: str = None, title: str = None) -> bool:
    """Check whether the given identifier has an anchor in retrieval_log.

    Priority: doi > source_id > title (fuzzy match)
    """
    if not (doi or source_id or title):
        return False
    records = read_log(task_dir)
    doi_norm = doi.lower().strip() if doi else None
    sid_norm = source_id.lower().strip() if source_id else None
    title_norm = re.sub(r"\s+", " ", title.lower().strip()) if title else None
    for r in records:
        if doi_norm and r.get("doi", "").lower().strip() == doi_norm:
            return True
        if sid_norm and r.get("source_id", "").lower().strip() == sid_norm:
            return True
        if title_norm:
            r_title = re.sub(r"\s+", " ", r.get("title", "").lower().strip())
            if title_norm and r_title and (title_norm in r_title or r_title in title_norm):
                return True
    return False


def find_by_doi(task_dir: Path, doi: str) -> dict | None:
    """Find the original record in retrieval_log by DOI."""
    doi_norm = doi.lower().strip()
    for r in read_log(task_dir):
        if r.get("doi", "").lower().strip() == doi_norm:
            return r
    return None


def find_by_source_id(task_dir: Path, source_id: str) -> dict | None:
    """Find by source_id."""
    sid_norm = source_id.lower().strip()
    for r in read_log(task_dir):
        if r.get("source_id", "").lower().strip() == sid_norm:
            return r
    return None


def stats(task_dir: Path) -> dict:
    """Return statistics grouped by source."""
    from collections import Counter
    records = read_log(task_dir)
    by_source = Counter(r.get("source", "unknown") for r in records)
    return {
        "total": len(records),
        "by_source": dict(by_source),
        "log_path": str(_log_path(task_dir)),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Query retrieval_log status")
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--doi", default=None, help="Check whether the DOI has an anchor")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    args = parser.parse_args()
    if args.doi:
        ok = has_provenance(args.task_dir, doi=args.doi)
        print(json.dumps({"doi": args.doi, "has_provenance": ok}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(stats(args.task_dir), ensure_ascii=False, indent=2))
