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
2. For each task where needs_work_agent=true OR status=initialized:
   a. Read state/task_spec.md, state/progress.json, state/directions_tried.json
   b. Route sub-skill via Deli_AutoResearch/skills/router.md based on phase + iteration
   c. Launch a FRESH work subagent (Task tool, never resume) using Deli_AutoResearch/prompts/pattern_a_goal_driven.md
   d. Work agent MUST: zero interaction, max 15 rounds or 30 min, ≤5 files, ≤300 lines/file
   e. After work: python tools/check_gates.py <task_dir> (non-blocking) ; python tools/update_progress.py <task_dir> --iteration --detail "..."
3. If stale_count >= 2: pivot STRUCTURE (not tactics) per Deli_AutoResearch/SKILL.md §6
4. If stale_count >= 3: inject new direction via Deli_AutoResearch/orchestrator/direction_generator.md
5. Log every decision to logs/orchestrator.jsonl (level=decision for ambiguity resolution)
6. Zero interaction — never ask the user questions

Read Deli_AutoResearch/SKILL.md if drifted. Read AGENTS.md for full protocol.
```

## Phase → iteration map (paper track)

| Phase | Iter range | Target score | Primary sub-skills |
|-------|------------|--------------|-------------------|
| 0 | — | — | Fill task_spec Scope/Angle/Audience |
| 1 | 1–6 | 6.0 | structure → literature → figures → review |
| 2 | 7–9 | 7.5–8.0 | experiment → figures → structure → review |
| 3 | 10+ | 8.5+ | review loop + weakness routing |

## Completion criteria per orchestrator tick

- [ ] All active tasks scanned
- [ ] Stalled tasks nudged or pivoted
- [ ] At least one work agent launched if any task needs_work_agent
- [ ] progress.json last_seen updated for touched tasks
