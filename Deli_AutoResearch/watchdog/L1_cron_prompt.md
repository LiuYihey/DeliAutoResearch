# L1 Heartbeat Patrol Prompt

Register as **hourly** durable cron (Cursor cron / system scheduler). Survives across sessions when bound to a living agent session.

---

## Patrol instruction

```
Deli AutoResearch L1 heartbeat patrol. Repo: {{REPO_ROOT}}

ALLOWED ACTIONS ONLY: liveness-check, restart, nudge.
DO NOT read task business data for reporting. DO NOT modify findings or paper content.

1. Append timestamp to {{REPO_ROOT}}/.heartbeat (create if missing)
2. Log: append to each task's logs/heartbeat.jsonl event=patrol
3. For each task under tasks/ (skip _example unless AUTORESEARCH_RUN_EXAMPLE=1):
   - python tools/stall_detector.py <task_dir>
   - If idle_hours >= 2 and needs_work_agent: launch nudge subagent (pattern_a, inject task_spec + "CONTINUE, zero interaction")
   - If nudge_count >= 3 with no progress: stop nudging; orchestrator must inject new direction next tick
4. Check orchestrator /loop last_seen (if tracked in .heartbeat meta); if stale > 3× loop interval, restart /loop per Deli_AutoResearch/orchestrator/loop_prompt.md
5. Zero interaction
```

## L0 shell guard

Run `watchdog/L0_shell_guard.ps1` (Windows) or `watchdog/L0_shell_guard.sh` (Unix) in a separate terminal. If `.heartbeat` age > 2h, script prints alert — start L1 patrol manually or via headless agent.
