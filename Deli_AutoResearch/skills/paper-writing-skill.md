# Scientific Paper Writing — Skill Group

Hierarchical skill group that orchestrates five sub-skills to autonomously produce 8.5/10 survey papers. Defines division of labor, phase routing, quality gates, and iterative review loops.

## Sub-skills

### 01 Literature Survey

4-stage pipeline: Recall → Score (LQS) → Classify (A/B/C/D) → Upgrade (arXiv→accepted).

**IN:** topic + taxonomy keywords  
**OUT:** references.bib + citation_plan.jsonl

#### Stage 1: High-Recall Retrieval
- 20-30 keyword queries via `search.py -o "site:arxiv.org ..."`
- Each taxonomy cell: 3+ query variants (core terms, synonyms, method names)
- Snowball: seed paper citation networks
- Target: 200-500 raw candidates

#### Stage 2: LQS Multi-Dimensional Scoring

| Dimension | Weight | Scoring |
|-----------|--------|---------|
| Recency | 30% | 6mo=10, 1yr=8, 2yr=5, 3yr=3 |
| Citation Impact | 25% | cites/mo: ≥50=10, ≥10=8, ≥3=6 |
| Venue | 20% | Top-tier=10, Strong=7, Workshop=4 |
| Institution | 10% | Top lab=10, Top uni=9 |
| Acceptance | 15% | Accepted=10, Under review=5, None=3 |

Thresholds: LQS≥7.0 must-cite, 5.0-7.0 conditional, <5.0 drop

#### Stage 3: Citation Depth Classification
- **A-level** (1-3 paragraphs): section protagonist, 3-5 per chapter
- **B-level** (2-5 sentences): important insight, 5-10 per chapter
- **C-level** (1 sentence): supporting evidence
- **D-level**: dropped, not cited

#### Stage 4: Venue Upgrade
- Cross-check DBLP + OpenReview for acceptance status
- arXiv with "Accepted at X" → `@inproceedings`
- Target: arXiv-only ratio ≤ 60%

#### Verification
- Every 20 citations: title match, author, year, venue check
- Target: verification rate ≥80%, hallucinated = 0
- Year distribution: within-1yr ≥40%, accepted ≥30%

---

### 02 Paper Structure & Logic

Chapter architecture, paragraph logic chains, taxonomy design, formal claims, hedge language, abstract-conclusion alignment.

