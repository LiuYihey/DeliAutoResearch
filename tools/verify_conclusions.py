#!/usr/bin/env python3
"""Verify whether the paper's conclusion is based on real evidence (anti-hallucination v3 — solid).

Why this tool is needed:
- The conclusion is the final output of the paper and must be held to the strictest standard
- A hallucination pattern observed in practice: the LLM writes from memory in the conclusion things like "X% improvement" / "our method outperforms all baselines"
- These claims must be traceable to:
  a) raw_results.jsonl from self-run experiments (own experimental data)
  b) or the fulltext of cited papers (when citing others' conclusions)

Workflow:
1. Scan the conclusion section and extract all claim sentences
2. Classify: numerical claim / comparison claim / summary claim
3. For each claim, check whether it can be anchored in the evidence:
   - Numerical claim (X% improvement) → must appear in raw_results.jsonl
   - Comparison claim (outperforms Y) → must have raw_results comparison data
   - Summary claim (proposed a novel method) → must have a description in the method section
4. Any unanchored conclusion claim = potential hallucination, blocks Gate 1.8
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_numerical_claims import NUM_PATTERNS  # noqa: E402
from check_factual_claims import load_fulltext_for_key, VERB_RE, CITE_RE, CITEP_RE, extract_keywords  # noqa: E402

# Comparison claim patterns
COMPARE_PATTERNS = [
    (re.compile(r"\boutperform[s]?\b", re.IGNORECASE), "outperform"),
    (re.compile(r"\bsuperior\s+to\b", re.IGNORECASE), "superior_to"),
    (re.compile(r"\bbetter\s+than\b", re.IGNORECASE), "better_than"),
    (re.compile(r"\bexceed[s]?\b", re.IGNORECASE), "exceed"),
    (re.compile(r"\bstate-of-the-art\b", re.IGNORECASE), "sota"),
    (re.compile(r"\bimprove[s]?\s+(by|over|upon)\b", re.IGNORECASE), "improve"),
]

# Summary claim patterns
SUMMARY_PATTERNS = [
    (re.compile(r"\bwe\s+(propose|present|introduce|develop)\b", re.IGNORECASE), "we_propose"),
    (re.compile(r"\bour\s+(method|approach|framework)\b", re.IGNORECASE), "our_method"),
    (re.compile(r"\bin\s+(this|our)\s+(paper|work|study)\b", re.IGNORECASE), "in_this_paper"),
]


def load_raw_results(task_dir: Path) -> list[dict]:
    """Load self-run experiment results."""
    out = []
    for fname in ("raw_results.jsonl", "results.jsonl", "experiments.jsonl"):
        p = task_dir / "paper" / fname
        if not p.exists():
            p = task_dir / "experiments" / fname
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def extract_claims_from_conclusion(tex_path: Path) -> list[dict]:
    """Extract all claims from the conclusion section."""
    text = tex_path.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE)
    claims = []
    for line_no, line in enumerate(text.splitlines(), 1):
        # Numerical claims
        for pat, kind in NUM_PATTERNS:
            for m in pat.finditer(line):
                value = m.group(1)
                if kind == "mean_pm_std":
                    value = f"{m.group(1)}±{m.group(2)}"
                ctx_start = max(0, m.start() - 60)
                ctx_end = min(len(line), m.end() + 60)
                claims.append({
                    "file": str(tex_path), "line": line_no,
                    "claim_type": "numerical", "value": str(value),
                    "context": line[ctx_start:ctx_end].strip(),
                    "nearby_cite_keys": [k.strip() for c in (CITE_RE.findall(line) + CITEP_RE.findall(line))
                                          for k in c.split(",")],
                })
        # Comparison claims
        for pat, kind in COMPARE_PATTERNS:
            for m in pat.finditer(line):
                ctx_start = max(0, m.start() - 80)
                ctx_end = min(len(line), m.end() + 80)
                claims.append({
                    "file": str(tex_path), "line": line_no,
                    "claim_type": "comparison", "value": kind,
                    "context": line[ctx_start:ctx_end].strip(),
                    "nearby_cite_keys": [k.strip() for c in (CITE_RE.findall(line) + CITEP_RE.findall(line))
                                          for k in c.split(",")],
                })
        # Summary claims
        for pat, kind in SUMMARY_PATTERNS:
            for m in pat.finditer(line):
                ctx_start = max(0, m.start() - 60)
                ctx_end = min(len(line), m.end() + 80)
                claims.append({
                    "file": str(tex_path), "line": line_no,
                    "claim_type": "summary", "value": kind,
                    "context": line[ctx_start:ctx_end].strip(),
                    "nearby_cite_keys": [k.strip() for c in (CITE_RE.findall(line) + CITEP_RE.findall(line))
                                          for k in c.split(",")],
                })
    return claims


def anchor_conclusion_claim(claim: dict, task_dir: Path, raw_results: list[dict]) -> dict:
    """Anchor a conclusion claim to evidence."""
    anchored = False
    anchor_in = None
    anchor_kind = None

    if claim["claim_type"] == "numerical":
        # Numerical claim: must be in raw_results or fulltext
        value_str = str(claim["value"])
        # Check raw_results first
        for r in raw_results:
            r_text = json.dumps(r, ensure_ascii=False).lower()
            if value_str in r_text:
                anchored = True
                anchor_in = "raw_results"
                anchor_kind = "self_run_data"
                break
        if not anchored:
            # Fall back to cited paper fulltext
            for key in claim["nearby_cite_keys"]:
                ft = load_fulltext_for_key(key, task_dir)
                if ft and value_str in ft:
                    anchored = True
                    anchor_in = f"fulltext:{key}"
                    anchor_kind = "cited_paper"
                    break
    elif claim["claim_type"] == "comparison":
        # Comparison claim: must have raw_results data containing at least 2 methods for comparison
        if len(raw_results) >= 2:
            anchored = True
            anchor_in = "raw_results"
            anchor_kind = "self_run_comparison"
        # When citing others' conclusions: find keywords like "outperform" in fulltext
        if not anchored:
            for key in claim["nearby_cite_keys"]:
                ft = load_fulltext_for_key(key, task_dir)
                if ft:
                    ft_lower = ft.lower()
                    if any(p[0].search(ft_lower) for p in COMPARE_PATTERNS):
                        anchored = True
                        anchor_in = f"fulltext:{key}"
                        anchor_kind = "cited_paper"
                        break
    elif claim["claim_type"] == "summary":
        # Summary claim: must have a concrete description in method/05_method.tex or similar locations
        sections_dir = task_dir / "paper" / "sections"
        if sections_dir.exists():
            keywords = extract_keywords(claim["context"])
            for tex in sections_dir.glob("*.tex"):
                if "conclusion" in tex.name.lower():
                    continue  # Do not anchor conclusion within the conclusion itself
                ft = tex.read_text(encoding="utf-8", errors="ignore").lower()
                hits = [k for k in keywords if k in ft]
                ratio = len(hits) / max(len(keywords), 1)
                if ratio >= 0.6:
                    anchored = True
                    anchor_in = f"section:{tex.name}"
                    anchor_kind = "method_description"
                    break

    claim["anchored"] = anchored
    claim["anchor_in"] = anchor_in
    claim["anchor_kind"] = anchor_kind
    return claim


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify conclusion claim traceability (anti-hallucination v3)")
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--sections-dir", type=Path, default=None)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    sections_dir = args.sections_dir or (args.task_dir / "paper" / "sections")
    # Find the conclusion section
    conclusion_files = [f for f in sections_dir.glob("*.tex") if "conclusion" in f.name.lower()
                        or "06" in f.name or "07" in f.name]
    if not conclusion_files:
        print(json.dumps({"passed": True, "reason": "no_conclusion_section"}, indent=2, ensure_ascii=False))
        return
    raw_results = load_raw_results(args.task_dir)
    all_claims = []
    for f in conclusion_files:
        all_claims.extend(extract_claims_from_conclusion(f))
    anchored = [anchor_conclusion_claim(c, args.task_dir, raw_results) for c in all_claims]
    unanchored = [c for c in anchored if not c["anchored"]]
    summary = {
        "total_claims": len(anchored),
        "anchored": len(anchored) - len(unanchored),
        "unanchored": len(unanchored),
        "anchor_rate": round((len(anchored) - len(unanchored)) / len(anchored), 3) if anchored else 0.0,
        "raw_results_count": len(raw_results),
        "conclusion_files": [str(f) for f in conclusion_files],
        "unanchored_claims": unanchored,
    }
    out = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    print(out)
    raise SystemExit(0 if not unanchored else 1)


if __name__ == "__main__":
    main()
