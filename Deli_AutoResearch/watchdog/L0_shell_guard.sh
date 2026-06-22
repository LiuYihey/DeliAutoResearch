#!/usr/bin/env bash
# L0 Resident Shell Guard (Unix)
# Usage: ./Deli_AutoResearch/watchdog/L0_shell_guard.sh
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEARTBEAT="$REPO_ROOT/.heartbeat"
MAX_STALE_HOURS=2
POLL_SECONDS=300

echo "L0 guard watching $HEARTBEAT"
while true; do
  if [ ! -f "$HEARTBEAT" ]; then
    date -Iseconds > "$HEARTBEAT"
  fi
  if [ "$(uname)" = "Darwin" ]; then
    age=$(( ($(date +%s) - $(stat -f %m "$HEARTBEAT")) / 3600 ))
  else
    age=$(( ($(date +%s) - $(stat -c %Y "$HEARTBEAT")) / 3600 ))
  fi
  if [ "$age" -gt "$MAX_STALE_HOURS" ]; then
    echo "ALERT: heartbeat stale ${age}h — start L1 patrol"
    date -Iseconds > "$HEARTBEAT"
  fi
  sleep "$POLL_SECONDS"
done
