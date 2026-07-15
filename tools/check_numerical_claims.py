#!/usr/bin/env python3
"""Scan numerical claims in section files and anchor them to cited original text (anti-hallucination v2).

Why this tool is needed:
- Field report section 6: precise numbers appear in sections like "SI 58.6%", "82% accuracy", "N=24, RCT"
- The old search_arxiv.py truncated summary to 500 chars, so LLM fabricated numbers from memory when writing sections
- The old framework had no mechanism to verify: whether these numbers really came from the cited paper

Workflow:
1. Scan sections/*.tex, extract all numerical claims near cite commands
2. For each claim, find the retrieval_log record for that key
3. Check whether the number appears in the summary/abstract of retrieval_log
4. Unanchored claims are marked unverified, blocking the gate

Numerical patterns (extensible):
- percent:   58.6%, 82 %
- pp/pp:     10.4 pp, 5.2pp
- N=:        N=24, N = 30
- accuracy/ACC: ACC 0.85
- Hz/ms:     32 Hz, 250 ms
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_log import find_by_doi, find_by_source_id, read_log  # noqa: E402


def load_fulltext_for_key(cite_key: str, task_dir: Path) -> str | None:
    """Load full text from paper/fulltext/<cite_key>.txt (anti-hallucination v3)."""
    p = task_dir / "paper" / "fulltext" / f"{cite_key}.txt"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore")
    return None

# Numerical claim patterns
NUM_PATTERNS = [
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*\\?%"), "percent"),       # 58.6%, 82 %, 91.97\% (LaTeX-escaped)
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*pp\b", re.IGNORECASE), "pp"),  # 10.4 pp
    (re.compile(r"\bN\s*=\s*(\d+)\b", re.IGNORECASE), "n_value"),    # N=24
    (re.compile(r"\bACC\s*[:=]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE), "acc"),  # ACC 0.85
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*Hz\b", re.IGNORECASE), "hz"),  # 32 Hz
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*ms\b", re.IGNORECASE), "ms"),  # 250 ms
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:±|pm)\s*(\d+(?:\.\d+)?)", re.IGNORECASE), "mean_pm_std"),
]

# \cite{} extraction
CITE_RE = re.compile(r"\\cite\{([^}]+)\}")


def extract_claims_from_line(line: str, file_path: Path, line_no: int) -> list[dict]:
    """Extract (cite_key, numerical claim) pairs from a LaTeX line."""
    claims = []
    cites = CITE_RE.findall(line)
    cite_keys = []
    for c in cites:
        cite_keys.extend([k.strip() for k in c.split(",")])
    for pat, kind in NUM_PATTERNS:
        for m in pat.finditer(line):
            num_str = m.group(1)
            # Take two segments for ± pattern
            value = num_str
            if kind == "mean_pm_std":
                value = f"{m.group(1)}±{m.group(2)}"
            # Take 60 chars before/after the number in line as context
            ctx_start = max(0, m.start() - 60)
            ctx_end = min(len(line), m.end() + 60)
            context = line[ctx_start:ctx_end].strip()
            claims.append({
                "file": str(file_path),
                "line": line_no,
                "kind": kind,
                "value": value,
                "context": context,
                "nearby_cite_keys": cite_keys,
            })
    return claims


def scan_sections(sections_dir: Path) -> list[dict]:
    """Scan all .tex files in the sections AND tables directories (anti-hallucination v3).

    Tables are scanned too because table cells contain numerical claims (accuracies, F1,
    trial counts) that must be anchored just like section prose. Not scanning tables
    was the loophole that left Gate 1.6 reporting total_claims=0.
    """
    claims = []
    if sections_dir.exists():
        for tex in sorted(sections_dir.glob("*.tex")):
            for i, line in enumerate(tex.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                claims.extend(extract_claims_from_line(line, tex, i))
    # Also scan tables/*.tex (close the table-claim loophole)
    if sections_dir.name == "sections":
        tables_dir = sections_dir.parent / "tables"
        if tables_dir.exists():
            for tex in sorted(tables_dir.glob("*.tex")):
                for i, line in enumerate(tex.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    claims.extend(extract_claims_from_line(line, tex, i))
    return claims


def anchor_claim(claim: dict, task_dir: Path) -> dict:
    """Anchor numerical claim to full text (anti-hallucination v3 — solid evidence).

    Priority:
    1. fulltext/<cite_key>.txt  (full text parsed from PDF, most authoritative)
    2. retrieval_log's extra.summary (arXiv/S2 abstract, fallback)
    3. Neither -> potential hallucination
    """
    anchored = False
    anchor_in = None
    matched_key = None
    value_str = str(claim["value"])
    for key in claim["nearby_cite_keys"]:
        # Prefer full text
        fulltext = load_fulltext_for_key(key, task_dir)
        if fulltext and value_str in fulltext:
            anchored = True
            anchor_in = f"fulltext:{key}"
            matched_key = key
            break
    if not anchored:
        # Fallback: retrieval_log summary
        for key in claim["nearby_cite_keys"]:
            for rec in read_log(task_dir):
                summary = rec.get("extra", {}).get("summary", "") or rec.get("summary", "")
                if summary and value_str in summary:
                    anchored = True
                    anchor_in = f"summary:{rec.get('source_id', '')}"
                    matched_key = key
                    break
            if anchored:
                break
    if not anchored:
        # Fallback: raw_results.jsonl metrics (anti-hallucination v3 — solid evidence chain).
        # A numerical claim is anchored if its value matches any metric in any trial,
        # supporting both decimal (0.9197) and percentage (91.97) forms.
        raw_path = task_dir / "paper" / "raw_results.jsonl"
        if raw_path.exists():
            for raw_line in raw_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not raw_line.strip():
                    continue
                try:
                    rec = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                for m_val in rec.get("metrics", {}).values():
                    if m_val is None:
                        continue
                    if value_str == str(m_val):
                        anchored = True
                        anchor_in = f"raw_results:{rec.get('trial_id', '')}"
                        matched_key = rec.get("cite_key", "")
                        break
                    try:
                        mv = float(m_val)
                        vs = float(value_str)
                        # Match decimal (0.9197) to percentage (91.97) and vice versa
                        if abs(mv * 100 - vs) < 0.01 or abs(mv - vs) < 0.0001:
                            anchored = True
                            anchor_in = f"raw_results:{rec.get('trial_id', '')}"
                            matched_key = rec.get("cite_key", "")
                            break
                    except (ValueError, TypeError):
                        pass
                if anchored:
                    break
    claim["anchored"] = anchored
    claim["anchor_in"] = anchor_in
    claim["matched_cite_key"] = matched_key
    return claim


def main() -> None:
    parser = argparse.ArgumentParser(description="Check section numerical claim anchors (anti-hallucination v2)")
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--sections-dir", type=Path, default=None,
                        help="default task_dir/paper/sections")
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    sections_dir = args.sections_dir or (args.task_dir / "paper" / "sections")
    claims = scan_sections(sections_dir)
    anchored_claims = [anchor_claim(c, args.task_dir) for c in claims]
    unanchored = [c for c in anchored_claims if not c["anchored"]]
    summary = {
        "total_claims": len(anchored_claims),
        "anchored": len(anchored_claims) - len(unanchored),
        "unanchored": len(unanchored),
        "anchor_rate": round((len(anchored_claims) - len(unanchored)) / len(anchored_claims), 3)
                       if anchored_claims else 0.0,
        "unanchored_claims": unanchored,
    }
    out = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    print(out)
    # Exit code: 1 if there are unanchored claims
    raise SystemExit(0 if not unanchored else 1)


if __name__ == "__main__":
    main()
