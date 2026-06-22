# AGENTS.md — Deli AutoResearch

**Read this file first.** Any coding agent dropped into this repo should follow this protocol to reproduce [Deli Chen's AutoResearch workflow](https://victorchen96.github.io/auto_research/framework.html).

## What this repo is

- **Framework:** `Deli_AutoResearch/SKILL.md` — orchestration, stall detection, heartbeat, zero-interaction rules
- **Paper pipeline:** `Deli_AutoResearch/skills/` — 5 sub-skills + `router.md`
- **Tools:** `tools/` — Python CLI agents call every iteration
- **Tasks:** `tasks/<slug>/` — one directory per research project (state + paper + logs)

No private infrastructure required. Replace internal `search_agent` / `call_api` with the included `tools/`.

## Quick start (agent)

```bash
# 1. Dependencies (optional; arxiv tools use stdlib only)
pip install -r requirements.txt

# 2. Create your task
python tools/init_task.py my-survey --topic "Your Research Topic"

# 3. Edit tasks/my-survey/state/task_spec.md — fill Scope, Angle, Audience

# 4. Start orchestrator loop in Cursor — paste from:
#    Deli_AutoResearch/orchestrator/loop_prompt.md
#    (replace {{REPO_ROOT}} with absolute path)

# 5. Optional: L0 watchdog in another terminal
#    powershell -File Deli_AutoResearch/watchdog/L0_shell_guard.ps1
```

## Mandatory behavioral rules

1. **Zero interaction** — never ask the user mid-run; log decisions to `logs/*.jsonl` with `level=decision`
2. **Fresh session per iteration** — inject state from files; never resume long chats
3. **Persist everything** — `state/`, `paper/`, `logs/`; not conversation memory
4. **Guardian separation** — heartbeat only: liveness-check, restart, nudge
5. **Validate between iterations** — `check_gates.py`, `compile_paper.py`, citation verify batches of 20

## Single iteration checklist

```
[ ] Read state/task_spec.md, progress.json, directions_tried.json
[ ] Route sub-skill: Deli_AutoResearch/skills/router.md
[ ] Read sub-skill SKILL.md
[ ] Execute (≤5 files, ≤300 lines/file)
[ ] Append finding to state/findings.jsonl
[ ] python tools/check_gates.py tasks/<slug>
[ ] python tools/update_progress.py tasks/<slug> --iteration --source work
```

## Orchestrator checklist (every /loop tick)

```
[ ] python tools/stall_detector.py tasks --scan
[ ] Launch Pattern A work agent for tasks with needs_work_agent
[ ] stale_count ≥ 2 → structural pivot (SKILL.md §6)
[ ] stale_count ≥ 3 → direction_generator.md
[ ] Log to logs/orchestrator.jsonl
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` or `AUTORESEARCH_API_KEY` | Peer review + API experiments |
| `OPENAI_BASE_URL` | OpenAI-compatible endpoint |
| `AUTORESEARCH_MODEL` | Model for call_api.py (default gpt-4o) |
| `AUTORESEARCH_RUN_EXAMPLE=1` | Include `tasks/_example` in scans |

## Key file map

| Path | Role |
|------|------|
| `Deli_AutoResearch/SKILL.md` | Master framework protocol |
| `Deli_AutoResearch/orchestrator/loop_prompt.md` | /loop 2h paste target |
| `Deli_AutoResearch/skills/router.md` | Phase + weakness routing |
| `Deli_AutoResearch/prompts/pattern_*.md` | Subagent templates |
| `tools/stall_detector.py` | Stall scan |
| `tools/check_gates.py` | Quality gates 1–5 |
| `tasks/<slug>/paper/` | LaTeX manuscript |

## Git discipline (recommended)

| When | Message |
|------|---------|
| Task init | `research(init): <slug>` |
| Protocol locked | `research(protocol): <hypothesis>` |
| Results | `research(results): <outcome>` |
| Review round | `research(review): score X.X` |

Protocol commit before results — never combine.

## Reference

- Framework: https://victorchen96.github.io/auto_research/framework.html
- Paper skill: https://victorchen96.github.io/auto_research/skill/paper-writing.html
- Full gate definitions: `Deli_AutoResearch/skills/paper-writing-skill.md` (legacy monolith, still valid)
