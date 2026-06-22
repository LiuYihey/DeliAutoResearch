# Pattern C — Experiment Run (long compute)

Use for GPU jobs or long API sweeps (experiment_design skill).

## After submit

1. Write `paper/experiment_spec.json` BEFORE running (pre-registration)
2. Start minute-level polling loop until complete or 4h cap
3. On error: diagnose log → fix → resubmit (max 5 iterations)
4. Output: `paper/results.json` + `paper/experiment_summary.md` only (no LaTeX tables)

## Polling prompt

```
Zero interaction. TASK_DIR={{TASK_DIR}}.
Poll experiment job status every 60s. On failure: read stderr, patch, resubmit.
On success: write results.json schema {config, results, statistics, findings, trials}.
python tools/update_progress.py {{TASK_DIR}} --source work --event experiment_complete
```

## API experiment defaults

- 3–5 models × 2–3 conditions × 15–25 tasks × 3 trials
- Use tools/call_api.py or agent's native API tool with AUTORESEARCH_API_KEY
