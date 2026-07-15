#!/usr/bin/env python3
"""Semantic Scholar retrieval — cross-database + citation count (anti-hallucination v2).

Why this tool is needed:
- LQS scoring requires cites_per_month, which arXiv/CrossRef do not directly provide
- Semantic Scholar provides citationCount / influentialCitationCount
- Also serves as a fallback entry point when arXiv/CrossRef both fail to find

Supports:
1. Keyword query:  search_semantic_scholar.py --task-dir T "transformer attention"
2. Paper ID query: search_semantic_scholar.py --task-dir T --paper-id 10.1145/3524499
3. DOI query:      search_semantic_scholar.py --task-dir T --doi 10.1145/3524499
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

S2_API = "https://api.semanticscholar.org/graph/v1"
# Public free tier, works without a key, lower rate (100 req/5min)
FIELDS = "title,authors,year,venue,externalIds,citationCount,influentialCitationCount,abstract,publicationTypes,publicationVenue,openAccessPdf"


def _norm_author(a: dict) -> str:
    """Semantic Scholar returns {name, authorId}, take name."""
    name = (a.get("name") or "").strip()
    return name


def _normalize_s2(msg: dict) -> dict:
    """Normalize to unified schema."""
    authors = [_norm_author(a) for a in msg.get("authors", []) if _norm_author(a)]
    ext = msg.get("externalIds") or {}
    doi = ext.get("DOI", "")
    arxiv = ext.get("ArXiv", "")
    pub_venue = msg.get("publicationVenue") or {}
    venue = msg.get("venue", "") or (pub_venue.get("name") if pub_venue else "")
    return {
        "title": msg.get("title", "") or "",
        "authors": authors,
        "year": msg.get("year"),
        "venue": venue,
        "doi": doi.lower() if doi else "",
        "url": msg.get("openAccessPdf", {}).get("url", "") if msg.get("openAccessPdf") else "",
        "arxiv_id": arxiv,
        "volume": "",
        "issue": "",
        "page": "",
        "type": ",".join(msg.get("publicationTypes") or []),
        "publisher": "",
        "issn": [],
        "summary": msg.get("abstract", "") or "",
        "raw": {
            "paperId": msg.get("paperId", ""),
            "citationCount": msg.get("citationCount", 0),
            "influentialCitationCount": msg.get("influentialCitationCount", 0),
            "venue_type": pub_venue.get("type") if pub_venue else "",
        },
    }


def search_keyword(query: str, max_results: int = 20) -> list[dict]:
    """Keyword query."""
    params = urllib.parse.urlencode({
        "query": query,
        "limit": max_results,
        "fields": FIELDS,
    })
    url = f"{S2_API}/paper/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "AutoResearch/2.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return [_normalize_s2(it) for it in data.get("data", [])]


def fetch_by_doi(doi: str) -> dict | None:
    """Direct DOI lookup."""
    url = f"{S2_API}/paper/DOI:{urllib.parse.quote(doi, safe='')}?fields={FIELDS}"
    req = urllib.request.Request(url, headers={"User-Agent": "AutoResearch/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return _normalize_s2(json.loads(resp.read()))
    except Exception:
        return None


def fetch_by_paper_id(paper_id: str) -> dict | None:
    """Direct Semantic Scholar paperId lookup."""
    url = f"{S2_API}/paper/{urllib.parse.quote(paper_id, safe='')}?fields={FIELDS}"
    req = urllib.request.Request(url, headers={"User-Agent": "AutoResearch/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return _normalize_s2(json.loads(resp.read()))
    except Exception:
        return None


def search_and_log(*, task_dir: Path, query: str = None, doi: str = None,
                   paper_id: str = None, max_results: int = 20) -> list[dict]:
    """Unified entry point."""
    results: list[dict] = []
    if doi:
        rec = fetch_by_doi(doi)
        if rec:
            results = [rec]
        log_query = f"doi:{doi}"
    elif paper_id:
        rec = fetch_by_paper_id(paper_id)
        if rec:
            results = [rec]
        log_query = f"paperid:{paper_id}"
    elif query:
        results = search_keyword(query, max_results)
        log_query = f"kw:{query}"
    else:
        return []
    for r in results:
        raw = r.get("raw", {})
        s2_id = raw.get("paperId", "")
        log_hit(
            task_dir,
            tool="search_semantic_scholar",
            query=log_query,
            hit=r,
            source="semantic_scholar",
            source_id=f"s2:{s2_id}" if s2_id else (f"doi:{r.get('doi')}" if r.get("doi") else ""),
            extra={
                "citationCount": raw.get("citationCount", 0),
                "influentialCitationCount": raw.get("influentialCitationCount", 0),
                "arxiv_id": r.get("arxiv_id", ""),
                # Store abstract full text in extra, for check_numerical_claims.py to anchor numerical values
                "summary": r.get("summary", ""),
            },
        )
        time.sleep(1.0)  # Public tier rate limit
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Semantic Scholar retrieval (anti-hallucination v2)")
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("query", nargs="?", default=None, help="Keyword query")
    parser.add_argument("--doi", default=None)
    parser.add_argument("--paper-id", default=None, help="Semantic Scholar paperId")
    parser.add_argument("-n", "--max-results", type=int, default=20)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    if not (args.query or args.doi or args.paper_id):
        parser.error("Need query keyword or --doi or --paper-id")
    results = search_and_log(
        task_dir=args.task_dir,
        query=args.query, doi=args.doi, paper_id=args.paper_id,
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
