# Pattern C — Experiment Run (long compute)

Use for GPU jobs or long API sweeps (experiment_design skill).

## After submit

1. Write `paper/experiment_spec.json` BEFORE running (pre-registration)
   - Each trial must declare `expected_quote_anchor` (fulltext cite_key or "self_run")
2. Start minute-level polling loop until complete or 4h cap
3. On error: diagnose log → fix → resubmit (max 5 iterations)
4. Output:
   - `paper/raw_results.jsonl` (MANDATORY — one JSON line per trial, append-only):
     ```json
     {"trial_id":"t1","config":{...},"metrics":{...},"ts":"2026-07-07T12:00:00Z",
      "raw_output":"...","expected_quote_anchor":"self_run|<cite_key>"}
     ```
   - `paper/results.json` (aggregated from raw_results.jsonl, NOT from LLM memory)
   - `paper/experiment_summary.md` (narrative derived from raw_results.jsonl)
5. Verify before exit (HARD-BLOCKING):
   - python tools/check_gates.py {{TASK_DIR}}  (Gate 2 + Gate 1.8 must pass)
   - Gate 1.8 conclusion_grounding: results.json trial count must match raw_results.jsonl
   - Every numerical citation must be traceable in raw_results.jsonl by trial_id.

## Polling prompt

```
Zero interaction. TASK_DIR={{TASK_DIR}}.
Poll experiment job status every 60s. On failure: read stderr, patch, resubmit.
On success:
1. Append each trial to paper/raw_results.jsonl (one line per trial):
   {"trial_id":"t1","config":{...},"metrics":{...},"ts":"...","expected_quote_anchor":"self_run"}
2. Aggregate into paper/results.json schema {config, results, statistics, findings, trials}.
   The trials count MUST equal len(raw_results.jsonl lines).
3. Write paper/experiment_summary.md (narrative derived from raw_results, NOT from memory).
4. python tools/verify_conclusions.py {{TASK_DIR}}  (conclusion must trace to raw_results).
5. python tools/check_gates.py {{TASK_DIR}}  (Gate 2 + Gate 1.8 are HARD-BLOCKING).
6. python tools/update_progress.py {{TASK_DIR}} --source work --event experiment_complete
```

## Anti-hallucination iron rules (experiment_design)

- The LLM must never write experimental numbers from memory. Every metric must come from a trial_id in raw_results.jsonl.
- The LLM must never describe baselines from memory. Baseline numbers must also be in raw_results.jsonl (use source: "baseline_run").
- The statistics field in results.json (mean / std / p-value) must be recomputed from raw_results.jsonl; do NOT hand-fill it.
- Experimental numbers cited in the conclusion must be traceable via verify_conclusions.py to a trial_id in raw_results.jsonl.
- Failure handling: if Gate 1.8 fails, re-run the experiment or correct the conclusion. Approximate or estimated values are NOT a permissible fallback.

## API experiment defaults

- 3–5 models × 2–3 conditions × 15–25 tasks × 3 trials
- Use tools/call_api.py or agent's native API tool with AUTORESEARCH_API_KEY
