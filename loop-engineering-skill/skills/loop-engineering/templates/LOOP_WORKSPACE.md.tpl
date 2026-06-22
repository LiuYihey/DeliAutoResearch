# Loop Workspace — {{SLUG}}

Autonomous loop for: **{{GOAL}}**

## Quick start

1. Fill `state/intake_brief.md` if not already complete
2. Review `state/loop_design.md` (phases, metrics, gates)
3. Paste `orchestrator/loop_prompt.md` into Cursor **`/loop {{CADENCE}}`**
4. Replace `{{WORKSPACE_ROOT}}` with absolute path to this directory

## Layout

| Path | Role |
|------|------|
| `state/` | Task spec, progress, findings — source of truth |
| `artifacts/` | Deliverables produced by work iterations |
| `logs/` | Append-only JSONL audit trail |
| `orchestrator/` | Loop tick + routing |
| `prompts/` | Work subagent templates |
| `scripts/` | Gates, stall scan, progress updater |

## Behavioral rules (non-negotiable)

1. **Zero interaction** during a run — log decisions to `logs/work.jsonl` (`level=decision`)
2. **Fresh session** per work iteration — never resume long chats
3. **≤5 files, ≤300 lines/file** per work iteration
4. **Run gates** before incrementing iteration: `bash scripts/check_gates.sh` or `python scripts/check_gates.py`
5. **Stall pivot** at `stale_count ≥ 2` — change structure, not parameters

## Monitor

```bash
cat state/progress.json
tail -n 5 logs/orchestrator.jsonl
python scripts/stall_scan.py
```

## Stop conditions

- `status: done` — success criteria met
- `status: needs_human` — `stale_count ≥ 4` or blocked external dep
- User stops `/loop` in Cursor

## Archetype

{{ARCHETYPE}} — see skill `reference/task-archetypes.md`
