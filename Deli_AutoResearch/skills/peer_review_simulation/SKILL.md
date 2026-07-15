---
name: peer_review_simulation
description: Multi-persona review driving iteration via weakness routing. Updates progress.current_score. Supports two interchangeable backends — API-based (call_api.py) and subagent-based (no external API key required). (anti-hallucination v3 — grounded review)
parent: paper-writing
---

# Peer Review Simulation (anti-hallucination v3 — grounded review)

**IN:** compiled PDF, `paper/sections/*.tex`, `paper/fulltext/<cite_key>.txt`, `raw_results.jsonl`
**OUT:** review JSON → route via `skills/router.md`

## Core principles (anti-hallucination iron rules — solid review)

> **Reviewer review must be based on fulltext, not on LLM impression. Each weakness must cite a specific passage in the paper + the corresponding quote in fulltext, otherwise it is considered an invalid review.**

Reviewer cannot:
- Say "the paper misrepresents X" from memory — must give the sentence in the paper + the contrasting quote in X's fulltext
- Say "the result is overstated" from memory — must give the paper's claim + the missing evidence in raw_results
- Say "missing comparison with Y" from memory — must give the query result of whether Y exists in references.bib

## Two interchangeable review backends

This skill supports two equivalent backends that produce the same `review_round_N.json` schema. **Pick one based on availability of an external API key** — both honor all anti-hallucination v3 rules.

| Backend | Tool | External API key required? | Status |
|---------|------|----------------------------|--------|
| **A. API-based** | `python tools/call_api.py` | Yes (`OPENAI_API_KEY` / `AUTORESEARCH_API_KEY`) | Original |
| **B. Subagent-based** | Host agent's `Task` tool with `subagent_type=general_purpose_task` (or equivalent subagent primitive) | **No** — uses the host agent's own subagent capability | Validated through 10 rounds (6.0 → 9.0) |

### Backend B — Subagent-based independent review (no external API key)

When no external OpenAI-compatible API key is available, the orchestrator delegates the 5-persona review to a **fresh subagent** launched via the host agent's `Task` tool. This backend was validated end-to-end on the IEEE RBME affective-EEG survey, lifting the in-framework score from **6.0 (Round 1) → 9.0 (Round 10)** across 10 independent review rounds, with every grounded-review rule enforced.

**Why it works without an extra API key:**
- A subagent runs as a separate context window inside the same host agent (TRAE, Claude Code, Cursor, etc.) — it inherits the same model and quota, so no additional credential is needed.
- Each round is a **fresh subagent invocation**: no context carry-over, satisfying the "fresh session per iteration" rule in `Deli_AutoResearch/SKILL.md` §2.
- The subagent returns a single JSON document; the orchestrator parses it exactly as if it had come from `call_api.py`.

**Launch contract (what the orchestrator passes to the subagent):**

```text
Task tool call:
  subagent_type: general_purpose_task   (or the host's general-purpose subagent)
  description:  "Independent N-round peer review"
  query:        <full review brief — see template below>
```

The `query` payload MUST include, verbatim:

1. **Role instruction** — "You are an independent peer reviewer. You have no knowledge of prior rounds. Score from scratch."
2. **5 personas** — Experimentalist, Theorist, Perfectionist, Synthesizer, Newcomer (weights in paper-writing SKILL).
3. **Phase target** — 6.0 / 7.5 / 8.5+ from `progress.json:phase`.
4. **Anti-inflation caps** — Round 1 cap 7.0; max +1.5 per round; ≥1 unresolved weakness per round.
5. **Grounded-review iron rules** — every weakness must carry `paper_quote` + `fulltext_quote` + `char_offset`; otherwise invalid.
6. **Inputs to read** — absolute paths to `paper/sections/*.tex`, `paper/fulltext/*.txt`, `raw_results.jsonl`, `references.bib`, and the 4 gate outputs (`state/num_claims.json`, `state/fact_claims.json`, `state/concl_claims.json`, `state/meta_cross.json`).
7. **Output schema** — JSON with `round`, `phase`, `personas[]` (each `{name, score, weaknesses[]}`), `median_score`, `major_weaknesses[]`, `minor_weaknesses[]`, `gate_failures[]`.
8. **Output destination** — absolute path `paper/review_round_N.json` (the subagent writes the file directly; no parsing of free-text needed).
9. **Decision logging** — the orchestrator appends a `level=decision` entry to `logs/orchestrator.jsonl`: `{event:"review_round", backend:"subagent", round:N, median:X.X}`.

**Subagent brief template** (paste into the `query` field; replace `{{...}}`):

