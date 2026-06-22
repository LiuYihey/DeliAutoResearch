# Example: Content Pipeline Loop

User request: *"I have a 12-post outline on Rust async patterns. Generate drafts overnight with quality checks."*

## Intake summary

| Field | Value |
|-------|-------|
| Archetype | `content-pipeline` |
| Slug | `rust-async-blog-series` |
| Metric | `pieces_done` / target `12` |
| Cadence | `/loop 1h` |
| Workspace | `loops/rust-async-blog-series/` |

## Scaffold command

```bash
python scripts/init_loop.py rust-async-blog-series \
  --goal "Draft 12 blog posts from locked outline on Rust async patterns" \
  --workspace loops \
  --archetype content-pipeline \
  --cadence 1h \
  --metric pieces_done \
  --target 12
```

## Customizations after init

### state/loop_design.md (excerpt)

```markdown
## Phases
- 0: Outline validated — 12 titles in artifacts/outline.md
- 1: Draft — one post per iteration until pieces_done=12
- 2: Edit — consistency pass across all posts
- 3: Polish — rubric score ≥ 8/10 per post

## Gates (scripts/check_gates.sh)
- Each draft ≥ 800 words
- `cargo check` on embedded snippets (if any)
- markdownlint on changed files
```

### orchestrator/router.md (iteration rows)

| Iter | Sub-skill | Output |
|------|-----------|--------|
| 1 | outline-lock | artifacts/outline.md |
| 2–13 | draft-post | artifacts/posts/NN-slug.md |
| 14–16 | edit-series | cross-post consistency |
| 17+ | polish | rubric pass |

### Finding example

```json
{"event":"finding","phase":1,"sub_skill":"draft-post","artifact":"artifacts/posts/03-channels.md","metric":"pieces_done","value":3,"verified":true}
```

### check_gates.sh snippet

```bash
POSTS=$(ls -1 artifacts/posts/*.md 2>/dev/null | wc -l)
test "$POSTS" -gt 0
for f in artifacts/posts/*.md; do
  words=$(wc -w < "$f")
  test "$words" -ge 800
done
python scripts/update_progress.py --metric-value "$POSTS"
```

## Handoff text (given to user)

1. Review `loops/rust-async-blog-series/state/intake_brief.md` — paste your outline into `artifacts/outline.md`
2. Start `/loop 1h` with `orchestrator/loop_prompt.md`
3. Monitor `state/progress.json` → `metric_value` toward 12
4. Stop when `status: done` or review drafts in `artifacts/posts/`

## Stall scenario

- Iterations 5–6 produce editorial tweaks only (`pieces_done` unchanged) → `stale_count` hits 2
- Orchestrator pivots structure: skip polish, enforce "new post only" rule, reduce scope to 600 words minimum temporarily
- Iteration 7 ships post 6 → `stale_count` resets
