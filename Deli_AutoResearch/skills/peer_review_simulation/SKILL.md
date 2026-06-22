---
name: peer_review_simulation
description: Multi-persona review driving iteration via weakness routing. Updates progress.current_score.
parent: paper-writing
---

# Peer Review Simulation

**IN:** compiled PDF or section summary  
**OUT:** review JSON → route via `skills/router.md`

## Run review
1. Ensure PDF or write `paper/review_input.md` summary (abstract + contributions + experiment headline)
2. ```bash
   python tools/call_api.py --summary-file paper/review_input.md --personas 5 -o paper/review_round_N.json
   ```
3. Update score: `python tools/update_progress.py <task> --score <median>`

## Personas (3–5)
Experimentalist, Theorist, Perfectionist, Synthesizer, Newcomer — see paper-writing SKILL for weights.

## Anti-inflation
- Round 1 cap 7.0; max +1.5 per round
- ≥1 unresolved weakness per round
- Use different model for ≥1 reviewer when possible (`AUTORESEARCH_MODEL` vs alt key)

## Phase targets
| Phase | Target |
|-------|--------|
| 1 | 6.0 |
| 2 | 7.5–8.0 |
| 3 | 8.5+ |

## Stop conditions
- score ≥ 8.5 OR Δ ≤ 0.3 for 2 consecutive rounds OR iter > 12

## After review
Route each Major weakness through `skills/router.md` weakness table. Launch Pattern A work agent for fixes.

Gate 5 blocks until score ≥ phase target and PDF exists.
