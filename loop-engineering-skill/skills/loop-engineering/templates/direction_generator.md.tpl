# Direction Generator

Invoke when `stale_count >= 3`. Orchestrator only — not the work agent.

## Inputs

Read:
- `state/directions_tried.json` — do not repeat approaches
- `state/findings.jsonl` — what actually shipped
- `logs/work.jsonl` — `level=decision` entries
- Last gate failure output

## Output

Write to `state/progress.json`:
- `active_direction`: one sentence, **structurally different** from all prior directions
- Append new entry to `directions_tried.json`

## Perturbation strategies (pick one)

1. **Scope split** — tackle smallest failing submodule first
2. **Artifact swap** — prose → table → diagram → code spike
3. **Inverted approach** — bottom-up instead of top-down; test-first instead of implement-first
4. **Parallel spike** — Pattern B: 2 subagents, 15 min each, pick winner
5. **Constraint tighten** — reduce files touched; stricter gate before expand
6. **Externalize** — mock/stub dependency to unblock; log tech debt finding

## Log

```json
{"level":"decision","event":"direction_injected","detail":"<strategy + new direction>"}
```

Append to `logs/orchestrator.jsonl`.
