#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "Deli AutoResearch bootstrap at $ROOT"
command -v python3 >/dev/null && python3 -m pip install -r requirements.txt -q 2>/dev/null || true
if [ ! -d "$ROOT/tasks/_example" ]; then
  python3 tools/init_task.py _example --topic "Example autonomous research survey"
fi
echo ""
echo "Next steps:"
echo "  1. Read AGENTS.md"
echo "  2. python3 tools/init_task.py <your-slug> --topic 'Your topic'"
echo "  3. Paste Deli_AutoResearch/orchestrator/loop_prompt.md into Cursor /loop 2h"
echo "Done."
