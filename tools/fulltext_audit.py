#!/usr/bin/env python3
"""Audit fulltext files for corruption (anti-hallucination v3 — re-ground repair).

Corrupted fulltext files arise when arXiv returns an HTML rate-limit/error page
instead of a PDF; pdfminer then parses the HTML into single-character-per-line
garbage. These files are >100 bytes so fetch_fulltext.py's cache check (line 189)
treats them as valid and never re-fetches.

This script:
- Reads every *.txt in a fulltext directory (skips .meta.json and .gitkeep)
- Computes: file size, line count, average line length, real-word count
- Classifies as "corrupted" if:
    avg_line_length < 10  OR  size == 59355  OR  real_word_count < 20
  where real_word_count = number of [A-Za-z]{4,} tokens
- Prints a JSON report and optionally writes the corrupted key list to --out

Usage:
    python tools/fulltext_audit.py tasks/<slug>/paper/fulltext
    python tools/fulltext_audit.py tasks/<slug>/paper/fulltext --out corrupted_keys.txt
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REAL_WORD_RE = re.compile(r"[A-Za-z]{4,}")
# Known broken-pdfminer output size for arXiv HTML error pages
KNOWN_BAD_SIZE = 59355


def audit_file(path: Path) -> dict:
    """Return audit metrics for a single .txt file."""
    try:
        size = path.stat().st_size
    except OSError:
        return {"cite_key": path.stem, "size": 0, "lines": 0,
                "avg_line_length": 0.0, "real_word_count": 0, "corrupted": True}
    text = path.read_text(encoding="utf-8", errors="ignore")
    char_count = len(text)
    lines = text.splitlines() if text else [""]
    line_count = max(len(lines), 1)
    avg_line_length = char_count / line_count
    real_word_count = len(REAL_WORD_RE.findall(text))
    corrupted = (avg_line_length < 10) or (size == KNOWN_BAD_SIZE) or (real_word_count < 20)
    return {
        "cite_key": path.stem,
        "size": size,
        "lines": line_count,
        "avg_line_length": round(avg_line_length, 2),
        "real_word_count": real_word_count,
        "corrupted": bool(corrupted),
    }


def audit_dir(fulltext_dir: Path) -> dict:
    """Audit every *.txt file in the directory (skip .meta.json, .gitkeep)."""
    files = [p for p in sorted(fulltext_dir.glob("*.txt"))
             if p.name != ".gitkeep"]
    audits = [audit_file(p) for p in files]
    corrupted_keys = [a["cite_key"] for a in audits if a["corrupted"]]
    real_keys = [a["cite_key"] for a in audits if not a["corrupted"]]
    return {
        "total": len(audits),
        "real": len(real_keys),
        "corrupted": len(corrupted_keys),
        "corrupted_keys": corrupted_keys,
        "real_keys": real_keys,
        "details": audits,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit fulltext files for corruption (anti-hallucination v3)")
    parser.add_argument("fulltext_dir", type=Path,
                        help="Path to paper/fulltext directory")
    parser.add_argument("--out", type=Path, default=None,
                        help="Write corrupted cite_key list (one per line) to this file")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-file details to stderr")
    args = parser.parse_args()

    if not args.fulltext_dir.is_dir():
        raise SystemExit(f"Not a directory: {args.fulltext_dir}")

    report = audit_dir(args.fulltext_dir)

    if args.verbose:
        import sys
        for a in report["details"]:
            flag = "CORRUPT" if a["corrupted"] else "OK"
            sys.stderr.write(
                f"[{flag}] {a['cite_key']}: size={a['size']} "
                f"lines={a['lines']} avg={a['avg_line_length']} "
                f"words4+={a['real_word_count']}\n")

    summary = {
        "total": report["total"],
        "real": report["real"],
        "corrupted": report["corrupted"],
        "corrupted_keys": report["corrupted_keys"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.out:
        args.out.write_text(
            "\n".join(report["corrupted_keys"]) + ("\n" if report["corrupted_keys"] else ""),
            encoding="utf-8")
        print(f"\nWrote {len(report['corrupted_keys'])} corrupted keys to {args.out}",
              file=__import__("sys").stderr)


if __name__ == "__main__":
    main()
