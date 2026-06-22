---
name: paper_structure
description: Survey chapter architecture, taxonomy, formal claims, hedge language. Outputs sections/*.tex.
parent: paper-writing
---

# Paper Structure & Logic

**IN:** `paper/references.bib`, `paper/citation_plan.jsonl`, experiment findings  
**OUT:** `paper/sections/*.tex`, updated `paper/main.tex`

## Chapter architecture
- §1 Introduction: Hook → Gap → Contributions → Roadmap
- §2 Background: definitions + taxonomy overview
- §3–6 Core: one method family per chapter + critical assessment
- §7 Benchmarks + experiments
- §8 Future: Barrier + Attack vector per open problem
- §9 Conclusion: numbered findings (not abstract repeat)

## Rules
- Each `.tex` file ≤ 300 lines — split if larger
- Paragraph patterns: Claim-Evidence-Implication, Compare-Contrast, Concession-Rebuttal, Funnel
- Taxonomy: multi-axis MECE matrix; empty cells = gap analysis
- Claims: default Conjecture + Remark; hedge ladder: demonstrates > suggests > may
- Mandatory related-work comparison table vs existing surveys

## Validation
```bash
python tools/compile_paper.py paper/
```

## Gate 3
- Compiles 0 errors; transitions between sections; ≥1 formal claim; terminology consistent
