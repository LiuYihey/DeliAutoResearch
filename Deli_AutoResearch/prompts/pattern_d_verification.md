# Pattern D — Verification (post-iteration QA)

Independent subagent — MUST NOT be the same session that produced the artifacts.

## Prompt

```
Zero interaction. TASK_DIR={{TASK_DIR}}.
You are an independent verifier. Do NOT fix issues — only report.

Audit:
1. Last 3 entries in state/findings.jsonl — is evidence path real?
2. python tools/verify_citations.py on next 20 bib entries (export JSON first)
3. python tools/check_gates.py {{TASK_DIR}}

Write report to state/verification_report.json:
{"passed":bool,"hallucinated_citations":[],"gate_failures":[],"recommendation":"..."}

If failed: orchestrator routes weakness via skills/router.md
```
