#!/usr/bin/env bash
# Quality gates for {{SLUG}} — customize checks below.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== Gate 1: workspace integrity =="
test -f state/progress.json
test -f state/intake_brief.md

echo "== Gate 2: primary validation (CUSTOMIZE) =="
# Examples — uncomment one block:
# npm test
# pytest -q
# python -m compileall artifacts/
# test "$(wc -l < artifacts/draft.md)" -gt 100

echo "== Gate 3: artifact sanity =="
# test -d artifacts && test "$(ls -1 artifacts | wc -l)" -gt 0

echo "ALL GATES PASSED"
