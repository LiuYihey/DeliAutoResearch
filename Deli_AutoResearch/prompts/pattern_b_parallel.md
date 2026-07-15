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

Anti-hallucination iron rules (mandatory):
- Investigator / Refuter evidence must come from real-API retrieval or from a paper/fulltext/ quote.
  - Do NOT cite from memory. Use tools/search_*.py to retrieve, and record hits to paper/retrieval_log.jsonl.
  - Do NOT paraphrase paper claims from memory. Extract quotes from paper/fulltext/<cite_key>.txt.
- The Analogist's cross-domain analogy must be structural (architecture / training paradigm).
  Do NOT use specific numbers, authors, or years (those are high-hallucination-risk).
- Every finding's evidence_path must point to one of:
  - paper/retrieval_log.jsonl#<stable_id>  (retrieval record)
  - paper/fulltext/<cite_key>.txt#<char_offset>  (full-text quote)
  - paper/raw_results.jsonl#<trial_id>  (experiment data)
```

Orchestrator merges findings after all complete; it does NOT let patrol agents edit paper.
Patrol agents that produce findings without retrieval_log / fulltext / raw_results anchoring
are flagged in logs/work.jsonl with level=warning and anchor=missing. The orchestrator
re-routes the task to literature_survey with a re-anchor directive before promoting the finding.
