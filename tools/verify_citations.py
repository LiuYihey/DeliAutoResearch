#!/usr/bin/env python3
"""Verify bibliography entries against arXiv API (batch of 20)."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def extract_arxiv_id(entry: dict) -> str | None:
    for key in ("arxiv_id", "id", "eprint"):
        val = entry.get(key)
        if val:
            return re.sub(r"v\d+$", "", str(val).split("/")[-1])
    url = entry.get("url", "") or entry.get("pdf_url", "")
    m = re.search(r"arxiv\.org/abs/([\d.]+)", url)
    return m.group(1) if m else None


def fetch_arxiv_meta(arxiv_id: str) -> dict | None:
    params = urllib.parse.urlencode({"id_list": arxiv_id})
    url = f"http://export.arxiv.org/api/query?{params}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            root = ET.fromstring(resp.read())
    except Exception:
        return None
    entry = root.find("atom:entry", ATOM_NS)
    if entry is None:
        return None
    title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
    published = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
    return {"arxiv_id": arxiv_id, "title": title, "published": published[:10] if published else ""}


def normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower().strip())


def verify_entry(entry: dict) -> dict:
    arxiv_id = extract_arxiv_id(entry)
    result = {"key": entry.get("key", ""), "title": entry.get("title", ""), "verified": False, "reason": ""}
    if not arxiv_id:
        result["reason"] = "no_arxiv_id"
        return result
    meta = fetch_arxiv_meta(arxiv_id)
    if not meta:
        result["reason"] = "arxiv_not_found"
        return result
    local = normalize_title(entry.get("title", ""))
    remote = normalize_title(meta["title"])
    if local and remote and (local in remote or remote in local):
        result["verified"] = True
        result["arxiv_meta"] = meta
        result["reason"] = "title_match"
    else:
        result["verified"] = False
        result["arxiv_meta"] = meta
        result["reason"] = "title_mismatch"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="JSON array of bib entries to verify")
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()
    entries = json.loads(args.input.read_text(encoding="utf-8"))
    batch = entries[: args.batch_size]
    results = [verify_entry(e) for e in batch]
    verified = sum(1 for r in results if r["verified"])
    summary = {
        "checked": len(results),
        "verified": verified,
        "verification_rate": round(verified / len(results), 3) if results else 0.0,
        "results": results,
    }
    out = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
