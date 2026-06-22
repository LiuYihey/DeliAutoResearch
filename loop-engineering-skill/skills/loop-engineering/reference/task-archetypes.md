# Task Archetypes

Pick the closest row; combine for hybrid tasks. Record choice in `state/loop_design.md`.

## Archetype table

| Archetype | Typical goals | Primary metric | Default phases | Default gates |
|-----------|---------------|----------------|----------------|---------------|
| `code-build` | Feature, service, CLI | `tests_passing` / `build_ok` | spec → implement → test → integrate | unit tests, lint, build |
| `refactor-hygiene` | Debt cleanup, migration | `issues_remaining` ↓ | scan → batch fix → verify → docs | lint, typecheck, diff size cap |
| `research-eval` | Compare options, survey | `evidence_items` / `score` | criteria → gather → analyze → recommend | citation verify, reproducibility |
| `content-pipeline` | Docs, blogs, course | `pieces_done` / `quality_score` | outline → draft → edit → polish | spellcheck, link check, rubric |
| `data-pipeline` | ETL, labeling, features | `rows_processed` / `valid_rate` | ingest → transform → validate → export | schema check, sample audit |
| `ops-automation` | CI, deploy, monitoring | `checks_green` | audit → script → dry-run → apply | dry-run pass, rollback plan |
| `bug-hunt` | Repro, fix, regress | `bugs_closed` | reproduce → isolate → fix → regression test | repro test, CI |
| `creative-explore` | Design, architecture options | `variants_explored` | frame → diverge → converge → commit | review rubric, constraint check |

## Phase design patterns

### code-build

| Phase | Exit criteria |
|-------|---------------|
| 0 Spec | `intake_brief.md` has API/contracts defined |
| 1 Core | Happy-path implementation compiles |
| 2 Harden | Tests ≥ target coverage; edge cases |
| 3 Integrate | Wired into repo; docs updated |

Router iterations 1–3: spec review → implement → test. Iteration 4+: router weakness table.

### content-pipeline

| Phase | Exit criteria |
|-------|---------------|
| 0 Outline | Structure + per-piece brief locked |
| 1 Draft | All pieces v1 in `artifacts/` |
| 2 Edit | Style/consistency pass |
| 3 Polish | SEO/accessibility/rubric score ≥ target |

Metric: `quality_score` from checklist or LLM rubric (log rubric version in findings).

### research-eval

| Phase | Exit criteria |
|-------|---------------|
| 0 Criteria | Evaluation matrix in `state/loop_design.md` |
| 1 Gather | N sources per option; findings.jsonl |
| 2 Analyze | Comparison table artifact |
| 3 Recommend | Decision doc with tradeoffs |

Gate: every claim in comparison links to a finding line with `verified: true`.

### refactor-hygiene

| Phase | Exit criteria |
|-------|---------------|
| 0 Inventory | Issue list with counts |
| 1 Batch | Fix ≤5 files per iteration (framework cap) |
| 2 Verify | CI/lint green |
| 3 Prevent | Rule/doc so issues don't return |

Metric: `issues_remaining` from scanner output; stall if count plateaus 2 iterations.

## Weakness routing (generic)

After phase 1, route by last gate failure or lowest metric:

| Signal | Sub-skill | Action |
|--------|-----------|--------|
| tests fail | `test-fix` | Fix failures before new features |
| lint/type errors | `hygiene` | Batch fix |
| missing docs | `document` | Update README/changelog |
| score below target | `review-polish` | Rubric-driven pass |
| external block | `escalate` | Log `needs_human`; poll if applicable |

## Cadence guidance

| Expected duration | Loop interval | Watchdog |
|-------------------|---------------|----------|
| < 2 hours | Manual iterations (no /loop) | No |
| 2–8 hours | `/loop 1h` | Optional L1 |
| 8–72 hours | `/loop 2h` | L1 hourly + optional L0 shell |
| Multi-day | `/loop 4h` | L1 + L0 required |

## Direction diversity

Before each work iteration, read `state/directions_tried.json`. New `active_direction` must differ in **approach**, not wording:

- Bad: "fix tests" → "repair tests"
- Good: "fix tests" → "rewrite module with TDD" → "isolate failing subsystem"

After stall pivot, append a structurally different constraint (smaller scope, different artifact type, parallel spike).
