#!/usr/bin/env python3
"""LQS (Literature Quality Score) for citation candidates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def score_recency(year: int, month: int = 6) -> float:
    now = datetime.now()
    age_months = (now.year - year) * 12 + (now.month - month)
    if age_months <= 6:
        return 10.0
    if age_months <= 12:
        return 8.0
    if age_months <= 24:
        return 5.0
    if age_months <= 36:
        return 3.0
    return 1.0


def score_citation_impact(cites_per_month: float) -> float:
    if cites_per_month >= 50:
        return 10.0
    if cites_per_month >= 10:
        return 8.0
    if cites_per_month >= 3:
        return 6.0
    if cites_per_month >= 1:
        return 4.0
    return 2.0


def score_venue(venue_tier: str) -> float:
    tiers = {"top": 10.0, "strong": 7.0, "workshop": 4.0, "arxiv": 3.0, "unknown": 2.0}
    return tiers.get(venue_tier.lower(), 2.0)


def score_institution(tier: str) -> float:
    tiers = {"top_lab": 10.0, "top_uni": 9.0, "strong": 7.0, "other": 5.0}
    return tiers.get(tier.lower(), 5.0)


def score_acceptance(status: str) -> float:
    statuses = {"accepted": 10.0, "under_review": 5.0, "none": 3.0}
    return statuses.get(status.lower(), 3.0)


def compute_lqs(paper: dict) -> float:
    recency = score_recency(int(paper.get("year", 2020)), int(paper.get("month", 6)))
    cites = score_citation_impact(float(paper.get("cites_per_month", 0)))
    venue = score_venue(paper.get("venue_tier", "unknown"))
    inst = score_institution(paper.get("institution_tier", "other"))
    accept = score_acceptance(paper.get("acceptance", "none"))
    return round(0.30 * recency + 0.25 * cites + 0.20 * venue + 0.10 * inst + 0.15 * accept, 2)


def classify_lqs(lqs: float) -> str:
    if lqs >= 7.0:
        return "must_cite"
    if lqs >= 5.0:
        return "conditional"
    return "drop"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="JSON array of paper metadata")
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    papers = json.loads(args.input.read_text(encoding="utf-8"))
    scored = []
    for p in papers:
        lqs = compute_lqs(p)
        scored.append({**p, "lqs": lqs, "lqs_class": classify_lqs(lqs)})
    scored.sort(key=lambda x: x["lqs"], reverse=True)
    out = json.dumps(scored, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
        print(f"Scored {len(scored)} papers → {args.output}")
    else:
        print(out)


if __name__ == "__main__":
    main()
