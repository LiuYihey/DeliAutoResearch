# Pattern D — Verification (post-iteration QA, anti-hallucination v3 — solid evidence)

Independent subagent — MUST NOT be the same session that produced the artifacts.

## Prompt

```
Zero interaction. TASK_DIR={{TASK_DIR}}.
You are an independent verifier. Do NOT fix issues — only report.

Audit:
1. Last 3 entries in state/findings.jsonl — is evidence path real?
2. python tools/verify_citations.py {{TASK_DIR}} --batch-size 20 -o state/verify_batch.json
   (anti-hallucination v2: three-way dispatch DOI > arXiv > title)
3. python tools/check_gates.py {{TASK_DIR}}
   (anti-hallucination v3: 9 gates, including 1.5-1.9 anti-hallucination five-piece suite)
4. python tools/check_numerical_claims.py {{TASK_DIR}} -o state/numerical_claims.json
   (anti-hallucination v3: numerical claims must be anchored to fulltext, not just summary)
5. python tools/check_factual_claims.py {{TASK_DIR}} -o state/factual_claims.json
   (anti-hallucination v3: factual claims "X proposed Y" must be anchored in fulltext)
6. python tools/verify_conclusions.py {{TASK_DIR}} -o state/conclusion_claims.json
   (anti-hallucination v3: conclusion must be based on raw_results or cited paper fulltext)
7. python tools/cross_validate_metadata.py {{TASK_DIR}} --batch-size 20 -o state/meta_cross.json
   (anti-hallucination v3: three-party metadata cross-validation)

Write report to state/verification_report.json:
{"passed":bool,"hallucinated_citations":[],"orphan_bib_entries":[],
 "unanchored_numerical_claims":[],"unanchored_factual_claims":[],
 "unanchored_conclusions":[],"metadata_diffs":[],
 "gate_failures":[],"recommendation":"..."}

If failed: orchestrator routes weakness via skills/router.md
- orphan_bib_entries non-empty → literature_survey (re-anchor): run search_crossref / search_dblp to supplement anchors
- unanchored_numerical_claims non-empty → fetch_fulltext + fix section (numerical values must be anchored in fulltext)
- unanchored_factual_claims non-empty → fetch_fulltext + grounded_writing rewrite section
- unanchored_conclusions non-empty → supplement raw_results or fix conclusion
- metadata_diffs non-empty → cross_validate_metadata provides ground truth, rewrite bib fields
```

## Solid evidence requirements (anti-hallucination v3)

verifier itself must be grounded — cannot write review from memory:
- each reported hallucinated_citation must provide evidence that CrossRef/DBLP/S2 all could not find it
- each reported unanchored_claim must provide specific attempt of "searching keyword X in fulltext/<cite_key>.txt failed"
- any weakness must be accompanied by quote or raw_log path, otherwise treated as invalid review, not counted in score
