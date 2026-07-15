---
name: Deli_AutoResearch
description: A protocol framework for long-horizon autonomous tasks. Targets three empirically-observed failure modes — cognitive loops, stalling, runtime fragility — by prescribing state management, stall detection, and watchdog mechanisms. Validated on multiple task types including paper writing (4 ICLR-format surveys, in-framework self-rating 8.0-8.6/10).
type: Agent Framework
tags: autonomous, long-horizon, zero-interaction, anti-loop, heartbeat-watchdog, loop, multi-agent, unattended, orchestration
---

# Deli_AutoResearch

This skill is a protocol framework for long-horizon autonomous tasks (days to weeks). This repository ships **reference implementations** in `tools/` plus orchestrator prompts — agents should read `AGENTS.md` at the repo root first.

## Repository layout (distributable)

```
<repo>/
├── AGENTS.md                      # Agent onboarding — read first
├── tools/                         # stall_detector, check_gates, search_arxiv, ...
├── tasks/<slug>/                  # Per-project state + paper + logs
│   ├── state/
│   ├── logs/
│   └── paper/
└── Deli_AutoResearch/
    ├── SKILL.md                   # This file
    ├── orchestrator/loop_prompt.md  # Paste into /loop 2h
    ├── watchdog/                  # L0 shell + L1 cron prompts
    ├── prompts/                   # Subagent patterns A–D
    └── skills/                    # paper-writing + 5 sub-skills + router.md
```

## 1. Motivation

Long-running code agents exhibit three recurring failure modes:

1. Cognitive loop — successive iterations try similar directions with diminishing returns, unable to escape a local optimum on their own.
2. Stalling — the agent finishes a chunk of work, outputs a summary, and waits for user feedback. Externally the session looks alive and polling runs, but work has effectively stopped. Run logs show this is more common than crashes.
3. Runtime fragility — context compaction silently breaks the loop; closing a session takes down the timers parasitic on it. Failures go unnoticed by default.

The common cause of all three is missing engineering scaffolding, not insufficient model capability. Every mechanism in this framework targets the failure modes above.

## 2. Behavioral Constraints

1. Zero interaction — no prompting the user during a run: no Plan Mode, no question tool, no ending on a question. Continue working until the user stops you. Resolve ambiguity yourself and write the reasoning to the log (level=decision).
2. Ready means execute — the most common hidden violation: finishing all preparation and then asking "should I submit?". The purpose of preparation is execution; submitting, resubmitting, fixing, and starting monitors are all routine operations needing no confirmation.
3. Callback means report-alive — after context compaction the loop dies silently. The first action of every callback is to update its own last_seen, then check liveness; on detecting failure it restarts immediately and logs it.
4. Persist state to files — all progress is written to state/ files, not conversation memory. Each iteration starts a fresh session, injecting only curated state; never use resume.
5. Guardian / worker separation — a heartbeat patrol may take only three actions on tasks that are not its own: liveness-check, restart, nudge. It does not read their data, modify their state files, or report to the user on their behalf.

## 3. Architecture

    ┌── Orchestrator (current session / durable cron) ──┐
    │ monitor state files → detect stalls → inject direction │
    └────┬─────────────┬─────────────┬────────────┘
      [Task A]      [Task B]      [Task C]   ← each its own fresh session

Core design decisions:
- Separate execution from evaluation — the agent doing the work does not judge its own progress; stall determination is made by the orchestration layer based on quantitative metrics.
- Fresh session over resume — context accumulation is the primary cause of cognitive loops. Each iteration starts with fresh context; state is injected via files.
- Enforced direction diversity — before each iteration, read the list of tried directions; a new direction must differ from all history.

## 4. State Files

    tasks/<slug>/state/
    ├── task_spec.md           # goal / milestones / success criteria
    ├── progress.json          # {iteration, total_findings, status, stale_count, phase, current_score}
    ├── findings.jsonl         # accumulated findings (append-only)
    ├── directions_tried.json  # directions already tried
    └── iteration_log.jsonl    # per-iteration summary
    
    tasks/<slug>/logs/
    ├── work.jsonl             # written by work agent; decisions tagged level=decision
    ├── orchestrator.jsonl     # written by orchestrator
    └── heartbeat.jsonl        # written by heartbeat watchdog
    
    tasks/<slug>/paper/          # LaTeX pipeline outputs (see skills/paper-writing/)

Log line format: {"ts":"...", "source":"...", "level":"info|warn|error|decision", "event":"...", "detail":"..."}

