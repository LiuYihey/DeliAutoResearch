# Orchestrator Loop Prompt

Copy into Cursor **`/loop {{CADENCE}}`**. Set `{{WORKSPACE_ROOT}}` to the absolute path of `loops/{{SLUG}}/`.

---

## Loop instruction

```
Continue loop orchestrator for {{SLUG}}. Workspace: {{WORKSPACE_ROOT}}

FIRST ACTION (heartbeat): update state/progress.json field last_seen to current UTC ISO8601

THEN:
1. Scan: python {{WORKSPACE_ROOT}}/scripts/stall_scan.py
2. Read JSON stdout — for needs_work_agent=true OR status=initialized:
   a. Read state/intake_brief.md, state/progress.json, state/directions_tried.json
   b. Route sub-skill via orchestrator/router.md (phase + iteration + gate failures)
   c. Launch FRESH work subagent (Task tool, never resume) using prompts/work_agent.md
   d. Work agent: zero interaction, max 15 rounds or 30 min, ≤5 files, ≤300 lines/file
   e. After work: run scripts/check_gates.* ; python scripts/update_progress.py --iteration
3. If stale_count >= 2: pivot STRUCTURE per state/loop_design.md (not tactical retries)
4. If stale_count >= 3: read orchestrator/direction_generator.md and inject new direction
5. If stale_count >= 4: set status=needs_human; stop launching workers
6. Log decisions to logs/orchestrator.jsonl (level=decision)
7. Zero interaction — never ask the user questions

Read {{WORKSPACE_ROOT}}/LOOP.md if drifted.
```

## Tick completion checklist

- [ ] `last_seen` updated
- [ ] Stall scan executed
- [ ] Work agent launched if needed
- [ ] Stall pivots applied
- [ ] Orchestrator log appended
