#!/usr/bin/env python3
"""CrossRef retrieval — real API entry for journal/conference papers (anti-hallucination v2).

Why this tool is needed:
- arXiv API only returns preprints, not covering formally published journal/conference versions
- The old framework allowed LLMs to "fill in from memory" non-arXiv entries — this is the source of 13/13 fabricated citations
- This tool mandates that all non-arXiv citations must go through real CrossRef retrieval

Supports three query types:
1. Direct DOI lookup (most authoritative): search_crossref.py --doi 10.1109/T-AFFC.2011.15
2. Title query:        search_crossref.py --title "Attention is all you need"
3. Author+year query:   search_crossref.py --author "Vaswani" --year 2017

Every hit is written to retrieval_log.jsonl, providing the anchor for Gate 1.5.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_log import log_hit  # noqa: E402

CROSSREF_API = "https://api.crossref.org/works"
MAILTO = "autoresearch@example.com"  # CrossRef recommends mailto to enter the polite pool


def _norm_date(d: str) -> str:
    """CrossRef returns '2020-03-15' or '2020-3', take the first 4 chars as year."""
    if not d:
        return ""
    return d[:4] if d[:4].isdigit() else ""


def fetch_by_doi(doi: str) -> dict | None:
    """Direct DOI lookup, returns normalized record or None."""
    url = f"{CROSSREF_API}/{urllib.parse.quote(doi, safe='/')}"
    req = urllib.request.Request(url, headers={"User-Agent": f"AutoResearch/2.0 (mailto:{MAILTO})"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None
    msg = data.get("message", {})
    return _normalize_crossref(msg, doi=doi)


def search_by_title(title: str, max_results: int = 20) -> list[dict]:
    """Query by title."""
    params = urllib.parse.urlencode({
        "query.bibliographic": title,
        "rows": max_results,
        "select": "DOI,title,author,container-title,published,volume,issue,page,type,ISSN,publisher",
        "mailto": MAILTO,
    })
    url = f"{CROSSREF_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": f"AutoResearch/2.0 (mailto:{MAILTO})"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    items = data.get("message", {}).get("items", [])
    return [_normalize_crossref(it) for it in items]


def search_by_author(author: str, year: int | None = None, max_results: int = 20) -> list[dict]:
    """Query by author (+year)."""
    query = {"query.author": author, "rows": max_results,
             "select": "DOI,title,author,container-title,published,volume,issue,page,type,ISSN,publisher",
             "mailto": MAILTO}
    if year:
        query["filter"] = f"from-pub-date:{year},until-pub-date:{year}"
    params = urllib.parse.urlencode(query)
    url = f"{CROSSREF_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": f"AutoResearch/2.0 (mailto:{MAILTO})"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    items = data.get("message", {}).get("items", [])
    return [_normalize_crossref(it) for it in items]


def _normalize_crossref(msg: dict, doi: str = None) -> dict:
    """Normalize CrossRef raw response to the unified schema."""
    title_list = msg.get("title") or []
    title = title_list[0] if title_list else ""
    container = msg.get("container-title") or []
    venue = container[0] if container else ""
    authors = []
    for a in msg.get("author", []):
        given = (a.get("given") or "").strip()
        family = (a.get("family") or "").strip()
        if family:
            authors.append(f"{family}, {given}" if given else family)
    published = msg.get("published-print") or msg.get("published-online") or msg.get("issued") or {}
    parts = published.get("date-parts", [[]])
    year = parts[0][0] if parts and parts[0] else None
    raw_doi = doi or msg.get("DOI", "")
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "doi": raw_doi.lower() if raw_doi else "",
        "volume": msg.get("volume", ""),
        "issue": msg.get("issue", ""),
        "page": msg.get("page", ""),
        "type": msg.get("type", ""),
        "publisher": msg.get("publisher", ""),
        "url": msg.get("URL", ""),
        "issn": msg.get("ISSN", []),
        "raw": msg,  # raw response, for subsequent audit
    }


def search_and_log(
    *,
    task_dir: Path,
    doi: str = None,
    title: str = None,
    author: str = None,
    year: int = None,
    max_results: int = 20,
    log_query: str = None,
) -> list[dict]:
    """Unified entry: retrieval + write to retrieval_log. Returns the list of hits."""
    results: list[dict] = []
    if doi:
        rec = fetch_by_doi(doi)
        if rec:
            results = [rec]
            log_query = log_query or f"doi:{doi}"
    elif title:
        results = search_by_title(title, max_results)
        log_query = log_query or f"title:{title}"
    elif author:
        results = search_by_author(author, year, max_results)
        log_query = log_query or f"author:{author},year:{year}"
    else:
        return []
    # Write to retrieval_log
    for r in results:
        log_hit(
            task_dir,
            tool="search_crossref",
            query=log_query,
            hit=r,
            source="crossref",
            source_id=f"doi:{r['doi']}" if r.get("doi") else "",
            extra={
                "type": r.get("type", ""),
                "publisher": r.get("publisher", ""),
                "issn": r.get("issn", []),
            },
        )
        time.sleep(0.05)  # friendly to the polite pool
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="CrossRef retrieval (anti-hallucination v2)")
    parser.add_argument("--task-dir", type=Path, required=True,
                        help="Task root directory (required, for writing to retrieval_log)")
    parser.add_argument("--doi", default=None, help="Direct DOI query")
    parser.add_argument("--title", default=None, help="Title query")
    parser.add_argument("--author", default=None, help="Author query")
    parser.add_argument("--year", type=int, default=None, help="Used together with --author")
    parser.add_argument("-n", "--max-results", type=int, default=20)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    if not (args.doi or args.title or args.author):
        parser.error("At least one of --doi / --title / --author is required")
    results = search_and_log(
        task_dir=args.task_dir,
        doi=args.doi, title=args.title, author=args.author, year=args.year,
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
