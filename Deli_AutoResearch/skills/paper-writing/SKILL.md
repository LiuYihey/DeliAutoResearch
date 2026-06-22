---
name: paper-writing
description: Parent skill group — orchestrates five sub-skills for autonomous 8.5/10 survey papers. Use skills/router.md for phase routing.
type: Skill Group
---

# Scientific Paper Writing — Skill Group

Hierarchical skill group validated on Deli Chen's AutoResearch pipeline (4 surveys, 8.0–8.6/10 in-framework).

## Sub-skills (read individually)

| # | Skill | Path |
|---|-------|------|
| 01 | Literature Survey | `literature_survey/SKILL.md` |
| 02 | Paper Structure | `paper_structure/SKILL.md` |
| 03 | Experiment Design | `experiment_design/SKILL.md` |
| 04 | Figures & Tables | `figures_tables/SKILL.md` |
| 05 | Peer Review Simulation | `peer_review_simulation/SKILL.md` |

## Router
**Always consult** `../router.md` for iteration → sub-skill mapping and weakness routing.

## Phases

- **Phase 0:** Topic — Scope / Angle / Audience in `task_spec.md`
- **Phase 1 (iter 1–6):** Draft → target 6.0
- **Phase 2 (iter 7–9):** Experiment + deep improvement → 7.5–8.0
- **Phase 3 (iter 10+):** Review sprint → 8.5+

## Quality gates
```bash
python tools/check_gates.py tasks/<your-task>
```

Full gate definitions: see original `skills/paper-writing-skill.md` or paper-writing.html on victorchen96.github.io.

## Score progression
6.0 complete draft → 7.0 transitions + conjecture → 8.0 experiment + 150 refs → 8.5 meta-analysis + theory