## 5. Usage

    # 1. Initialize a task:
    python tools/init_task.py <slug> --topic "Your topic"
    # Edit tasks/<slug>/state/task_spec.md (Scope, Angle, Audience)
    
    # 2. Start the orchestrator loop — full prompt in orchestrator/loop_prompt.md:
    /loop 2h  (paste loop block; set {{REPO_ROOT}})
    # Each tick: python tools/stall_detector.py tasks --scan
    # Launch work agents via prompts/pattern_a_goal_driven.md + skills/router.md
    
    # 3. Register heartbeat — watchdog/L1_cron_prompt.md (hourly)
    # Optional L0: watchdog/L0_shell_guard.ps1 or .sh in separate terminal

## 6. Stall Detection & Pivoting

| Mechanism           | Rule                                                         |
| ------------------- | ------------------------------------------------------------ |
| Stall detection     | an iteration with 0 new findings or a metric drop → stale_count + 1 |
| Forced pivot        | stale_count >= 2 → change a structural constraint, not tactical parameters; >= 4 → flag for human attention |
| Direction diversity | a new direction must differ from every tried one; after a stall, inject a perturbation strategy |
| Round cap           | a single work session caps at 15 rounds or 30 minutes        |

"Pivot structure, not tactics" comes from practice: when a task stalls repeatedly within a frame, the decisive gain usually comes from correcting the environment/structural constraint itself, not from tuning strategy parameters harder inside the existing frame.

## 7. Heartbeat Watchdog

The business loop is itself unreliable and needs an independent guardian layer. Three mutually-checking layers (V3):

| Layer | Form                 | Depends on                   | Role                                                         |
| ----- | -------------------- | ---------------------------- | ------------------------------------------------------------ |
| L0    | resident shell guard | no session                   | heartbeat stale > 2h → spin up an emergency patrol via a headless agent |
| L1    | durable cron, hourly | a living interactive session | check each loop's last_seen, restart timed-out loops, detect stalling and nudge |
| L2    | business loop        | each its own session         | first line of each callback updates its own last_seen        |

Any one layer dying can be detected and recovered by another.

Stall detection: if progress has no update for over 2 hours and the last output is a question → judged stalled, launch a nudge subagent. Three consecutive nudges with no progress → judged structurally stuck; stop nudging and reopen with a new direction. The 2h threshold is deliberately shorter than the 4h stuck-task threshold.

## 8. Subagent Scheduling Patterns

| Pattern                | Use                  | Key idea                                                     |
| ---------------------- | -------------------- | ------------------------------------------------------------ |
| A Goal-driven          | research iteration   | inject tried directions, require verifiable findings, write back to findings.jsonl |
| B Parallel exploration | complex sub-problems | fire multiple agents in one message: investigation, refutation, cross-domain analogy |
| C Experiment run       | long compute jobs    | start minute-level polling right after submit: auto-diagnose errors, fix, resubmit |
| D Verification         | post-iteration QA    | an independent subagent audits the evidence chain of findings |
| E Independent review   | peer review round    | a fresh subagent runs the 5-persona review; no external API key required (Backend B in `skills/peer_review_simulation/SKILL.md`) |

A subagent prompt should include: background, a verifiable deliverable, working directory, file/line caps, and completion criteria.

**Pattern E (API-free independent review).** When no OpenAI-compatible API key is available, peer review is delegated to a fresh subagent launched via the host agent's `Task` tool (`subagent_type=general_purpose_task` or equivalent). The subagent inherits the host's own model and quota — no extra credential is needed. It reads the same grounded-evidence inputs (fulltext, raw_results, gate outputs), enforces the same anti-hallucination v3 iron rules (every weakness carries `paper_quote` + `fulltext_quote` + `char_offset`), and writes `paper/review_round_N.json` in the same schema as `call_api.py`. Validated end-to-end on the affective-EEG survey (6.0 → 9.0 over 10 rounds, zero external API keys). Full launch contract and brief template in `skills/peer_review_simulation/SKILL.md`.

## 9. Engineering Constraints

