# Orchestrator Loop Prompt

Copy this into Cursor **/loop** (recommended: every 2 hours). Replace `{{REPO_ROOT}}` with the absolute path to this repository.

---

## Loop instruction (paste into /loop 2h)

```
Continue Deli AutoResearch orchestrator. Repo: {{REPO_ROOT}}

FIRST ACTION (L2 heartbeat): run
  python tools/update_progress.py {{REPO_ROOT}}/tasks --event heartbeat --detail "orchestrator tick" --source orchestrator
(use any task dir only to touch global heartbeat if needed; prefer updating each active task's last_seen via scan below)

THEN:
1. Scan: python tools/stall_detector.py {{REPO_ROOT}}/tasks --scan
   (stall_detector now reports anti_hallucination.fulltext_missing and retrieval_log.orphans;
    these elevate needs_work_agent and force re-anchor routing)
2. For each task where needs_work_agent=true OR status=initialized:
   a. Read state/task_spec.md, state/progress.json, state/directions_tried.json
   b. Route sub-skill via Deli_AutoResearch/skills/router.md based on phase + iteration.
      If stall_detector flags provenance / hallucinat / factual / misrepresent / conclusion / overstated,
      route to literature_survey with a re-anchor directive (no paper_structure until cleared).
   c. Launch a FRESH work subagent (Task tool, never resume) using Deli_AutoResearch/prompts/pattern_a_goal_driven.md.
      - For literature_survey tasks: confirm paper/retrieval_log.jsonl exists and grows this iteration.
      - For paper_structure tasks: confirm grounded_writing.py was run (paper/grounded_writes/*.tex).
   d. Work agent MUST: zero interaction, max 15 rounds or 30 min, <=5 files, <=300 lines/file.
   e. After work: python tools/check_gates.py <task_dir>  (HARD-BLOCKING on Gate 1.5-1.9)
      - Gate 1.5 (retrieval_provenance): 0 orphans required
      - Gate 1.6 (numerical_claims): 100% anchored required
      - Gate 1.7 (factual_claims): 100% anchored at >= moderate required
      - Gate 1.8 (conclusion_grounding): 100% grounded + raw_results.jsonl present
      - Gate 1.9 (metadata_cross_validated): 0 FAILs required
      - Any Gate 1.5-1.9 failure -> do NOT advance phase; route back to literature_survey / paper_structure.
   f. python tools/update_progress.py <task_dir> --iteration --detail "..."
3. If stale_count >= 2: pivot STRUCTURE (not tactics) per Deli_AutoResearch/SKILL.md section 6.
4. If stale_count >= 3: inject new direction via Deli_AutoResearch/orchestrator/direction_generator.md.
5. Log every decision to logs/orchestrator.jsonl (level=decision for ambiguity resolution).
6. Zero interaction — never ask the user questions.

Read Deli_AutoResearch/SKILL.md if drifted. Read AGENTS.md for full protocol.
There is no "remaining risk" escape hatch and no "human final check" fallback. If Gate 1.5-1.9 fails,
the task does not advance until the LLM repairs the issue using real-API retrieval plus a verbatim full-text quote.
```

## Phase -> iteration map (paper track)

| Phase | Iter range | Target score | Primary sub-skills |
|-------|------------|--------------|-------------------|
| 0 | - | - | Fill task_spec Scope/Angle/Audience |
| 1 | 1–6 | 6.0 | structure → literature → figures → review |
| 2 | 7–9 | 7.5–8.0 | experiment → figures → structure → review |
| 3 | 10+ | 8.5+ | review loop + weakness routing |

## Completion criteria per orchestrator tick

- [ ] All active tasks scanned
- [ ] Stalled tasks nudged or pivoted
- [ ] At least one work agent launched if any task needs_work_agent
- [ ] progress.json last_seen updated for touched tasks
- [ ] For literature_survey tasks touched: paper/retrieval_log.jsonl grew this tick
- [ ] For paper_structure tasks touched: paper/grounded_writes/*.tex present + check_gates.py Gate 1.5-1.9 all pass
- [ ] No task advanced phase while Gate 1.5-1.9 failing
