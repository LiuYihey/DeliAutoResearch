---
name: experiment_design
description: Pre-registered experiments supporting paper claims. Outputs results.json and experiment_summary.md. (anti-hallucination v3 — solid data)
parent: paper-writing
---

# Experiment Design (anti-hallucination v3 — solid data)

**IN:** gap from structure or review weakness
**OUT:** `paper/experiment_spec.json`, `paper/results.json`, `paper/raw_results.jsonl`, `paper/experiment_summary.md`

## Core principles (anti-hallucination iron rules — solid data)

> **Any experiment data referenced by a paper section must be traceable line by line to the original run results in `paper/raw_results.jsonl`. The LLM must not "supplement" in the section any numbers that do not appear in raw_results.**

raw_results.jsonl format (one trial per line):
```json
{"trial_id":"t1","config":{"model":"gpt-4o","task":"math"},"metrics":{"acc":0.82,"latency_ms":1240},"ts":"2026-07-07T10:00:00Z","raw_log":"logs/t1.json"}
```

## Stage 1 — Design (before any run)
Fill `paper/experiment_spec.json`:
- hypothesis, supports_claim, IV/DV/controls, statistical_plan, path (`api` | `gpu`)

Must answer: **which paper claim does this support?**
**(anti-hallucination v3)** Must explicitly list `expected_quote_anchor` (which statement in the paper section will be supported by this experiment)

## Stage 2 — Execute

| Path | Command / action |
|------|------------------|
| API | `tools/call_api.py` or agent API; 3–5 models × 2–3 conditions × 15–25 tasks × 3 trials |
| GPU | Submit cluster job; use Pattern C polling |

Set `AUTORESEARCH_API_KEY` and optional `AUTORESEARCH_MODEL`.

**(anti-hallucination v3)** Each trial must:
1. Write a raw_results.jsonl record (containing trial_id, config, metrics, ts, raw_log path)
2. raw_log must point to the complete prompt/response log, must not be lost

## Stage 3 — Iterate (max 5)
Ceiling → harder tasks; floor → debug; not significant → more trials; surprise → follow-up

## Stage 4 — Report only data
`results.json` schema:
```json
{"config":{}, "results":[], "statistics":{}, "findings":[], "trials":3, "raw_results_file":"raw_results.jsonl"}
```
Do NOT write LaTeX tables here — figures_tables skill handles presentation.

## Gate 2 (anti-hallucination v3 upgrade)
- Pre-registered spec, ≥3 trials, statistical test, links to claim
- **(New)** raw_results.jsonl exists and the trial count is consistent with the trials in results.json
- **(New)** Every number in results.json must be obtainable by aggregating raw_results.jsonl
- **(New)** Experiment numbers referenced in a section must be findable in results.json (verified by Gate 1.8)

Use `Deli_AutoResearch/prompts/pattern_c_experiment.md` for long runs.
