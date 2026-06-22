---
name: experiment_design
description: Pre-registered experiments supporting paper claims. Outputs results.json and experiment_summary.md.
parent: paper-writing
---

# Experiment Design

**IN:** gap from structure or review weakness  
**OUT:** `paper/experiment_spec.json`, `paper/results.json`, `paper/experiment_summary.md`

## Stage 1 — Design (before any run)
Fill `paper/experiment_spec.json`:
- hypothesis, supports_claim, IV/DV/controls, statistical_plan, path (`api` | `gpu`)

Must answer: **which paper claim does this support?**

## Stage 2 — Execute

| Path | Command / action |
|------|------------------|
| API | `tools/call_api.py` or agent API; 3–5 models × 2–3 conditions × 15–25 tasks × 3 trials |
| GPU | Submit cluster job; use Pattern C polling |

Set `AUTORESEARCH_API_KEY` and optional `AUTORESEARCH_MODEL`.

## Stage 3 — Iterate (max 5)
Ceiling → harder tasks; floor → debug; not significant → more trials; surprise → follow-up

## Stage 4 — Report only data
`results.json` schema:
```json
{"config":{}, "results":[], "statistics":{}, "findings":[], "trials":3}
```
Do NOT write LaTeX tables here — figures_tables skill handles presentation.

## Gate 2
- Pre-registered spec, ≥3 trials, statistical test, links to claim

Use `Deli_AutoResearch/prompts/pattern_c_experiment.md` for long runs.
