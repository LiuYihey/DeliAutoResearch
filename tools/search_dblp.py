#!/usr/bin/env python3
"""DBLP retrieval — real API entry for CS conference/journal venue upgrade (anti-hallucination v2).

Why this tool is needed:
- literature_survey Stage 4 requires upgrading arXiv entries to inproceedings
- The old framework let LLMs write booktitle/pages from memory — multiple of the 13 fabricated citations were of this type
- This tool mandates that venue upgrade must go through real DBLP matching

Supports:
1. Keyword query:     search_dblp.py --task-dir T "transformer attention"
2. DOI reverse lookup:    search_dblp.py --task-dir T --doi 10.1145/3524499
3. Author query:       search_dblp.py --task-dir T --author "Lu Bao-Liang"
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_log import log_hit  # noqa: E402

DBLP_API = "https://dblp.org/search/publ/api"


def _text(node, tag: str) -> str:
    if node is None:
        return ""
    el = node.find(tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def _normalize_dblp(hit_xml, query: str) -> dict:
    """Normalize DBLP hits to the unified schema."""
    title = _text(hit_xml, "title")
    venue = _text(hit_xml, "venue")
    year = _text(hit_xml, "year")
    try:
        year_int = int(year) if year else None
    except ValueError:
        year_int = None
    authors = []
    for a in hit_xml.findall("author"):
        if a.text:
            authors.append(a.text.strip())
    doi = _text(hit_xml, "doi")
    ee = _text(hit_xml, "ee")
    pages = _text(hit_xml, "pages")
    volume = _text(hit_xml, "volume")
    number = _text(hit_xml, "number")
    pub_type = _text(hit_xml, "type")
    # key looks like "journals/tac/Vaswani12"
    key = _text(hit_xml, "key")
    return {
        "title": title,
        "authors": authors,
        "year": year_int,
        "venue": venue,
        "doi": doi.lower() if doi else "",
        "url": ee,
        "volume": volume,
        "issue": number,
        "page": pages,
        "type": pub_type,
        "publisher": "",
        "issn": [],
        "raw": {"dblp_key": key, "venue": venue, "type": pub_type},
    }


def search_dblp(query: str, max_results: int = 30) -> list[dict]:
    """Keyword query against DBLP."""
    params = urllib.parse.urlencode({
        "q": query,
        "format": "xml",
        "h": max_results,
        "f": 0,
    })
    url = f"{DBLP_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "AutoResearch/2.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        root = ET.fromstring(resp.read())
    hits = root.findall(".//hit")
    return [_normalize_dblp(h.find("info"), query) for h in hits if h.find("info") is not None]


def search_and_log(*, task_dir: Path, query: str = None, doi: str = None,
                   author: str = None, max_results: int = 30) -> list[dict]:
    """Unified entry: retrieval + write to retrieval_log."""
    log_query = ""
    results: list[dict] = []
    if doi:
        # DBLP does not support DOI queries directly, use keyword method as an approximation
        log_query = f"doi~{doi}"
        results = search_dblp(doi, max_results)
    elif author:
        log_query = f"author:{author}"
        results = search_dblp(author, max_results)
    elif query:
        log_query = f"kw:{query}"
        results = search_dblp(query, max_results)
    else:
        return []
    for r in results:
        log_hit(
            task_dir,
            tool="search_dblp",
            query=log_query,
            hit=r,
            source="dblp",
            source_id=f"dblp:{r.get('raw', {}).get('dblp_key', '')}" or "",
            extra={"venue": r.get("venue", ""), "type": r.get("type", "")},
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="DBLP retrieval (anti-hallucination v2)")
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("query", nargs="?", default=None, help="Keyword query")
    parser.add_argument("--doi", default=None, help="Use DOI for approximate matching")
    parser.add_argument("--author", default=None, help="Author query")
    parser.add_argument("-n", "--max-results", type=int, default=30)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    if not (args.query or args.doi or args.author):
        parser.error("Requires a query keyword or --doi or --author")
    results = search_and_log(
        task_dir=args.task_dir,
        query=args.query, doi=args.doi, author=args.author,
        max_results=args.max_results,
    )
    payload = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {len(results)} records to {args.output}")
    else:
        print(payload)
    print(f"Logged hits to {args.task_dir}/paper/retrieval_log.jsonl")


if __name__ == "__main__":
    main()
