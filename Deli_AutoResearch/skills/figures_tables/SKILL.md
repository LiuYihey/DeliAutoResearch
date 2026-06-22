---
name: figures_tables
description: High-density booktabs tables and vector figures from results.json.
parent: paper-writing
---

# Academic Figures & Tables

**IN:** `paper/results.json`, section placeholders  
**OUT:** `paper/figures/*`, `paper/tables/*.tex`

## Tables
- booktabs only — no vertical lines
- `\rowcolor{gray!6}` alternating rows
- Bold best per column; mean ± std for experiments
- Caption = key finding, not description only

## Figures
- matplotlib → PDF for data plots
- TikZ / SVG for architecture diagrams
- Palette: #2196F3, #F44336, #4CAF50, #FF9800; font ≥ 10pt

## Targets (full survey)
- ≥10 tables, ≥6 figures
- Every figure/table referenced in text

## Validation
```bash
python tools/check_gates.py <task_dir>
python tools/compile_paper.py <task_dir>/paper
```