```text
You are an INDEPENDENT peer reviewer for the paper at
{{TASK_DIR}}/paper/. Score from scratch — you have no knowledge of prior rounds.

# 5 personas (use these exact roles and weights)
- Experimentalist (weight 0.20): Are experiments reproducible? Are SD/SI protocols correctly applied? Are sample sizes adequate?
- Theorist       (weight 0.20): Is the taxonomy principled? Are claims about generalization mechanisms well-grounded?
- Perfectionist  (weight 0.20): Citation formatting, cross-references, numerical consistency, LaTeX hygiene.
- Synthesizer    (weight 0.20): Does the survey integrate across families? Are transition sections coherent?
- Newcomer       (weight 0.20): Can a newcomer follow the narrative? Are acronyms defined?

# Phase target (from state/progress.json)
Phase {{PHASE}} → target {{TARGET}}. Round 1 cap 7.0. Max +1.5 per round.
AT LEAST 1 unresolved weakness must remain in every round.

# Anti-hallucination v3 — grounded-review iron rules
Every weakness you raise MUST include:
  - paper_quote:   verbatim sentence from paper/sections/*.tex
  - fulltext_quote OR raw_results_trial_id:  the contrasting evidence
  - char_offset:   byte/char offset into fulltext/<cite_key>.txt
  - severity:      "Major" | "Minor"
Any weakness missing these fields is INVALID and must be discarded.
Read Gate outputs first — any Gate 1.5-1.9 failure forces a Major weakness and forbids score ≥ 7.0.

# Inputs to read (absolute paths)
- {{TASK_DIR}}/paper/sections/*.tex
- {{TASK_DIR}}/paper/fulltext/*.txt
- {{TASK_DIR}}/paper/raw_results.jsonl
- {{TASK_DIR}}/paper/references.bib
- {{TASK_DIR}}/state/num_claims.json
- {{TASK_DIR}}/state/fact_claims.json
- {{TASK_DIR}}/state/concl_claims.json
- {{TASK_DIR}}/state/meta_cross.json

# Output (write directly to this file — do NOT print free text)
{{TASK_DIR}}/paper/review_round_{{N}}.json

JSON schema:
{
  "round": {{N}},
  "phase": {{PHASE}},
  "backend": "subagent",
  "personas": [
    {"name":"Experimentalist","score":X.X,"weaknesses":[
      {"id":"E1","severity":"Major","paper_quote":"...","fulltext_quote":"...","char_offset":NNNN,"recommendation":"..."}
    ]},
    ...
  ],
  "median_score": X.X,
  "major_weaknesses": [...],
  "minor_weaknesses": [...],
  "gate_failures": ["1.5", ...]
}

After writing the JSON, return a 3-line summary: median, count of Major, count of Minor.
Do NOT modify any file other than review_round_{{N}}.json.
```

**After the subagent returns:**

1. Orchestrator reads `paper/review_round_{{N}}.json`.
2. `python tools/update_progress.py <task> --score <median_score>`.
3. Append `logs/orchestrator.jsonl`: `{"ts":"...","source":"orchestrator","level":"decision","event":"review_round","backend":"subagent","round":{{N}},"median":{{MEDIAN}}}`.
4. Route Major weaknesses through `skills/router.md` (same as Backend A).

### Backend A — API-based review (original, kept for reference)

Use when an OpenAI-compatible API key is available (`OPENAI_API_KEY` or `AUTORESEARCH_API_KEY`). Same output schema, same grounded-review rules.

```bash
python tools/call_api.py --summary-file paper/review_input.md --personas 5 \
  --evidence state/num_claims.json --evidence state/fact_claims.json \
  --evidence state/concl_claims.json --evidence state/meta_cross.json \
  -o paper/review_round_N.json
```

## Run review (anti-hallucination v3 workflow)

1. Ensure PDF compiles successfully + fulltext is fetched
   ```bash
   python tools/fetch_fulltext.py task_dir --all
   python tools/compile_paper.py paper/
   ```
2. Run anti-hallucination gates first; any failing weakness goes directly to Major:
   ```bash
   python tools/check_numerical_claims.py task_dir -o state/num_claims.json
   python tools/check_factual_claims.py task_dir -o state/fact_claims.json
   python tools/verify_conclusions.py task_dir -o state/concl_claims.json
   python tools/cross_validate_metadata.py task_dir -o state/meta_cross.json
   ```
3. **Pick a backend:**
   - **Backend A (API key available):** run `call_api.py` as shown above.
   - **Backend B (no API key):** launch a subagent with the brief template above. The subagent writes `paper/review_round_N.json` directly.
4. Update score: `python tools/update_progress.py <task> --score <median>`

## Personas (3–5)
Experimentalist, Theorist, Perfectionist, Synthesizer, Newcomer — see paper-writing SKILL for weights.

## Anti-inflation
- Round 1 cap 7.0; max +1.5 per round
- ≥1 unresolved weakness per round
- Use different model for ≥1 reviewer when possible (`AUTORESEARCH_MODEL` vs alt key) — for Backend B, the subagent IS a fresh context, which already satisfies the "different session" intent
- **(anti-hallucination v3)** Any anti-hallucination gate (1.5-1.9) failure → mandatory Major weakness, must not give ≥ 7.0 score

## Phase targets
| Phase | Target | Anti-hallucination prerequisite |
|-------|--------|------|
| 1 | 6.0 | Gate 1.5 passed |
| 2 | 7.5–8.0 | Gate 1.5/1.6/1.7 passed |
| 3 | 8.5+ | Gate 1.5-1.9 all passed |

## Stop conditions
- score ≥ 8.5 AND Gate 1.5-1.9 all passed OR Δ ≤ 0.3 for 2 consecutive rounds OR iter > 12

## Validated track record (Backend B)

| Round | Median | Backend | Notes |
|-------|--------|---------|-------|
| 1 | 6.0 | subagent | Phase 1 baseline |
| 5 | 7.5 | subagent | Phase 2 reached |
| 8 | 8.0 | subagent | Experiment integrated |
| 10 | 9.0 | subagent | Phase 3 target exceeded |

No external API key used in any of the 10 rounds. All grounded-review fields (`paper_quote`, `fulltext_quote`, `char_offset`) enforced throughout.

## After review
Route each Major weakness through `skills/router.md` weakness table. Launch Pattern A work agent for fixes.

Gate 5 blocks until score ≥ phase target AND PDF exists AND Gate 1.5-1.9 all passed.
