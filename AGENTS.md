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
6. **(Anti-hallucination v3) Provenance-or-die** — Any entry written to `references.bib` must have a corresponding API call anchor in `paper/retrieval_log.jsonl` (Gate 1.5)
7. **(Anti-hallucination v3) Fulltext-first** — A/B-level citations must have their full text fetched to `paper/fulltext/<cite_key>.txt`; all factual and numerical claims anchor to the full text first (Gate 1.6/1.7)
8. **(Anti-hallucination v3) Grounded writing** — When the LLM writes a section, every factual claim must include `cite_key + quote`; the quote must verbatim match the full text (via `tools/grounded_writing.py`)
9. **(Anti-hallucination v3) Conclusion grounding** — Every claim in the conclusion must be based on `paper/raw_results.jsonl` or on the cited paper's full text (Gate 1.8)
10. **(Anti-hallucination v3) Metadata cross-validation** — Bib metadata must be consistent across CrossRef / DBLP / Semantic Scholar (Gate 1.9)
11. **(Anti-hallucination v3) Solid evidence chain** — Any paper claim must be traceable backwards to either (a) experimental data in `raw_results.jsonl` or (b) a verbatim quote in `fulltext/<cite_key>.txt`; no traceable evidence = treated as hallucination and must not be retained

## Single iteration checklist (anti-hallucination v3)

```
[ ] Read state/task_spec.md, progress.json, directions_tried.json
[ ] Route sub-skill: Deli_AutoResearch/skills/router.md
[ ] Read sub-skill SKILL.md
[ ] (literature_survey) Run real-API searches -> auto-writes retrieval_log.jsonl
[ ] (literature_survey) fetch_fulltext.py pulls A/B citation full text -> paper/fulltext/
[ ] (paper_structure) Write section via grounded_writing.py (with JSON claims + quote)
[ ] Execute (<=5 files, <=300 lines/file)
[ ] Append finding to state/findings.jsonl
[ ] python tools/check_gates.py tasks/<slug>  (10 gates, incl. 1.5-1.9 anti-hallucination suite)
[ ] python tools/update_progress.py tasks/<slug> --iteration --source work
```

## Orchestrator checklist (every /loop tick, anti-hallucination v3)

```
[ ] python tools/stall_detector.py tasks --scan  (detects A/B citations with missing full text = stalled)
[ ] Launch Pattern A work agent for tasks with needs_work_agent
[ ] For literature_survey tasks: confirm retrieval_log.jsonl + fulltext/ have been generated
[ ] For paper_structure tasks: confirm grounded_writing.py has verified the section
[ ] For peer_review_simulation: pick a backend — A (call_api.py, needs API key) OR B (Pattern E subagent, no API key); see skills/peer_review_simulation/SKILL.md
[ ] stale_count >= 2 -> structural pivot (SKILL.md section 6)
[ ] stale_count >= 3 -> direction_generator.md
[ ] Any Gate 1.5-1.9 failure -> force Major weakness, route back to literature_survey for repair
[ ] Log to logs/orchestrator.jsonl
```

## Environment variables

| Variable | Purpose | Required? |
|----------|---------|-----------|
| `OPENAI_API_KEY` or `AUTORESEARCH_API_KEY` | Peer review Backend A + API experiments | No — Backend B (subagent) needs no key |
| `OPENAI_BASE_URL` | OpenAI-compatible endpoint | Only for Backend A |
| `AUTORESEARCH_MODEL` | Model for call_api.py (default gpt-4o) | Only for Backend A |
| `AUTORESEARCH_RUN_EXAMPLE=1` | Include `tasks/_example` in scans | Optional |

> **API-key-free operation:** If no external OpenAI-compatible key is configured, the framework automatically falls back to Backend B (Pattern E subagent) for peer review. Literature search still uses the free arXiv / CrossRef / DBLP / Semantic Scholar APIs. Only `call_api.py` and API experiments require a key.

## Key file map

| Path | Role |
|------|------|
| `Deli_AutoResearch/SKILL.md` | Master framework protocol (anti-hallucination v3 rules 7-16) |
| `Deli_AutoResearch/orchestrator/loop_prompt.md` | /loop 2h paste target |
| `Deli_AutoResearch/skills/router.md` | Phase + weakness routing |
| `Deli_AutoResearch/prompts/pattern_*.md` | Subagent templates |
| `tools/stall_detector.py` | Stall scan (incl. fulltext-missing detection) |
| `tools/check_gates.py` | Quality gates 1-5 + anti-hallucination 1.5-1.9 |
| `tools/retrieval_log.py` | Unified API call log (anti-hallucination core) |
| `tools/search_arxiv.py` | arXiv real-API search |
| `tools/search_crossref.py` | CrossRef real-API search (non-arXiv citations) |
| `tools/search_dblp.py` | DBLP real-API search (venue upgrade) |
| `tools/search_semantic_scholar.py` | Semantic Scholar real-API search (citation count) |
| `tools/verify_citations.py` | Three-path dispatch verification (DOI/arXiv/title) |
| `tools/cross_validate_metadata.py` | Three-way metadata cross-validation |
| `tools/fetch_fulltext.py` | PDF download + pdfminer full-text parsing |
| `tools/check_numerical_claims.py` | Numerical claim anchoring to full text |
| `tools/check_factual_claims.py` | Factual claim anchoring to full text |
| `tools/verify_conclusions.py` | Conclusion traceability to raw_results |
| `tools/grounded_writing.py` | Mandatory quote verification for LLM-written sections |
| `tasks/<slug>/paper/` | LaTeX manuscript |
| `tasks/<slug>/paper/retrieval_log.jsonl` | API call anchors (anti-hallucination required) |
| `tasks/<slug>/paper/fulltext/` | A/B citation full text (anti-hallucination required) |
| `tasks/<slug>/paper/raw_results.jsonl` | self-run experiment data (anti-hallucination required) |

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
