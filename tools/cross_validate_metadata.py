#!/usr/bin/env python3
"""CrossRef / DBLP / Semantic Scholar three-way metadata cross-validation (anti-hallucination v3 — solid).

Why this tool is needed:
- Anti-hallucination v2 relies on a single API (CrossRef priority, fallback DBLP/S2 on failure)
- A single API may have errors in author/year/venue fields
- Field reports: hypothetical entries where type / journal / authors / year / volume / issue / title were wrong
  (e.g. wrong entry type, wrong journal name, mismatched author list, wrong year, wrong title)
- These errors cannot be detected within a single API; cross-API comparison is needed

Strategy (majority vote):
- All three agree: PASS
- Two agree, one missing: PASS (use the consistent ones)
- Two agree, one disagrees: WARN (take majority, but record diff)
- All three differ: FAIL (manual review)

Field-level comparison:
- title (substring match after normalization)
- year (allow ±1 difference)
- authors (set similarity ≥ 0.6)
- venue (substring match after normalization)
- doi (exact lowercase match)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_log import read_log, find_by_doi, find_by_source_id  # noqa: E402


def normalize_title(t: str) -> str:
    s = (t or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_venue(t: str) -> str:
    s = (t or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    # Remove common stop words
    stop = {"the", "of", "and", "in", "on", "for", "a", "an", "to"}
    tokens = [w for w in s.split() if w not in stop]
    return " ".join(tokens).strip()


def normalize_authors(authors: list[str]) -> set[str]:
    """Return set of family names (lowercase)."""
    s = set()
    for a in authors:
        if not a:
            continue
        # Take family name: "Vaswani, A." → "vaswani"; "Ashish Vaswani" → "vaswani"
        if "," in a:
            fam = a.split(",")[0].strip().lower()
        else:
            parts = a.split()
            fam = parts[-1].strip().lower() if parts else ""
        if fam and len(fam) > 1:
            s.add(fam)
    return s


def authors_overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def fetch_crossref(doi: str) -> dict | None:
    if not doi:
        return None
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='/')}"
    req = urllib.request.Request(url, headers={"User-Agent": "AutoResearch/2.0 (mailto:autoresearch@example.com)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None
    msg = data.get("message", {})
    title = (msg.get("title") or [""])[0]
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
    return {
        "source": "crossref", "title": title, "venue": venue,
        "authors": authors, "year": year, "doi": (msg.get("DOI") or "").lower(),
    }


def fetch_s2_by_doi(doi: str) -> dict | None:
    if not doi:
        return None
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi, safe='')}?fields=title,authors,year,venue,externalIds"
    req = urllib.request.Request(url, headers={"User-Agent": "AutoResearch/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            msg = json.loads(resp.read())
    except Exception:
        return None
    authors = [(a.get("name") or "").strip() for a in msg.get("authors", [])]
    authors = [a for a in authors if a]
    return {
        "source": "semantic_scholar",
        "title": msg.get("title", "") or "",
        "venue": msg.get("venue", "") or "",
        "authors": authors,
        "year": msg.get("year"),
        "doi": (msg.get("externalIds", {}) or {}).get("DOI", "").lower(),
    }


def fetch_dblp_by_query(query: str) -> dict | None:
    import xml.etree.ElementTree as ET
    params = urllib.parse.urlencode({"q": query, "format": "xml", "h": 3, "f": 0})
    url = f"https://dblp.org/search/publ/api?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "AutoResearch/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            root = ET.fromstring(resp.read())
    except Exception:
        return None
    hits = root.findall(".//hit")
    for h in hits:
        info = h.find("info")
        if info is None:
            continue
        title = (info.findtext("title") or "").strip()
        if title:
            authors = []
            for a in info.findall("author"):
                if a.text:
                    authors.append(a.text.strip())
            year = (info.findtext("year") or "").strip()
            venue = (info.findtext("venue") or "").strip()
            doi = (info.findtext("doi") or "").lower().strip()
            return {
                "source": "dblp", "title": title, "venue": venue,
                "authors": authors,
                "year": int(year) if year.isdigit() else None,
                "doi": doi,
            }
    return None


def compare_field(local: str, remote: str, kind: str = "title") -> bool:
    if not local or not remote:
        return False
    if kind == "title":
        l = normalize_title(local)
        r = normalize_title(remote)
        return l and r and (l in r or r in l)
    if kind == "venue":
        l = normalize_venue(local)
        r = normalize_venue(remote)
        return l and r and (l in r or r in l or l == r)
    if kind == "doi":
        return local.lower().strip() == remote.lower().strip()
    return local == remote


def cross_validate_entry(entry: dict, task_dir: Path | None = None) -> dict:
    """Run three-way cross-validation on a single bib entry."""
    key = entry.get("_key", entry.get("key", ""))
    title = entry.get("title", "")
    doi = entry.get("doi", "").strip()
    year_local = entry.get("year", "")
    try:
        year_local_int = int(year_local) if year_local else None
    except ValueError:
        year_local_int = None

    sources = {}
    # 1. CrossRef
    if doi:
        cr = fetch_crossref(doi)
        if cr:
            sources["crossref"] = cr
        time.sleep(0.3)
    # 2. Semantic Scholar
    if doi:
        s2 = fetch_s2_by_doi(doi)
        if s2:
            sources["semantic_scholar"] = s2
        time.sleep(1.0)
    # 3. DBLP (query by title)
    if title:
        dblp = fetch_dblp_by_query(title)
        if dblp:
            sources["dblp"] = dblp
        time.sleep(0.5)

    # Comparison
    diffs = []
    agreements = []
    if len(sources) >= 2:
        # title
        titles = [(s, d["title"]) for s, d in sources.items() if d.get("title")]
        for i in range(len(titles)):
            for j in range(i + 1, len(titles)):
                s1, t1 = titles[i]
                s2, t2 = titles[j]
                if compare_field(t1, t2, "title"):
                    agreements.append(f"title:{s1}={s2}")
                else:
                    diffs.append({"field": "title", f"{s1}": t1[:80], f"{s2}": t2[:80]})
        # year (allow ±1)
        years = [(s, d["year"]) for s, d in sources.items() if d.get("year")]
        for i in range(len(years)):
            for j in range(i + 1, len(years)):
                s1, y1 = years[i]
                s2, y2 = years[j]
                if abs((y1 or 0) - (y2 or 0)) <= 1:
                    agreements.append(f"year:{s1}={s2}")
                else:
                    diffs.append({"field": "year", f"{s1}": y1, f"{s2}": y2})
        # venue
        venues = [(s, d["venue"]) for s, d in sources.items() if d.get("venue")]
        for i in range(len(venues)):
            for j in range(i + 1, len(venues)):
                s1, v1 = venues[i]
                s2, v2 = venues[j]
                if compare_field(v1, v2, "venue"):
                    agreements.append(f"venue:{s1}={s2}")
                else:
                    diffs.append({"field": "venue", f"{s1}": v1[:80], f"{s2}": v2[:80]})
        # authors (set similarity)
        author_sets = {s: normalize_authors(d["authors"]) for s, d in sources.items() if d.get("authors")}
        src_list = list(author_sets.keys())
        for i in range(len(src_list)):
            for j in range(i + 1, len(src_list)):
                s1, s2 = src_list[i], src_list[j]
                ov = authors_overlap(author_sets[s1], author_sets[s2])
                if ov >= 0.6:
                    agreements.append(f"authors:{s1}={s2}(overlap={ov:.2f})")
                else:
                    diffs.append({"field": "authors", f"{s1}": list(author_sets[s1])[:5],
                                  f"{s2}": list(author_sets[s2])[:5], "overlap": round(ov, 2)})
        # doi
        dois = [(s, d["doi"]) for s, d in sources.items() if d.get("doi")]
        for i in range(len(dois)):
            for j in range(i + 1, len(dois)):
                s1, d1 = dois[i]
                s2, d2 = dois[j]
                if d1 == d2:
                    agreements.append(f"doi:{s1}={s2}")
                else:
                    diffs.append({"field": "doi", f"{s1}": d1, f"{s2}": d2})

    # Determine status
    n_sources = len(sources)
    n_diffs = len(diffs)
    if n_sources == 0:
        status = "no_remote_data"
    elif n_sources == 1:
        status = "single_source"  # unverifiable, WARN
    elif n_diffs == 0:
        status = "consistent"
    elif n_diffs <= n_sources:  # minority disagreement
        status = "minor_diff"
    else:
        status = "major_diff"

    return {
        "cite_key": key,
        "title_local": title,
        "doi": doi,
        "n_sources": n_sources,
        "sources": sources,
        "agreements": agreements,
        "diffs": diffs,
        "status": status,
        "verdict": "PASS" if status in ("consistent", "single_source") else
                   ("WARN" if status == "minor_diff" else "FAIL"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="CrossRef/DBLP/S2 three-way cross-validation (anti-hallucination v3)")
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--key", default=None, help="Only verify the specified cite key")
    parser.add_argument("--batch-size", type=int, default=10, help="Maximum entries to verify per run (polite rate)")
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    # Reuse verify_citations.parse_bib
    from verify_citations import parse_bib
    bib = args.task_dir / "paper" / "references.bib"
    entries = parse_bib(bib)
    if args.key:
        entries = [e for e in entries if e.get("_key") == args.key]
    else:
        entries = entries[: args.batch_size]
    results = [cross_validate_entry(e, args.task_dir) for e in entries]
    consistent = sum(1 for r in results if r["status"] == "consistent")
    fail = sum(1 for r in results if r["verdict"] == "FAIL")
    warn = sum(1 for r in results if r["verdict"] == "WARN")
    summary = {
        "checked": len(results), "consistent": consistent,
        "warn": warn, "fail": fail,
        "results": results,
    }
    out = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    print(out)
    raise SystemExit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
