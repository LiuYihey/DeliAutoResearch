#!/usr/bin/env python3
"""arXiv search for literature survey stage 1."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def search_arxiv(query: str, max_results: int = 50) -> list[dict]:
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
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
        authors = [
            a.findtext("atom:name", default="", namespaces=ATOM_NS)
            for a in entry.findall("atom:author", ATOM_NS)
        ]
        link = ""
        for l in entry.findall("atom:link", ATOM_NS):
            if l.attrib.get("title") == "pdf":
                link = l.attrib.get("href", "")
                break
        arxiv_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS).split("/abs/")[-1]
        papers.append(
            {
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": [a for a in authors if a],
                "published": published[:10] if published else "",
                "summary": summary[:500],
                "pdf_url": link,
            }
        )
    return papers


def main() -> None:
    parser = argparse.ArgumentParser(description="Search arXiv (literature stage 1)")
    parser.add_argument("query", help='e.g. "all:autonomous research agents"')
    parser.add_argument("-n", "--max-results", type=int, default=50)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    results = search_arxiv(args.query, args.max_results)
    payload = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {len(results)} papers to {args.output}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
