#!/usr/bin/env python3
"""OpenAI-compatible API helper for peer review and API experiments."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path


def chat_completion(
    messages: list[dict],
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.3,
) -> str:
    api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AUTORESEARCH_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENAI_API_KEY or AUTORESEARCH_API_KEY")
    base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = model or os.environ.get("AUTORESEARCH_MODEL", "gpt-4o")

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def run_peer_review(pdf_summary: str, personas: int = 3, evidence_pack: str | None = None) -> dict:
    """Run multi-persona peer review.

    evidence_pack: optional text appended to the prompt that lists grounded
    evidence (fulltext quotes + raw_results trial_ids). When provided, the
    reviewer is instructed to anchor every weakness to a specific quote or
    trial_id — preventing the reviewer itself from hallucinating claims
    about the paper. When None, the reviewer is told to mark any weakness
    it cannot anchor with a quote as "unverified — do not promote".
    """
    persona_names = ["Experimentalist", "Theorist", "Perfectionist", "Synthesizer", "Newcomer"]
    reviews = []
    for i in range(min(personas, len(persona_names))):
        name = persona_names[i]
        grounding_clause = (
            "You MUST cite a specific paragraph from the paper or a fulltext quote.\n"
            "Any weakness you cannot anchor to a quote or trial_id MUST be flagged "
            "'unverified — do not promote'.\n\nEvidence pack (verified quotes + raw trial ids):\n"
            f"{evidence_pack}\n"
            if evidence_pack
            else "No evidence pack provided — for any weakness, state 'unverified — no fulltext quote available'. "
            "Do NOT invent specifics; reviewers that hallucinate are rejected."
        )
        prompt = f"""You are Reviewer {name} for a survey paper. Score 1-10 on: Novelty, Comprehensiveness, Clarity, Technical Depth, Experimental Validation.

{grounding_clause}

Return JSON only: {{"persona":"{name}","overall":float,"dimensions":{{}},"strengths":[],"weaknesses":[
  {{"issue":"...","evidence_type":"fulltext_quote|raw_trial|paper_paragraph","cite_key":"...","quote":"...","trial_id":"...","verified":true/false}}
],"recommendation":"..."}}

Paper summary:
{pdf_summary}
"""
        raw = chat_completion([{"role": "user", "content": prompt}])
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            reviews.append(json.loads(raw[start:end]))
        except json.JSONDecodeError:
            reviews.append({"persona": name, "raw": raw})

    scores = [r.get("overall", 0) for r in reviews if isinstance(r.get("overall"), (int, float))]
    median = sorted(scores)[len(scores) // 2] if scores else 0.0
    # Drop reviews where any weakness has verified=false (reviewer self-hallucination)
    valid_reviews = []
    dropped = []
    for r in reviews:
        weaknesses = r.get("weaknesses", []) if isinstance(r, dict) else []
        unverified = [w for w in weaknesses if isinstance(w, dict) and w.get("verified") is False]
        if unverified and not evidence_pack:
            dropped.append({"persona": r.get("persona"), "reason": "unverified_weaknesses_no_evidence_pack"})
        else:
            valid_reviews.append(r)
    return {
        "reviews": valid_reviews,
        "dropped_reviews": dropped,
        "median_score": median,
        "evidence_pack_provided": evidence_pack is not None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-file", type=Path, required=True, help="Text summary of paper for review")
    parser.add_argument("--personas", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument(
        "--evidence", type=Path, default=None,
        help="Optional path to evidence pack (text file of grounded quotes + trial_ids). "
             "When provided, reviewer must anchor every weakness to a quote/trial_id.",
    )
    args = parser.parse_args()
    summary = args.summary_file.read_text(encoding="utf-8")
    evidence = args.evidence.read_text(encoding="utf-8") if args.evidence else None
    result = run_peer_review(summary, args.personas, evidence)
    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
