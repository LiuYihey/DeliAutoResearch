#!/usr/bin/env python3
"""Verify bibliography entries (anti-hallucination v2).

Key changes:
1. No longer arXiv-only — priority DOI > arXiv > title query, covering all entry types
2. Use CrossRef API to verify non-arXiv entries (old version skipped them, blind spot for 13 fabricated citations)
3. Returns verified_metadata, for apply_metadata.py to auto-overwrite fields LLM wrote incorrectly
4. Linked with retrieval_log: on verification, log a provenance anchor
5. Failed entries marked as hallucinated, for Gate 1.5 to block

Usage:
    python tools/verify_citations.py task_dir --batch-size 20
    python tools/verify_citations.py task_dir --key vaswani2017attention
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_log import has_provenance, log_hit, find_by_doi  # noqa: E402

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
CROSSREF_API = "https://api.crossref.org/works"
MAILTO = "autoresearch@example.com"


# ---------------- BibTeX parsing ----------------

BIB_ENTRY_RE = re.compile(r"@(\w+)\s*\{([^,]+),\s*(.*?)\n\}", re.DOTALL)
BIB_FIELD_RE = re.compile(r'(\w+)\s*=\s*[\{"]?(.*?)[\}"]?\s*(?:,\s*\n|\n\}|\Z)', re.DOTALL)


def parse_bib(bib_path: Path) -> list[dict]:
    """Simple BibTeX parser (good enough)."""
    if not bib_path.exists():
        return []
    text = bib_path.read_text(encoding="utf-8", errors="ignore")
    entries = []
    for m in BIB_ENTRY_RE.finditer(text):
        entry_type, key, body = m.group(1), m.group(2).strip(), m.group(3)
        fields = {"_type": entry_type, "_key": key}
        for fm in BIB_FIELD_RE.finditer(body):
            fname = fm.group(1).lower()
            fval = fm.group(2).strip().strip("{}").strip('"')
            fields[fname] = fval
        entries.append(fields)
    return entries


def extract_arxiv_id(entry: dict) -> str | None:
    for key in ("arxiv_id", "eprint"):
        val = entry.get(key)
        if val:
            return re.sub(r"v\d+$", "", str(val).split("/")[-1])
    url = entry.get("url", "")
    m = re.search(r"arxiv\.org/abs/([\d.]+)", url)
    return m.group(1) if m else None


def normalize_title(t: str) -> str:
    """Normalize title: lowercase + fold whitespace + strip punctuation (CrossRef occasionally inserts semicolons/colons)."""
    s = (t or "").lower()
    # Remove non-alphanumeric non-whitespace characters (semicolons, colons, hyphens, etc.)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------- Three-path verification ----------------

def verify_via_arxiv(arxiv_id: str, local_title: str) -> dict:
    """arXiv path."""
    params = urllib.parse.urlencode({"id_list": arxiv_id})
    url = f"http://export.arxiv.org/api/query?{params}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            root = ET.fromstring(resp.read())
    except Exception as e:
        return {"verified": False, "reason": f"arxiv_error:{type(e).__name__}"}
    entry = root.find("atom:entry", ATOM_NS)
    if entry is None:
        return {"verified": False, "reason": "arxiv_not_found"}
    title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
    published = entry.findtext("atom:published", default="", namespaces=ATOM_NS) or ""
    authors = [
        a.findtext("atom:name", default="", namespaces=ATOM_NS)
        for a in entry.findall("atom:author", ATOM_NS)
    ]
    authors = [a for a in authors if a]
    local = normalize_title(local_title)
    remote = normalize_title(title)
    verified = bool(local and remote and (local in remote or remote in local))
    return {
        "verified": verified,
        "reason": "title_match" if verified else "title_mismatch",
        "verified_metadata": {
            "title": title, "authors": authors, "year": int(published[:4]) if published[:4].isdigit() else None,
            "arxiv_id": arxiv_id, "source": "arxiv",
        },
    }


def verify_via_crossref_doi(doi: str, local_title: str) -> dict:
    """CrossRef DOI path — most authoritative."""
    url = f"{CROSSREF_API}/{urllib.parse.quote(doi, safe='/')}"
    req = urllib.request.Request(url, headers={"User-Agent": f"AutoResearch/2.0 (mailto:{MAILTO})"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return {"verified": False, "reason": f"crossref_error:{type(e).__name__}"}
    msg = data.get("message", {})
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
    local = normalize_title(local_title)
    remote = normalize_title(title)
    verified = bool(local and remote and (local in remote or remote in local))
    return {
        "verified": verified,
        "reason": "doi_title_match" if verified else "doi_title_mismatch",
        "verified_metadata": {
            "title": title, "authors": authors, "year": year, "venue": venue,
            "doi": doi.lower(), "volume": msg.get("volume", ""), "issue": msg.get("issue", ""),
            "page": msg.get("page", ""), "type": msg.get("type", ""), "publisher": msg.get("publisher", ""),
            "source": "crossref",
        },
    }


def verify_via_crossref_title(title: str) -> dict:
    """CrossRef title query path — used when no DOI."""
    params = urllib.parse.urlencode({
        "query.bibliographic": title,
        "rows": 5,
        "select": "DOI,title,author,container-title,published,volume,issue,page,type,publisher",
        "mailto": MAILTO,
    })
    url = f"{CROSSREF_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": f"AutoResearch/2.0 (mailto:{MAILTO})"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return {"verified": False, "reason": f"crossref_search_error:{type(e).__name__}"}
    items = data.get("message", {}).get("items", [])
    if not items:
        return {"verified": False, "reason": "crossref_no_match"}
    local = normalize_title(title)
    best = None
    for it in items:
        titles = it.get("title") or []
        rt = titles[0] if titles else ""
        if not rt:
            continue
        rn = normalize_title(rt)
        if local in rn or rn in local:
            best = it
            break
    if not best:
        return {"verified": False, "reason": "crossref_no_title_match",
                "candidates": [t.get("title", [""])[0] if t.get("title") else "" for t in items[:3]]}
    container = best.get("container-title") or []
    venue = container[0] if container else ""
    authors = []
    for a in best.get("author", []):
        given = (a.get("given") or "").strip()
        family = (a.get("family") or "").strip()
        if family:
            authors.append(f"{family}, {given}" if given else family)
    published = best.get("published-print") or best.get("published-online") or best.get("issued") or {}
    parts = published.get("date-parts", [[]])
    year = parts[0][0] if parts and parts[0] else None
    return {
        "verified": True,
        "reason": "title_query_match",
        "verified_metadata": {
            "title": (best.get("title") or [""])[0], "authors": authors, "year": year, "venue": venue,
            "doi": (best.get("DOI") or "").lower(), "volume": best.get("volume", ""),
            "issue": best.get("issue", ""), "page": best.get("page", ""),
            "type": best.get("type", ""), "publisher": best.get("publisher", ""),
            "source": "crossref",
        },
    }


def verify_via_dblp(query: str) -> dict:
    """DBLP fallback path — for CS conference papers, when arXiv/CrossRef both fail."""
    params = urllib.parse.urlencode({"q": query, "format": "xml", "h": 5, "f": 0})
    url = f"https://dblp.org/search/publ/api?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "AutoResearch/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            root = ET.fromstring(resp.read())
    except Exception as e:
        return {"verified": False, "reason": f"dblp_error:{type(e).__name__}"}
    hits = root.findall(".//hit")
    if not hits:
        return {"verified": False, "reason": "dblp_no_match"}
    # Take the first one with a title
    for h in hits:
        info = h.find("info")
        if info is None:
            continue
        title_el = info.find("title")
        if title_el is not None and title_el.text:
            return {
                "verified": True,
                "reason": "dblp_match",
                "verified_metadata": {
                    "title": title_el.text.strip(),
                    "venue": (info.findtext("venue") or "").strip(),
                    "year": int(info.findtext("year") or 0) or None,
                    "doi": (info.findtext("doi") or "").lower(),
                    "url": (info.findtext("ee") or "").strip(),
                    "source": "dblp",
                },
            }
    return {"verified": False, "reason": "dblp_no_match"}


# ---------------- Main entry ----------------

def verify_entry(entry: dict, task_dir: Path | None = None) -> dict:
    """Priority: DOI (CrossRef) > arXiv > title (CrossRef) > title (DBLP)."""
    key = entry.get("_key", "")
    title = entry.get("title", "")
    doi = entry.get("doi", "").strip()
    arxiv_id = extract_arxiv_id(entry)
    result = {"key": key, "title": title, "verified": False, "reason": "", "verified_metadata": None}

    # Already in retrieval_log, pass directly
    if task_dir is not None and doi and has_provenance(task_dir, doi=doi):
        result["verified"] = True
        result["reason"] = "retrieval_log_anchor"
        result["verified_metadata"] = {"doi": doi.lower(), "source": "retrieval_log"}

    if not result["verified"]:
        if doi:
            r = verify_via_crossref_doi(doi, title)
        elif arxiv_id:
            r = verify_via_arxiv(arxiv_id, title)
        elif title:
            r = verify_via_crossref_title(title)
            if not r["verified"]:
                # DBLP fallback
                r2 = verify_via_dblp(title)
                if r2["verified"]:
                    r = r2
        else:
            r = {"verified": False, "reason": "no_identifier"}
        result.update(r)

    # Verified → add a retrieval_log anchor (if task_dir provided and no current record)
    if result["verified"] and task_dir is not None:
        meta = result.get("verified_metadata") or {}
        if meta.get("doi") and not has_provenance(task_dir, doi=meta["doi"]):
            log_hit(
                task_dir, tool="verify_citations", query=f"verify:{key}",
                hit=meta, source=meta.get("source", "crossref"),
                source_id=f"doi:{meta['doi']}",
                extra={"reason": result["reason"]},
            )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify bib entries (anti-hallucination v2)")
    parser.add_argument("task_dir", type=Path, help="Task root directory (for retrieval_log)")
    parser.add_argument("--bib", type=Path, default=None, help="bib path (default task_dir/paper/references.bib)")
    parser.add_argument("--key", default=None, help="Only verify the specified cite key")
    parser.add_argument("--batch-size", type=int, default=20, help="Maximum entries to verify per run (polite rate)")
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    bib = args.bib or (args.task_dir / "paper" / "references.bib")
    entries = parse_bib(bib)
    if args.key:
        entries = [e for e in entries if e.get("_key") == args.key]
    else:
        entries = entries[: args.batch_size]
    results = []
    for e in entries:
        r = verify_entry(e, task_dir=args.task_dir)
        results.append(r)
        time.sleep(0.2)  # Polite rate
    verified = sum(1 for r in results if r["verified"])
    hallucinated = [r for r in results if not r["verified"]]
    summary = {
        "checked": len(results),
        "verified": verified,
        "verification_rate": round(verified / len(results), 3) if results else 0.0,
        "hallucinated_count": len(hallucinated),
        "hallucinated_keys": [r["key"] for r in hallucinated],
        "results": results,
    }
    out = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    print(out)
    # Exit code: 1 if hallucinations exist
    raise SystemExit(0 if not hallucinated else 1)


if __name__ == "__main__":
    main()
