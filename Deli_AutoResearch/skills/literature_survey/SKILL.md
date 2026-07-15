---
name: literature_survey
description: Stage 1-4 literature pipeline — recall, LQS score, A/B/C/D classify, venue upgrade. Outputs references.bib and citation_plan.jsonl. (anti-hallucination v2)
parent: paper-writing
---

# Literature Survey (anti-hallucination v2)

**IN:** `state/task_spec.md` (topic, taxonomy keywords)
**OUT:** `paper/references.bib`, `paper/citation_plan.jsonl`, `paper/retrieval_log.jsonl`

## Core Principles (anti-hallucination iron rules)

> **Any bib entry must have a corresponding API call anchor in `paper/retrieval_log.jsonl`. Entries without an anchor are considered fabricated, blocked by Gate 1.5, and the task cannot proceed.**

The LLM's responsibilities are compressed to three things:
1. Write query terms
2. Score candidates with LQS
3. Mark A/B/C/D citation depth

**LLM strictly forbidden**: directly editing `references.bib`, "filling in" authors/volume/issue/page/DOI from memory, rewriting arXiv preprints as `@inproceedings`.

## Pipeline

### Stage 1 — High-recall retrieval (mandatory real API)

Four parallel entry points, covering all citation types:

```bash
# 1. arXiv preprints (main entry)
python tools/search_arxiv.py 'all:"YOUR TOPIC"' -n 50 -o paper/literature_raw_arxiv.json --task-dir tasks/<slug>

# 2. CrossRef journals/conferences (anti-hallucination key — replaces old "LLM fills in fields from memory")
python tools/search_crossref.py --task-dir tasks/<slug> --title "YOUR TOPIC" -n 30 -o paper/literature_raw_crossref.json

# 3. DBLP CS conferences (for venue upgrade)
python tools/search_dblp.py --task-dir tasks/<slug> "YOUR TOPIC" -n 30 -o paper/literature_raw_dblp.json

# 4. Semantic Scholar (citation count, for LQS scoring)
python tools/search_semantic_scholar.py --task-dir tasks/<slug> "YOUR TOPIC" -n 20 -o paper/literature_raw_s2.json
```

- 20–30 keyword variants per taxonomy cell, each runs 4 APIs
- Snowball: citation network of seed paper
- Target: 200–500 raw candidates
- Each API call automatically writes to `paper/retrieval_log.jsonl` — this is the anchor for subsequent Gate 1.5

### Stage 2 — LQS scoring

Prepare JSON with fields: `year`, `month`, `cites_per_month` (from S2), `venue_tier`, `institution_tier`, `acceptance`
```bash
python tools/lqs_score.py paper/literature_raw_*.json -o paper/literature_scored.json
```
- LQS ≥ 7.0 → must_cite; 5.0–7.0 conditional; < 5.0 drop

### Stage 3 — Citation depth (citation_plan.jsonl)

One JSON object per line:
```json
{"key":"author2024title","depth":"A","section":"03_methods","source_id":"doi:10.xxx/yyy","rationale":"..."}
```
- A: 1–3 paragraphs (3–5 per chapter); B: 2–5 sentences; C: 1 sentence; D: drop
- **New**: `source_id` field is mandatory, must correspond to the anchor in retrieval_log

### Stage 4 — Venue upgrade (mandatory DBLP verification)

The old version let the LLM "from memory" rewrite arXiv as `@inproceedings` — this was one source of 13 fabricated citations.

New version:
1. LLM can only "mark" `arxiv_id → should upgrade to inproceedings`
2. The upgrade action must go through real DBLP matching:
   ```bash
   python tools/search_dblp.py --task-dir tasks/<slug> --doi 10.xxx/yyy
   ```
3. The `booktitle` / `pages` / `year` returned by DBLP are the only fields written to bib; the LLM must not modify them
4. DBLP lookup fails → keep `@article` + `eprint`, **must not upgrade**

### Verification (mandatory every 20 entries, anti-hallucination v2)

```bash
# Verify + automatically fill in retrieval_log anchor (if verification passes)
python tools/verify_citations.py tasks/<slug> --batch-size 20 -o paper/verify_report.json
```

verify_citations.py now supports three-way dispatch: DOI (CrossRef) > arXiv > title (CrossRef + DBLP fallback).
Failed entries = hallucination candidates, must be replaced.

## Gate 1 / 1.5 / 1.6 targets

| Gate | Check | Threshold |
|------|------|------|
| 1 literature | number of citations | ≥ 80 (draft) / ≥ pages×3 (final) |
| 1 literature | arXiv-only ratio | ≤ 0.60 |
| 1 literature | verification rate | ≥ 80% |
| **1.5 retrieval_provenance** | **bib orphans (no anchor)** | **= 0 (strict)** |
| **1.6 numerical_claims** | **section numerical claim anchoring rate** | **= 100% (strict)** |

## Finding record

Append to `state/findings.jsonl` with `citations_added`, `verification_rate`, `arxiv_ratio`, `orphans_count`, `unanchored_claims_count`.

## LLM Responsibility Matrix (anti-hallucination iron rules)

| Stage | LLM can do | LLM cannot do |
|------|------|------|
| Stage 1 retrieval | write query terms | directly edit references.bib |
| Stage 1 retrieval | run 4 search_*.py | "fill in" a new entry from memory |
| Stage 2 LQS | score candidates | modify fields returned by API |
| Stage 3 classification | mark A/B/C/D | rewrite author/title fields |
| Stage 4 upgrade | mark "should upgrade to inproceedings" | change `@article → @inproceedings` itself |
| Section writing | cite cite_key | write specific values like "SI 58.6%" from impression (unless anchorable in the summary of retrieval_log) |
