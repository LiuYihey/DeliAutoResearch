# Skill Router — Phase & Weakness Routing

Central routing table for orchestrator and peer review. Read `state/progress.json` for `phase` and `iteration`.

## Phase 0 → 1 transition

When `task_spec.md` has Scope, Angle, Audience filled:
`python tools/update_progress.py <task> --phase 1 --status running`

## Iteration → sub-skill (paper track)

| Iter | Sub-skill | Key outputs |
|------|-----------|-------------|
| 1 | paper_structure | sections/01-02, main.tex compiles |
| 2 | literature_survey | references.bib, citation_plan.jsonl (stage 1-2) |
| 3 | paper_structure + figures_tables | sections/03-06, 2+ figures |
| 4 | literature_survey + paper_structure | stage 3-4, sections/07-08 |
| 5 | literature_survey + peer_review_simulation | verify citations, first review score |
| 6 | router (weakness fixes) | route per table below |
| 7 | experiment_design | experiment_spec.json, results.json |
| 8 | figures_tables + paper_structure | integrate experiment |
| 9 | peer_review_simulation | review + fixes |
| 10+ | peer_review_simulation loop | until score ≥ 8.5 or Δ≤0.3 × 2 rounds |

Override with `progress.active_sub_skill` if orchestrator sets explicit focus.

## Weakness → sub-skill

| Weakness keyword | Route to | Tool |
|------------------|----------|------|
| citation, arxiv, recent, coverage | literature_survey | search_arxiv.py, verify_citations.py |
| structure, taxonomy, transition, claim | paper_structure | — |
| experiment, rigor, trial, ablation | experiment_design | call_api.py |
| table, figure, error bar, visualization | figures_tables | compile_paper.py |
| review, score, clarity, novelty | peer_review_simulation | call_api.py |

## After each sub-skill

1. `python tools/check_gates.py <task_dir>`
2. `python tools/update_progress.py <task_dir> --iteration`
3. If phase target score met: `--phase N`

## Skill paths

- `Deli_AutoResearch/skills/literature_survey/SKILL.md`
- `Deli_AutoResearch/skills/paper_structure/SKILL.md`
- `Deli_AutoResearch/skills/experiment_design/SKILL.md`
- `Deli_AutoResearch/skills/figures_tables/SKILL.md`
- `Deli_AutoResearch/skills/peer_review_simulation/SKILL.md`
- `Deli_AutoResearch/skills/paper-writing/SKILL.md` (overview)
