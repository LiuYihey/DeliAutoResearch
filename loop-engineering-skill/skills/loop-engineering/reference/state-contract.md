# State Contract

All loops use the same file semantics. Customize field names in `loop_design.md` but keep shapes stable so `stall_scan.py` works.

## progress.json

```json
{
  "task_slug": "my-task",
  "goal_summary": "one line",
  "iteration": 0,
  "total_findings": 0,
  "last_iteration_findings": 0,
  "status": "initialized",
  "stale_count": 0,
  "nudge_count": 0,
  "last_seen": null,
  "phase": 0,
  "phase_targets": {},
  "primary_metric": "tests_passing",
  "metric_value": 0,
  "target_metric_value": 100,
  "active_sub_skill": null,
  "active_direction": null,
  "archetype": "code-build"
}
```

### Field semantics

| Field | Owner | Notes |
|-------|-------|-------|
| `iteration` | orchestrator | Incremented after each work agent completes |
| `last_iteration_findings` | orchestrator | Snapshot of `total_findings` at iter start |
| `stale_count` | stall_scan | Reset to 0 when `new_findings > 0` |
| `status` | orchestrator | `initialized` \| `running` \| `blocked` \| `needs_human` \| `done` |
| `last_seen` | any loop tick | ISO8601 UTC; heartbeat |
| `phase` | orchestrator | Integer; transitions per `loop_design.md` |
| `metric_value` | work agent via update_progress | Domain-specific primary metric |

## directions_tried.json

```json
{
  "directions": [
    {"id": "d1", "summary": "top-down refactor auth module", "iteration": 1, "outcome": "stalled"}
  ]
}
```

## findings.jsonl

Append-only. One JSON object per line. Required keys: `event`, `artifact`, `metric`, `value`, `verified`.

Orchestrator sets `total_findings = line count`.

## iteration_log.jsonl

One summary per completed iteration:

```json
{"iteration": 1, "sub_skill": "implement", "shipped": "artifacts/api/routes.py", "metric_delta": 12, "gates_passed": true}
```

## Log levels

| level | Use |
|-------|-----|
| `info` | Routine progress |
| `warn` | Recoverable issue |
| `error` | Failed gate or tool |
| `decision` | Ambiguity resolved without user input — **required** for autonomous runs |

## Stall scan output (stdout JSON)

`scripts/stall_scan.py` should print:

```json
{
  "needs_work_agent": true,
  "recommended_actions": ["nudge_work_agent", "pivot_structure"],
  "stale_count": 2,
  "new_findings_last_iter": 0,
  "idle_hours": 1.5
}
```

Orchestrator reads this; worker never reads stall state during execution (separation of duties).
