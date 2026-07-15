#!/usr/bin/env python3
"""Scan factual claims in sections and anchor them to paper full text (anti-hallucination v3 — solid evidence).

Why this tool is needed:
- check_numerical_claims.py only checks numbers (58.6%, N=24)
- but sections also contain many textual factual claims:
  "X et al. proposed a CNN-GRU hybrid"
  "Z introduced the XYZ benchmark dataset"
  "Y demonstrated that ..."
- These claims must be quote-matchable against original text in the fulltext of the corresponding cite_key
- Otherwise = LLM writing facts from impression = potential hallucination

Factual claim patterns (core verbs):
- proposed / introduced / presented / developed
- demonstrated / showed / proved / verified
- achieved / obtained / reached
- used / employed / applied
- found / observed / reported
- extended / generalized

Workflow:
1. Scan sections/*.tex, find factual claim sentences near cite commands
2. For each cite_key, load fulltext/<cite_key>.txt
3. Extract the sentence core (subject+verb+object keywords), fuzzy-match in full text
4. Unanchored = potential hallucination, blocks Gate 1.7
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_log import read_log  # noqa: E402

# Factual claim verbs
FACTUAL_VERBS = [
    "proposed", "introduced", "presented", "developed", "designed",
    "demonstrated", "showed", "proved", "verified", "confirmed",
    "achieved", "obtained", "reached", "reported",
    "used", "employed", "applied", "adopted",
    "found", "observed", "discovered", "identified",
    "extended", "generalized", "modified", "improved",
    "built", "constructed", "formulated", "established",
]
VERB_RE = re.compile(r"\b(" + "|".join(FACTUAL_VERBS) + r")\b", re.IGNORECASE)

# Sentence boundary
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# cite command
CITE_RE = re.compile(r"\\cite\{([^}]+)\}")
CITEP_RE = re.compile(r"\\cite[p]?\{([^}]+)\}")


def split_sentences(text: str) -> list[str]:
    """Simple sentence splitting."""
    sents = SENTENCE_END_RE.split(text)
    return [s.strip() for s in sents if s.strip()]


def extract_factual_claims_from_tex(tex_path: Path) -> list[dict]:
    """Extract factual claims from a LaTeX file."""
    text = tex_path.read_text(encoding="utf-8", errors="ignore")
    # Remove comments
    text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE)
    claims = []
    for line_no, line in enumerate(text.splitlines(), 1):
        # Find sentences containing cite and factual verbs
        cites = CITE_RE.findall(line) + CITEP_RE.findall(line)
        if not cites:
            continue
        cite_keys = []
        for c in cites:
            cite_keys.extend([k.strip() for k in c.split(",")])
        if not any(VERB_RE.search(line) for _ in [1]):
            continue
        # Extract all factual claims in this line
        for verb_m in VERB_RE.finditer(line):
            verb = verb_m.group(1).lower()
            # Take 80 chars before/after verb as claim snippet
            ctx_start = max(0, verb_m.start() - 80)
            ctx_end = min(len(line), verb_m.end() + 80)
            context = line[ctx_start:ctx_end].strip()
            # Extract keywords (remove stop words, keep content words)
            keywords = extract_keywords(context)
            claims.append({
                "file": str(tex_path),
                "line": line_no,
                "verb": verb,
                "context": context,
                "keywords": keywords,
                "nearby_cite_keys": cite_keys,
            })
    return claims


STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "by", "as", "at", "from", "this", "that", "these", "those",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "can", "their", "his", "her", "its", "our", "your",
    "they", "them", "he", "she", "it", "we", "you", "i",
    "et", "al", "cite", "ref", "fig", "table", "section",
    "which", "who", "whom", "whose", "what", "where", "when", "how",
    "than", "then", "such", "so", "if", "because", "while", "although",
    "however", "therefore", "moreover", "furthermore", "thus",
}


def extract_keywords(text: str) -> list[str]:
    """Extract content-word keywords (for full-text matching)."""
    # Remove LaTeX commands
    text = re.sub(r"\\[a-zA-Z]+(\[[^\]]*\])?\{([^}]*)\}", r"\2", text)
    text = re.sub(r"\\[a-zA-Z]+", " ", text)
    # Remove punctuation
    text = re.sub(r"[^a-zA-Z0-9\s-]", " ", text)
    words = text.split()
    keywords = []
    for w in words:
        wl = w.lower()
        if wl in STOP_WORDS:
            continue
        if len(wl) < 4:
            continue
        # Remove -ing -ed -s etc.
        stem = re.sub(r"(ing|ed|s|es|ment|tion|ity)$", "", wl)
        if len(stem) < 3:
            continue
        keywords.append(stem)
    # Deduplicate, take first 8
    seen = set()
    out = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            out.append(k)
        if len(out) >= 8:
            break
    return out


def load_fulltext_for_key(cite_key: str, task_dir: Path) -> str | None:
    """Load the full text from paper/fulltext/<cite_key>.txt."""
    p = task_dir / "paper" / "fulltext" / f"{cite_key}.txt"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore")
    return None


def load_summary_for_key(cite_key: str, task_dir: Path) -> str | None:
    """Get summary from retrieval_log (fallback when full text is missing)."""
    for rec in read_log(task_dir):
        summary = rec.get("extra", {}).get("summary", "")
        if summary:
            return summary
    return None


def anchor_factual_claim(claim: dict, task_dir: Path) -> dict:
    """Anchor a factual claim in the full text corresponding to cite_key.

    Matching strategy (strict to loose):
    1. Strict: all keywords appear in full text
    2. Moderate: >= 70% keywords appear
    3. Loose: core verb + >= 50% keywords appear
    4. Failed: < 50% keywords appear -> potential hallucination
    """
    anchored = False
    anchor_in = None
    matched_key = None
    match_strength = "none"
    for key in claim["nearby_cite_keys"]:
        fulltext = load_fulltext_for_key(key, task_dir)
        if not fulltext:
            # Fallback: use summary
            fulltext = load_summary_for_key(key, task_dir) or ""
            source_kind = "summary"
        else:
            source_kind = "fulltext"
        if not fulltext:
            continue
        # Lowercase full text
        ft_lower = fulltext.lower()
        # Check whether each keyword appears
        kw_hits = [k for k in claim["keywords"] if k in ft_lower]
        ratio = len(kw_hits) / max(len(claim["keywords"]), 1)
        verb_in_text = claim["verb"] in ft_lower
        if ratio == 1.0 and verb_in_text:
            anchored = True
            match_strength = "strict"
        elif ratio >= 0.7 and verb_in_text:
            anchored = True
            match_strength = "moderate"
        elif ratio >= 0.5 and verb_in_text:
            anchored = True
            match_strength = "loose"
        if anchored:
            anchor_in = f"{source_kind}:{key}"
            matched_key = key
            break
    claim["anchored"] = anchored
    claim["anchor_in"] = anchor_in
    claim["matched_cite_key"] = matched_key
    claim["match_strength"] = match_strength
    return claim


def scan_sections(sections_dir: Path) -> list[dict]:
    if not sections_dir.exists():
        return []
    claims = []
    for tex in sorted(sections_dir.glob("*.tex")):
        claims.extend(extract_factual_claims_from_tex(tex))
    return claims


def main() -> None:
    parser = argparse.ArgumentParser(description="Check factual claim anchoring (anti-hallucination v3)")
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--sections-dir", type=Path, default=None)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    sections_dir = args.sections_dir or (args.task_dir / "paper" / "sections")
    claims = scan_sections(sections_dir)
    anchored = [anchor_factual_claim(c, args.task_dir) for c in claims]
    # Strict: only accept strict / moderate, loose counts as unanchored
    strict_ok = [c for c in anchored if c.get("match_strength") in ("strict", "moderate")]
    unanchored = [c for c in anchored if c.get("match_strength") in ("loose", "none")]
    summary = {
        "total_claims": len(anchored),
        "strict_anchored": len(strict_ok),
        "unanchored": len(unanchored),
        "anchor_rate": round(len(strict_ok) / len(anchored), 3) if anchored else 0.0,
        "unanchored_claims": unanchored,
    }
    out = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    print(out)
    raise SystemExit(0 if not unanchored else 1)


if __name__ == "__main__":
    main()