**IN:** bib + experiment findings  
**OUT:** sections/*.tex (full manuscript)

#### Chapter Architecture (Survey Standard)
- §1 Introduction: Hook → Gap → Contributions → Roadmap
- §2 Background: formal definitions, taxonomy overview
- §3-6 Core: one method family per chapter, with critical assessment
- §7 Benchmarks + Experiments
- §8 Future: specific open problems (Barrier + Attack vector)
- §9 Conclusion: numbered key findings (not repeat of abstract)

#### Paragraph Logic Patterns

| Pattern | Structure | Use Case |
|---------|-----------|----------|
| Claim-Evidence-Implication | Assert → Data → So what | Main body |
| Compare-Contrast | A → B → Difference → Trade-off | Method comparison |
| Concession-Rebuttal | Admit strength → But limitation | Critical analysis |
| Funnel | Broad → Narrow → This paper | Introduction |

#### Taxonomy Design
- Multi-axis matrix (not flat list)
- MECE: mutually exclusive, collectively exhaustive
- Must have empty cells → gap analysis material
- Spanning methods show taxonomy tension (good)

#### Formal Claims
- Default: `Conjecture + Remark` (not Theorem)
- Hedge ladder: demonstrates > suggests > may > hypothesize
- Rule: claim strength ≤ evidence strength

#### Related Work Differentiation
- Mandatory comparison table with existing surveys
- "We're more recent" is NOT sufficient differentiation
- Need structural novelty: new taxonomy, new angle, new experiment

---

### 03 Experiment Design

4-stage loop: Design (hypothesis) → Execute (API/GPU) → Iterate (adjust) → Report (structured JSON).

**IN:** conjecture or gap  
**OUT:** results.json + experiment_summary.md

#### Stage 1: Design (Most Important)
- Must answer: "which paper claim does this support?"
- Experiment spec: hypothesis, independent/dependent vars, control vars, expected results
- Statistical plan decided BEFORE running (no HARKing)
- Principles: falsifiable, minimal first, pre-registered, has control

#### Stage 2: Execute

| Path | Scale | Use Case |
|------|-------|----------|
| Path A: API | Hours, lightweight | Multi-model comparison, prompt ablation |
| Path B: GPU RL | Days, heavyweight | Agent training, reward shaping |

- API: 3-5 frontier models × 2-3 conditions × 15-25 tasks × 3 trials
- GPU: cluster job submission + auto-monitoring loop

#### Stage 3: Iterate
- Ceiling effect → increase difficulty
- Floor effect → decrease difficulty or check for bugs
- Not significant → increase trials or change hypothesis
- Surprise finding → design follow-up
- Max 5 iterations, then accept best result

#### Stage 4: Report (Data Only)
- Output: `results.json` (schema: config + results + statistics + findings)
- Output: `experiment_summary.md` (purpose, results, limitations)
- **Does NOT** produce LaTeX tables or figures — that's the Figures skill's job

---

### 04 Academic Figures & Tables

High information-density tables and vector figures. Presentation layer for all data in the paper.

**IN:** results.json + section placeholders  
**OUT:** figures/*.pdf + tables/*.tex

#### Table Types

| Type | Use | Info Density |
|------|-----|-------------|
| Comparison Matrix | Methods × features | Very high |
| Benchmark Table | Models × metrics | High |
| Ablation Table | Conditions × results | High |
| Taxonomy Table | Classification visualization | Medium |
| Meta-analysis | Aggregated cross-paper data | Very high |

#### Table Rules
- No vertical lines — booktabs three-line style only
- Alternating row color: `\\rowcolor{gray!6}`
- Bold best results in each column
- All experimental data: mean ± std
- Caption must contain key finding, not just description

#### Figure Types & Tools
- Data-driven (curves, bars, heatmaps): `matplotlib → PDF`
- Architecture/flow diagrams: TikZ or SVG→PDF
- Simple schematics: PIL → PNG (acceptable per reviewer feedback)
- Priority: TikZ > matplotlib PDF > SVG→PDF > PIL PNG

#### Quality Checklist
- Vector format (PDF) preferred, PNG ≥ 300 DPI
- Font size ≥ 10pt after scaling
- Academic palette: blue #2196F3, red #F44336, green #4CAF50, orange #FF9800
- All axes labeled, all lines have legend
- Light grid (alpha=0.3) for readability
- Self-contained: understandable without reading main text

#### Quantity Targets
- Full survey (50+ pages): ≥10 tables, ≥6 figures
- Short survey (30 pages): ≥5 tables, ≥3 figures

---

### 05 Peer Review Simulation

Multi-persona scoring that **drives the iteration loop** by routing weaknesses back to sub-skills #1-4.

**IN:** compiled PDF  
**OUT:** score + weakness list → routed to corresponding sub-skill

#### Reviewer Personas (3-5 per round)

| Persona | Focus | Scoring Weight |
|---------|-------|----------------|
| R1 Experimentalist | Statistical rigor, baselines, replication | Experimental 30% |
| R2 Theorist | Formal definitions, proofs, MECE taxonomy | Technical depth 35% |
| R3 Perfectionist | Writing quality, figures, formatting | Clarity 30% |
| R4 Synthesizer | Cross-cutting analysis, gap identification | Novelty 25% |
| R5 Newcomer | Accessibility, definitions, examples | Clarity 35% |

#### Scoring Protocol
- Each reviewer scores independently (no anchoring)
- Final score = median of all reviewers
- Dimensions: Novelty, Comprehensiveness, Clarity, Technical Depth, Experimental Validation
- Calibration: 6.0=workshop, 7.0=main conference, 8.0=Strong Accept (top 20%), 9.0=Oral

#### Anti-Inflation Rules
- First round score capped at 7.0 (every paper has room to improve)
- Max +1.5 per round
- At least 1 "unresolved" weakness must remain
- Different LLM model for at least 1 reviewer per round (diversity)

#### Output Format
- Overall score + per-dimension scores
- 3-5 Strengths, 3-5 Weaknesses (prioritized Major/Minor)
- Concrete suggestions (actionable)
- Recommendation: Accept / Weak Accept / Borderline / Reject
- Regression check: are previously-fixed weaknesses still fixed?

---

## Workflow & Phase Routing

**Phase 0: Topic Selection** (before pipeline starts)
- 3-question test: Scope? Angle? Audience?

**Phase 1: Draft** (Iter 1-6, target: 6.0/10)
- Iter 1: skeleton + §1-2 + compile
- Iter 2: Literature Stage 1-2: recall + LQS scoring
- Iter 3: §3-6 core + Figures 2+ figures
- Iter 4: Literature Stage 3-4 + §7-8
- Iter 5: verify citations → compile → Review first score
- Iter 6: route fixes → compile

**Phase 2: Deep Improvement** (Iter 7-9, target: 7.5-8.0)
- Iter 7: Experiment design + execute
- Iter 8: Figures present results + Structure integrate
- Iter 9: compile → Review → route fixes

**Phase 3: Sprint** (Iter 10+, target: 8.5+)
- Loop: Review → weakness routing → fix → compile → Review
- Stop: score ≥ 8.5 OR Δ ≤ 0.3 for 2 rounds OR iter > 12

---

## Weakness Routing Table

When peer review identifies a weakness, it routes to the responsible sub-skill:

| Reviewer Weakness | Route To | Action |
|-------------------|----------|--------|
| "Citation coverage insufficient" | Literature | Stage 1-2 targeted search |
| "Too many arXiv-only refs" | Literature | Stage 4 upgrade via DBLP |
| "Missing recent papers" | Literature | 2025-2026 focused search |
| "Structure unclear" | Structure | Reorganize + add transitions |
| "Analysis lacks depth" | Structure | Add Critical Assessment |
| "Taxonomy not novel" | Structure | Redesign multi-axis |
| "Claims too strong" | Structure | Hedge language downgrade |
| "No experiments" | Experiment | Design pilot study |
| "Experiment not rigorous" | Experiment | Add trials / ablation |
| "Tables incomparable" | Figures | Regroup + add Δ column |
| "Missing visualizations" | Figures | Add figure |
| "No error bars" | Figures | Add ± std |

---

## Quality Gates

Each sub-skill output must pass its gate before integration. Gates 1&2 can run in parallel; Gate 5 is blocking.

### Gate 1: Literature
- Citations ≥ 80 (draft) / ≥ pages×3 (final)
- Within 1yr ≥ 40%
- Accepted ≥ 30%
- arXiv-only ≤ 60%
- Verification rate ≥ 80%
- Every taxonomy cell ≥ 2 A/B refs

### Gate 2: Experiment
- Clear hypothesis pre-registered
- Statistical test reported (p or CI)
- ≥ 3 trials with std
- No ceiling/floor effect
- Links to specific paper claim
- (Bonus) Surprise finding

### Gate 3: Structure
- Compiles with 0 errors & 0 undefined refs
- Every .tex file ≤ 300 lines
- Abstract-conclusion alignment
- Inter-section transitions present
- Critical assessment in core sections
- ≥ 1 formal claim (conjecture/observation)
- Terminology consistent throughout

### Gate 4: Figures & Tables
- Tables ≥ 10, Figures ≥ 6 (full survey)
- booktabs format, no vertical lines
- Each carries a non-trivial insight
- Captions contain conclusion, not just description
- Every figure/table referenced in text
- Experimental data has mean ± std

### Gate 5: Final Review (Blocking)
- All Gates 1-4 passed
- PDF compiles cleanly
- Peer review score ≥ target (6.0/7.0/8.0/8.5 by phase)
- No regression: previously fixed weaknesses remain fixed
- Version bumped and snapshot saved

---

## Score Progression (Validated Path)

| Score | Requirements Beyond Previous | Typical Additions |
|-------|------------------------------|-------------------|
| 6.0 | Complete draft, 80+ refs, compiles | Full 8 sections + basic tables |
| 7.0 | + logical transitions, quantitative data, gap analysis | Formal conjecture + grouped tables |
| 8.0 | + original experiment, critical assessment, 150+ refs | Multi-model pilot study + vector figures |
| 8.5 | + cross-validation, meta-analysis, key takeaways, proof sketch | Cross-benchmark table + deeper theory |

---

## Production Statistics

| Sub-skill | % of Time | Score Contribution | Key Output |
|-----------|-----------|-------------------|------------|
| Literature Survey | 20% | Foundation (without: ≤6.0) | 941 total citations across 3 papers |
| Structure & Logic | 35% | Main driver (6.0→7.5) | 190 pages of manuscript |
| Experiment Design | 20% | +1.0~1.5 points | 3,300+ API calls, 9 models evaluated |
| Figures & Tables | 10% | +0.5~1.0 points | 59+ tables, 26+ figures |
| Review + Integration | 15% | Drives iteration | 14 review rounds total |

---

Source: docs/scientific_paper_writing_skill.md
