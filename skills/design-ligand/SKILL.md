---
name: design-ligand
description: Design and rank small-molecule ligands for a protein pocket using generation, docking, ADMET, and optional synthesis evidence. Use for pocket-based hit generation or lead ideation.
---

# Design Ligand

Create a small, high-value candidate set through expert hypothesis generation and tool calibration.

## Required inputs

- Standardized target or protein structure
- Design objective and chemical constraints
- Optional reference ligand, pocket coordinates, and ADMET priorities

## Workflow

1. Resolve the target with `target.standardize` and obtain a structure with `protein.download` when needed.
2. Use `pocket.find` for an unknown pocket. Use `pocket.prepare` only when coordinates and dimensions are explicit.
3. Use `$prioritize-design-hypotheses` to propose three to six distinct strategies from pocket chemistry, known ligand patterns, medicinal-chemistry experience, bioisosteres, conformational control, and the stated objective. Rank what is worth making before broad scoring.
4. Generate a compact candidate batch with `ligand.generate-in-pocket`. When the private Trio contract matches the task, use `$run-trioworkspace` for exact-pocket TrioMol2 or the accepted BRD4 TrioPROTAC task. Ensure the batch represents the leading hypotheses rather than one narrow score optimum.
5. Score candidates under one docking setup with `docking.score` and predict comparable requested properties with `admet.predict`.
6. Use tool results to remove hard conflicts and rerank the portfolio. Preserve promising knowledge-led hypotheses when a proxy is unavailable or inconclusive, with adjusted confidence and a decisive experiment.
7. Run one focused refinement round when either expert analysis or calibrated evidence identifies a clear weakness.
8. Use `retrosynthesis.flash` for finalists when synthesis feasibility is part of the request.

## Output

Lead with the ranked shortlist and why each design is worth making. Then return structures, knowledge basis, docking evidence, ADMET evidence, constraint checks, tradeoffs, failure modes, and the smallest informative experiment. Explain each rejection and identify the parent candidate for every refinement.

## Guardrails

- Keep tool parameters comparable across candidates.
- Retain failed and missing measurements as explicit cells.
- Keep metric-specific comparisons restricted to compounds with comparable measurements. The overall design priority may also use explicit expert judgment and biological rationale.
- Present docking and predicted properties as computational evidence with uncertainty.
