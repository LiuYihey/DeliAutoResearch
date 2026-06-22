# Skill Router — {{SLUG}}

Read `state/progress.json` for `phase`, `iteration`, `archetype`. Override with `active_sub_skill` if set.

## Phase transitions

| From | Condition | Action |
|------|-----------|--------|
| 0 → 1 | Phase 0 exit criteria met in intake_brief | `update_progress.py --phase 1 --status running` |
| 1 → 2 | Phase 1 exit criteria met | `--phase 2` |
| 2 → 3 | Phase 2 exit criteria met | `--phase 3` |
| * → done | `metric_value >= target_metric_value` AND gates pass | `--status done` |

## Iteration → sub-skill (customize per task)

| Iter | Phase | Sub-skill | Key outputs |
|------|-------|-----------|-------------|
| 1 | 0 | {{SUB_SKILL_1}} | {{OUTPUT_1}} |
| 2 | 1 | {{SUB_SKILL_2}} | {{OUTPUT_2}} |
| 3 | 1 | {{SUB_SKILL_3}} | {{OUTPUT_3}} |
| 4+ | 2+ | router weakness table | see below |

## Weakness → sub-skill

| Signal (gate failure / metric) | Route to |
|--------------------------------|----------|
| {{WEAKNESS_1}} | {{ROUTE_1}} |
| {{WEAKNESS_2}} | {{ROUTE_2}} |
| {{WEAKNESS_3}} | {{ROUTE_3}} |

## After each sub-skill

1. Run `scripts/check_gates.sh` or `scripts/check_gates.py`
2. `python scripts/update_progress.py --iteration --detail "<what shipped>"`
3. Append verifiable line to `state/findings.jsonl`
