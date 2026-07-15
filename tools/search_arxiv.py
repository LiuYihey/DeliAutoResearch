#!/usr/bin/env python3
"""arXiv retrieval — literature survey stage 1.

Key changes (anti-hallucination v2):
1. summary is no longer truncated to 500 chars — returned in full, for check_numerical_claims.py to anchor numerical claims
2. Every hit is written to retrieval_log.jsonl (via retrieval_log.log_hit)
3. Returns unified schema fields: title/authors/year/venue/doi/url
4. CLI adds --task-dir, for anchor logging
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# Allow direct import of sibling modules from tools/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_log import log_hit  # noqa: E402

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def search_arxiv(query: str, max_results: int = 50, task_dir: Path | None = None, log_query: str | None = None) -> list[dict]:
    """Query arXiv and write every hit to retrieval_log.

    Args:
        query: arXiv query syntax, e.g. 'all:"autonomous research agents"'
        max_results: maximum number of entries to return
        task_dir: task root directory (if provided, hits are written to retrieval_log)
        log_query: query terms written to retrieval_log (defaults to query)
    """
    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    url = f"http://export.arxiv.org/api/query?{params}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        root = ET.fromstring(resp.read())

    papers = []
    for entry in root.findall("atom:entry", ATOM_NS):
        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip()
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS) or ""
        authors = [
            a.findtext("atom:name", default="", namespaces=ATOM_NS)
            for a in entry.findall("atom:author", ATOM_NS)
        ]
        authors = [a for a in authors if a]
        link = ""
        for l in entry.findall("atom:link", ATOM_NS):
            if l.attrib.get("title") == "pdf":
                link = l.attrib.get("href", "")
                break
        arxiv_url = entry.findtext("atom:id", default="", namespaces=ATOM_NS) or ""
        arxiv_id = arxiv_url.split("/abs/")[-1] if "/abs/" in arxiv_url else ""
        # DOI field (some arXiv papers have an associated DOI)
        doi = entry.findtext("arxiv:doi", default="", namespaces=ATOM_NS) or ""
        # Journal citation field (some entries come from journal-ref)
        journal_ref = entry.findtext("arxiv:journal_ref", default="", namespaces=ATOM_NS) or ""

        record = {
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "published": published[:10] if published else "",
            "year": int(published[:4]) if published[:4].isdigit() else None,
            "summary": summary,  # full text, not truncated
            "pdf_url": link,
            "url": arxiv_url,
            "doi": doi,
            "venue": journal_ref,
        }
        papers.append(record)

        if task_dir is not None:
            log_hit(
                task_dir,
                tool="search_arxiv",
                query=log_query or query,
                hit=record,
                source="arxiv",
                source_id=f"arxiv:{arxiv_id}" if arxiv_id else "",
                # summary full text stored in extra, for check_numerical_claims.py to anchor numerical claims
                extra={"journal_ref": journal_ref, "pdf_url": link, "summary": summary},
            )
    return papers


def main() -> None:
    parser = argparse.ArgumentParser(description="Search arXiv (literature stage 1) — anti-hallucination v2")
    parser.add_argument("query", help='e.g. "all:autonomous research agents"')
    parser.add_argument("-n", "--max-results", type=int, default=50)
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--task-dir", type=Path, default=None,
                        help="Task root directory; if provided, every hit is written to retrieval_log.jsonl")
    args = parser.parse_args()
    results = search_arxiv(args.query, args.max_results, task_dir=args.task_dir)
    payload = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {len(results)} papers to {args.output}")
        if args.task_dir:
            print(f"Also logged hits to {args.task_dir}/paper/retrieval_log.jsonl")
    else:
        print(payload)


if __name__ == "__main__":
    main()
