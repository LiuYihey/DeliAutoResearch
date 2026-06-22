# Watchdog Patrol (L1)

Register as **hourly** cron or paste into a separate `/loop 1h` session.

```
Loop engineering L1 patrol. Workspace parent: {{WORKSPACE_ROOT}}

ALLOWED: liveness-check, restart orchestrator loop, nudge worker.
FORBIDDEN: edit artifacts/, declare task done, read business data for user reports.

1. Touch {{WORKSPACE_ROOT}}/../.heartbeat (or workspace .heartbeat) with timestamp
2. For workspace {{WORKSPACE_ROOT}}:
   - python scripts/stall_scan.py
   - If idle_hours >= 2 and needs_work_agent: nudge via prompts/work_agent.md
     (inject: "CONTINUE from progress.json, zero interaction")
   - If nudge_count >= 3 with no metric progress: stop nudging; next orchestrator tick must inject direction
3. If orchestrator last_seen stale > 3× loop interval: remind user to restart /loop
4. Log to logs/heartbeat.jsonl
5. Zero interaction
```

## L0 shell guard (optional)

Run in a separate terminal every 30 min:

```bash
# Unix — save as loops/.heartbeat_guard.sh
THRESH=7200  # seconds
HB="{{WORKSPACE_ROOT}}/.heartbeat"
if [ -f "$HB" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$HB" 2>/dev/null || stat -f %m "$HB") ))
  [ "$age" -gt "$THRESH" ] && echo "ALERT: heartbeat stale ${age}s — restart patrol"
fi
```