1. At most 5 large files per iteration; no single file over 300 lines.
2. State is injected via files, not conversation history.
3. Validation (test / compile / check) must run between iterations.
4. Citation-like content is verified every 20 entries, never batched up.
5. With multiple candidate directions, prefer adding diversity over digging one deeper.
6. Unresolvable external-dependency failures escalate (full report + notify the owner + poll for a reply); never abandon silently.
7. **(Anti-hallucination v2) Provenance-or-die** — Any entry written to `references.bib` must have a corresponding API call anchor in `paper/retrieval_log.jsonl` (matched by DOI / arXiv ID / title). Entries without an anchor are treated as fabricated; Gate 1.5 blocks progress.
8. **(Anti-hallucination v2) Multi-source retrieval** — Non-arXiv citations must be retrieved via `search_crossref.py` / `search_dblp.py` / `search_semantic_scholar.py`. The LLM must never fill fields (author / volume / issue / pages / DOI / booktitle) from memory.
9. **(Anti-hallucination v2) Numerical claim anchoring** — Exact numerical values appearing in section files (`58.6%`, `N=24`, `32 Hz`, etc.) must be anchored to a verbatim source string in `retrieval_log.jsonl`'s `extra.summary` or in `fulltext/<cite_key>.txt`. Gate 1.6 blocks unanchored claims.
10. **(Anti-hallucination v2) LLM responsibility compression** — In literature_survey the LLM does only three things: write query terms / score LQS / tag A-B-C-D depth. Editing bib files directly, rewriting `@article` to `@inproceedings`, or writing numerical claims from memory is forbidden.
11. **(Anti-hallucination v3) Fulltext-first** — A/B-level citations must have their full text fetched to `paper/fulltext/<cite_key>.txt` (via `tools/fetch_fulltext.py`). All factual and numerical claims anchor to the full text first; abstract is only a fallback.
12. **(Anti-hallucination v3) Grounded writing** — Any section paragraph containing factual claims must begin with a JSON claims block; each claim must include `cite_key` + `quote`, and the quote must verbatim match the full text. If `tools/grounded_writing.py` verification fails, the LaTeX output is rejected.
13. **(Anti-hallucination v3) Factual claim anchoring** — Factual statements in sections (e.g. "X proposed Y", "Z demonstrated W") must be findable in the cited full text (verb + >=70% keyword match). Gate 1.7 blocks unanchored claims.
14. **(Anti-hallucination v3) Conclusion grounding** — Every numerical / comparative / summary statement in the conclusion section must be based on `paper/raw_results.jsonl` (self-run experiments) or on the cited paper's full text. Gate 1.8 blocks ungrounded conclusions.
15. **(Anti-hallucination v3) Metadata cross-validation** — Bib metadata (title/year/authors/venue/doi) must be cross-validated across CrossRef / DBLP / Semantic Scholar. If any field disagrees across all three sources, that is a FAIL and Gate 1.9 blocks progress.
16. **(Anti-hallucination v3) Solid evidence chain** — Any paper claim must be traceable backwards to either (a) experimental data in `raw_results.jsonl` or (b) a verbatim quote in `fulltext/<cite_key>.txt`. A claim with no traceable evidence is treated as a hallucination and must not be retained.

## 10. Validation & Limits

The framework has carried several heterogeneous tasks: academic paper writing, long-horizon research, etc. Paper-track output:

| Paper                                             | Pages | Citations | Self-rated | Review backend |
| ------------------------------------------------- | ----- | --------- | ---------- | -------------- |
| Autonomous Research Agents                        | 59    | 228       | 8.0/10     | A (API)        |
| Continual Learning                                | 65    | 326       | 8.0/10     | A (API)        |
| Long-Horizon Decision-Making                      | 55    | 384       | 8.0/10     | A (API)        |
| Self-Play (285B RL experiment + theory hardening) | 75    | 217       | 8.6/10     | A (API)        |
| Affective EEG/BCI survey (IEEE RBME)              | —     | —         | 9.0/10     | B (subagent, no API key) |

Limits:
1. Scores come from in-framework multi-persona simulated review; comparable only longitudinally within the same protocol, not an external quality claim.
2. The longest continuous run on record was 72 hours, with 6 directional human inputs during it — zero operational intervention, directional intervention retained.
3. Fabricated citations and data artifacts originate from the LLM itself; the **anti-hallucination v2+v3** stack closes the loop end-to-end:
   - v2 retrieval_log mandatory anchor (Gate 1.5)
   - v2 multi-source API retrieval (search_crossref / dblp / semantic_scholar)
   - v2 numerical claim anchoring (Gate 1.6)
   - v3 fulltext fetch (fetch_fulltext.py)
   - v3 grounded writing protocol (grounded_writing.py)
   - v3 factual claim anchoring to full text (Gate 1.7)
   - v3 conclusion must be grounded in raw_results (Gate 1.8)
   - v3 three-way metadata cross-validation (Gate 1.9)

   There is no "remaining risk" escape hatch and no "human final check" fallback. If a gate fails, the task does not advance until the LLM repairs the issue using real API retrieval plus a verbatim full-text quote.
4. Separation of duties relies on protocol constraints, not model self-discipline; removing the constraints brings overstepping behavior back.