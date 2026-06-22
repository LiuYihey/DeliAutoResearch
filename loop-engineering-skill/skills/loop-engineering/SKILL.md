---
name: loop-engineering
description: >-
  Designs and scaffolds autonomous agent loop frameworks from user requests.
  Borrows loop-engineering patterns (file-backed state, orchestrator ticks, stall
  detection, fresh sessions, quality gates) to generate a tailored multi-iteration
  workflow for any long-horizon task. Use when the user wants a /loop setup,
  unattended agent runs, loop framework, orchestrator scaffold, or asks to turn
  a goal into a repeatable agent iteration protocol.
---

# Loop Engineering

Generate a **self-contained loop workspace** that lets an agent run a user goal across many iterations without cognitive loops, silent stalls, or context rot.

This skill **does not modify** existing project code. Output lives under `loops/<slug>/` (or a user-specified path) unless the user explicitly asks to integrate elsewhere.

## When to apply

| Signal | Action |
|--------|--------|
| User describes a multi-step goal spanning hours/days | Run full workflow below |
| User mentions `/loop`, cron, unattended, overnight | Include orchestrator + watchdog |
| User wants one-shot work | **Do not** use this skill — execute directly |
| User already has Deli AutoResearch paper task | Point to repo `AGENTS.md`; do not duplicate |

## Core philosophy (borrowed, domain-agnostic)

Long-horizon agent runs fail for **engineering** reasons, not model limits:

1. **Cognitive loop** — retries similar tactics; fix with direction history + structural pivots
2. **Stalling** — agent summarizes and waits; fix with zero-interaction rules + nudge patrol
3. **Context rot** — compaction kills progress; fix with fresh session per iteration + file state

Every generated loop must embed these invariants:

| Invariant | Implementation |
|-----------|----------------|
| State in files | `state/`, `artifacts/`, `logs/` — never conversation memory |
| Fresh session | Each work iteration = new agent/subagent; no resume |
| Separate judge | Orchestrator reads metrics; worker does not self-declare "done" |
| Gates between iterations | Automated checks before `progress.json` advances |
| Stall → pivot structure | `stale_count ≥ 2` changes framing/constraints, not hyperparameters |
| Zero interaction mid-run | Worker never asks user; log `level=decision` instead |

## Workflow overview

```
User request → Intake → Classify archetype → Design loop → Scaffold → Handoff
```

Copy this checklist and track progress:

```
Loop scaffold progress:
- [ ] 1. Intake brief written (goal, deliverables, constraints)
- [ ] 2. Archetype + phases chosen (see reference/task-archetypes.md)
- [ ] 3. Metrics + gates defined
- [ ] 4. Workspace files created under loops/<slug>/
- [ ] 5. Orchestrator loop_prompt.md ready for /loop
- [ ] 6. Optional watchdog prompt if run > 4h unattended
- [ ] 7. User handoff: how to start, where state lives, stop conditions
```

---

## Phase 1 — Intake

Extract or infer from the user request. If critical fields are missing, ask **once** before scaffolding (this is setup, not mid-run interaction).

| Field | Question to answer |
|-------|-------------------|
| **Goal** | One sentence outcome |
| **Deliverables** | Concrete artifacts (files, PRs, reports, datasets) |
| **Success criteria** | Measurable done-ness (tests pass, word count, metric threshold) |
| **Scope / non-goals** | What is explicitly out |
| **Cadence** | Loop interval: 30m / 1h / 2h / daily |
| **Risk** | External deps, secrets, destructive ops → escalate rules |
| **Workspace** | Default `loops/<slug>/`; slug = kebab-case from goal |

Write `loops/<slug>/state/intake_brief.md` using [templates/task_spec.md.tpl](templates/task_spec.md.tpl) as the base (rename sections as needed).

---

## Phase 2 — Classify & design

Read [reference/task-archetypes.md](reference/task-archetypes.md) and pick the closest archetype. Hybrid tasks combine rows (e.g. build + content).

### Design decisions (record in `state/loop_design.md`)

1. **Phases** — 2–5 phases with entry/exit criteria
2. **Iteration router** — which sub-skill runs at iteration N (see [templates/router.md.tpl](templates/router.md.tpl))
3. **Primary metric** — one number the orchestrator tracks (`current_score`, `tests_passing`, `items_done`, etc.)
4. **Finding format** — append-only `state/findings.jsonl`; each line = verifiable delta
5. **Gates** — shell/python checks run after every work iteration ([templates/check_gates.sh.tpl](templates/check_gates.sh.tpl))
6. **Subagent patterns** — pick from table below
7. **Stop conditions** — success threshold, max iterations, or `stale_count ≥ 4` → flag human

### Subagent patterns

| Pattern | When | Template |
|---------|------|----------|
| A Goal-driven | Default per-iteration work | [templates/work_agent.md.tpl](templates/work_agent.md.tpl) |
| B Parallel probe | Stuck on design; need alternatives | Launch 2–3 subagents: best path, skeptic, analogy |
| C Long job | Training, batch jobs, CI | Submit → poll → auto-fix → resubmit |
| D Verification | After risky edits | Independent subagent audits evidence chain |

### Stall rules (always include)

