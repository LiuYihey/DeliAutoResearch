# Pattern B — Parallel Exploration

Fire 2–3 subagents in ONE message when stuck or exploring taxonomy / gaps.

## Agents to launch in parallel

| Agent | Role | Deliverable |
|-------|------|-------------|
| Investigator | Best case for current hypothesis | findings.jsonl entry + evidence path |
| Refuter | Strongest counter-evidence | findings.jsonl entry + evidence path |
| Analogist | Cross-domain structural analogy | 1-page memo in state/ or finding |

## Prompt skeleton

```
Zero interaction. TASK_DIR={{TASK_DIR}}. Read task_spec.md only.
You are the {{ROLE}} agent. Return ONE append-only finding to state/findings.jsonl.
Do not edit paper/ unless your role is Investigator and task_spec requires it.
Max 10 rounds. Log to logs/work.jsonl.
```

Orchestrator merges findings after all complete; does NOT let patrol agents edit paper.
