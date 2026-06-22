---
name: literature_survey
description: Stage 1-4 literature pipeline — recall, LQS score, A/B/C/D classify, venue upgrade. Outputs references.bib and citation_plan.jsonl.
parent: paper-writing
---

# Literature Survey

**IN:** `state/task_spec.md` (topic, taxonomy keywords)  
**OUT:** `paper/references.bib`, `paper/citation_plan.jsonl`

## Pipeline

### Stage 1 — High-recall retrieval
```bash
python tools/search_arxiv.py 'all:"YOUR TOPIC"' -n 50 -o paper/literature_raw.json
```
- 20–30 keyword variants per taxonomy cell
- Snowball from seed papers
- Target: 200–500 raw candidates (run multiple queries, merge JSON)

### Stage 2 — LQS scoring
Prepare JSON with fields: `year`, `month`, `cites_per_month`, `venue_tier`, `institution_tier`, `acceptance`
```bash
python tools/lqs_score.py paper/literature_raw.json -o paper/literature_scored.json
```
- LQS ≥ 7.0 → must_cite; 5.0–7.0 conditional; < 5.0 drop

### Stage 3 — Citation depth (citation_plan.jsonl)
One JSON object per line:
```json
{"key":"author2024title","depth":"A","section":"03_methods","rationale":"..."}
```
- A: 1–3 paragraphs (3–5 per chapter); B: 2–5 sentences; C: 1 sentence; D: drop

### Stage 4 — Venue upgrade
- Cross-check DBLP / OpenReview where possible
- arXiv with acceptance note → `@inproceedings`
- Target: arXiv-only ≤ 60%

### Verification (every 20 entries)
```bash
python tools/verify_citations.py paper/bib_batch.json -o paper/verify_report.json
```

## Gate 1 targets
- Citations ≥ 80 (draft) / ≥ pages×3 (final)
- Within-1yr ≥ 40%; accepted ≥ 30%; verification ≥ 80%

## Finding record
Append to `state/findings.jsonl` with `citations_added`, `verification_rate`, `arxiv_ratio`.