| Event | Action |
|-------|--------|
| 0 new findings in iteration | `stale_count += 1` |
| `stale_count ≥ 2` | Pivot **structure** (scope split, different artifact type, new sub-skill order) |
| `stale_count ≥ 3` | Inject new direction via `orchestrator/direction_generator.md` |
| `stale_count ≥ 4` | Set `status: needs_human`; stop auto-nudging |
| Idle > 2× loop interval | Watchdog nudge (if watchdog enabled) |

---

## Phase 3 — Scaffold workspace

Run the init script **or** copy templates manually:

```bash
# From the installed skill directory (e.g. .cursor/skills/loop-engineering/)
python scripts/init_loop.py <slug> --goal "..." --workspace loops
```

### Target layout

```
loops/<slug>/
├── LOOP.md                 # Human + agent onboarding (from LOOP_WORKSPACE.md.tpl)
├── orchestrator/
│   ├── loop_prompt.md      # Paste into Cursor /loop
│   └── direction_generator.md
├── prompts/
│   └── work_agent.md
├── state/
│   ├── intake_brief.md     # task spec
│   ├── loop_design.md
│   ├── progress.json
│   ├── findings.jsonl
│   ├── directions_tried.json
│   └── iteration_log.jsonl
├── artifacts/              # deliverables (code, docs, data — task-specific)
├── logs/
│   ├── work.jsonl
│   ├── orchestrator.jsonl
│   └── heartbeat.jsonl
└── scripts/
    ├── check_gates.sh      # or .py — task-specific validation
    ├── update_progress.py
    └── stall_scan.py
```

File schemas: [reference/state-contract.md](reference/state-contract.md)

### Customization rules

- Replace every `{{PLACEHOLDER}}` in templates
- `check_gates` must be **executable** and return non-zero on failure
- `router.md` lives in `orchestrator/router.md` — keep ≤ 15 iteration rows; complexity → phases
- Cap work agent: **≤5 files**, **≤300 lines/file**, **≤15 tool rounds** or **30 min** per iteration
- Log format (all `logs/*.jsonl`):

```json
{"ts":"ISO8601","source":"work|orchestrator|heartbeat","level":"info|warn|error|decision","event":"...","detail":"..."}
```

### Finding line format

```json
{"event":"finding","phase":1,"sub_skill":"implement","artifact":"artifacts/src/foo.py","metric":"tests_added","value":3,"verified":true}
```

---

## Phase 4 — Orchestrator prompt

Fill [templates/loop_prompt.md.tpl](templates/loop_prompt.md.tpl) → `orchestrator/loop_prompt.md`.

User starts the loop in Cursor:

```
/loop 2h
```

(paste contents of `orchestrator/loop_prompt.md`; set `{{WORKSPACE_ROOT}}` to absolute path)

Orchestrator tick checklist (embed in loop_prompt):

1. Heartbeat: update `state/progress.json` → `last_seen`
2. Run `python scripts/stall_scan.py` (or equivalent)
3. For each `needs_work_agent`: read state files → route → launch **fresh** work subagent
4. Apply stall actions (pivot / new direction / flag human)
5. Append `logs/orchestrator.jsonl`
6. Zero interaction

---

## Phase 5 — Watchdog (optional)

For unattended runs > 4 hours, add [templates/watchdog.md.tpl](templates/watchdog.md.tpl) as hourly cron or separate terminal guard.

Guardian may **only**: liveness-check, restart loop, nudge worker. Never edit `artifacts/` or declare task complete.

---

## Phase 6 — Handoff to user

Deliver a short summary:

1. **Path** — `loops/<slug>/`
2. **Start** — paste `orchestrator/loop_prompt.md` into `/loop <cadence>`
3. **Monitor** — `state/progress.json`, `logs/orchestrator.jsonl`
4. **Stop** — success criteria met OR `status: needs_human`
5. **First manual step** — anything the loop cannot auto-resolve (credentials, approvals)

---

## Examples

| User request | Archetype | Key phases |
|--------------|-----------|------------|
| "Migrate Express API to FastAPI overnight" | `code-build` | audit → port routes → tests → cleanup |
| "Write 12 blog posts from outline" | `content-pipeline` | outline lock → draft batch → edit → SEO pass |
| "Benchmark 5 vector DBs and pick one" | `research-eval` | criteria → run benches → compare → recommendation |
| "Fix all ESLint errors in monorepo" | `refactor-hygiene` | scan → batch fix → verify → regressions |

Full walkthrough: [examples/content-pipeline.md](examples/content-pipeline.md)

---

## Anti-patterns

| Avoid | Why |
|-------|-----|
| Single giant prompt, no state files | Context rot; unrecoverable stalls |
| Worker decides "we're done" | Premature stop; no metric gate |
| Resume long chat each iteration | Cognitive loop; tool-call drift |
| Pivot by tuning same approach harder | Proven stall pattern |
| Skip gates to save time | Silent quality regression |
| Scaffold inside `src/` without asking | Violates isolation default |

---

## Reference index

| File | Purpose |
|------|---------|
| [reference/task-archetypes.md](reference/task-archetypes.md) | Archetype → phases, metrics, gates |
| [reference/state-contract.md](reference/state-contract.md) | JSON schemas, field semantics |
| [examples/content-pipeline.md](examples/content-pipeline.md) | End-to-end sample |
| [templates/](templates/) | Copy-fill scaffold templates |
| [scripts/init_loop.py](scripts/init_loop.py) | One-command workspace bootstrap |
