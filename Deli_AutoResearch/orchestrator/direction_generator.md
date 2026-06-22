# Direction Generator

Use when `stale_count >= 3` or three consecutive nudges failed.

## Rules

1. Read `state/directions_tried.json` — new direction MUST differ from all entries.
2. After stall: perturb, don't refine — opposite hypothesis, cross-domain analogy, or structural constraint change.
3. Write new direction to `directions_tried.json` via:
   `python tools/update_progress.py <task_dir> --direction "your new direction"`

## Perturbation strategies

| Strategy | When | Example |
|----------|------|---------|
| Opposite hypothesis | Confirmatory loop failed | "Methods fail at long horizon" instead of "methods succeed" |
| Cross-domain analogy | Taxonomy stuck | Import ideas from robotics / neuroscience / economics |
| Structural pivot | stale_count ≥ 2 | Change experiment path API→synthetic; split mega-section |
| Review-driven | Low clarity score | Rebuild taxonomy axis, not more prose |
| Literature gap | Coverage weakness | Target 2025–2026 only; venue-upgrade pass |

## Direction record format

Append to `findings.jsonl` when direction is chosen:

```json
{"source":"orchestrator","level":"decision","event":"new_direction","detail":"...","direction":"..."}
```

## Anti-patterns (reject these directions)

- "Try harder on same section"
- "Add more citations" without taxonomy cell target
- "Improve wording" when structure gate failed
- Any direction semantically similar to a tried one
