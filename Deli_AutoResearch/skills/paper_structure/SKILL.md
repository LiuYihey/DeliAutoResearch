---
name: paper_structure
description: Survey chapter architecture, taxonomy, formal claims, hedge language. Outputs sections/*.tex. (anti-hallucination v3 — grounded writing)
parent: paper-writing
---

# Paper Structure & Logic (anti-hallucination v3 — grounded writing)

**IN:** `paper/references.bib`, `paper/citation_plan.jsonl`, `paper/fulltext/<cite_key>.txt`, experiment findings
**OUT:** `paper/sections/*.tex`, updated `paper/main.tex`

## Core principles (anti-hallucination iron rules — solid evidence)

> **Every factual claim written by the LLM in a section must be traceable to an original quote in `paper/fulltext/<cite_key>.txt`, or to experimental data in self-run `raw_results.jsonl`. No quote = potential hallucination, blocked by Gate 1.7/1.8.**

Allowed "creative freedom" for the LLM in sections:
- Paragraph organization, transition sentences, taxonomy design
- Own commentary / critical assessment (but must be clearly marked)
- LaTeX commands, figure descriptions

The LLM is strictly prohibited from:
- Writing "X et al. proposed Y" from memory — must quote-match the full text
- Writing "Z achieved 92%" from memory — must be anchored in raw_results or fulltext
- Writing conclusion "our method outperforms all baselines" from memory — must have raw_results comparison

## Chapter architecture
- §1 Introduction: Hook → Gap → Contributions → Roadmap
- §2 Background: definitions + taxonomy overview
- §3–6 Core: one method family per chapter + critical assessment
- §7 Benchmarks + experiments
- §8 Future: Barrier + Attack vector per open problem
- §9 Conclusion: numbered findings (not abstract repeat)

## Grounded writing protocol (mandatory)

Every LaTeX paragraph containing factual claims must start with a JSON claims block for grounded_writing.py to verify:

````
```json
{
  "claims": [
    {
      "text": "Vaswani et al. introduced the Transformer architecture",
      "cite_key": "vaswani2017attention",
      "quote": "we propose a new simple network architecture, the Transformer, based solely on attention mechanisms",
      "quote_location": {"file": "fulltext/vaswani2017attention.txt", "char_offset": 1234}
    }
  ]
}
```
\section{...}
Vaswani et al. \cite{vaswani2017attention} introduced the Transformer architecture based solely on attention mechanisms.
````

LLM workflow:
1. Read `paper/fulltext/<cite_key>.txt` (must run `python tools/fetch_fulltext.py` first)
2. Find the original text fragment to cite, record the quote string
3. Write the claim JSON + LaTeX paragraph based on the quote
4. Run `python tools/grounded_writing.py task_dir --input draft.md -o sections/03_xxx.tex`
5. grounded_writing.py verifies the quote is actually in the fulltext, outputs LaTeX only if it passes

## Rules
- Each `.tex` file ≤ 300 lines — split if larger
- Paragraph patterns: Claim-Evidence-Implication, Compare-Contrast, Concession-Rebuttal, Funnel
- Taxonomy: multi-axis MECE matrix; empty cells = gap analysis
- Claims: default Conjecture + Remark; hedge ladder: demonstrates > suggests > may
- Mandatory related-work comparison table vs existing surveys
- **(anti-hallucination v3)** Factual claims for A/B level citations must quote-match the fulltext; C/D level citations are not allowed to write factual claims

## Validation (anti-hallucination v3 full chain)
```bash
# 1. Full text must be fetched first
python tools/fetch_fulltext.py task_dir --all

# 2. Verify quote with grounded_writing when writing section
python tools/grounded_writing.py task_dir --input draft.md -o sections/03_xxx.tex

# 3. Gate 1.6/1.7/1.8 checks
python tools/check_numerical_claims.py task_dir -o state/num_claims.json
python tools/check_factual_claims.py task_dir -o state/fact_claims.json
python tools/verify_conclusions.py task_dir -o state/concl_claims.json

# 4. Compile
python tools/compile_paper.py paper/

# 5. Run all gates
python tools/check_gates.py task_dir
```

## Gate 3 / 1.6 / 1.7 / 1.8 targets

| Gate | Check | Threshold |
|------|------|------|
| 1.6 numerical_claims | Numerical claim anchoring rate | = 100% (strict) |
| 1.7 factual_claims | Factual claims anchored to full text | = 100% (strict, at least moderate) |
| 1.8 conclusion_grounding | Conclusion based on raw_results | = 100% (strict) |
| 3 structure | Compile/transition/claim | Pass |
