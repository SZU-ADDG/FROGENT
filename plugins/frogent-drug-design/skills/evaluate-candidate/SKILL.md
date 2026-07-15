---
name: evaluate-candidate
description: Evaluate small molecules or peptides against a target with comparable docking and property evidence. Use to rank candidates, compare a proposal with a baseline, or explain failed candidates.
---

# Evaluate Candidate

Produce a fair comparison from a consistent evaluation setup.

## Required inputs

- Candidate structures or peptide sequences
- Target and pocket context
- Baseline candidate when available
- Requested endpoints and decision thresholds

## Workflow

1. Validate candidate identifiers and keep the original input order.
2. Split small molecules and peptides into separate evaluation groups.
3. Score small molecules with `docking.score` under identical parameters.
4. Score peptides with `peptide.docking-score` under identical parameters.
5. Use `admet.predict` for a single molecule or `admet.compare` for a pair when requested.
6. Apply user thresholds after collecting results, keeping failed calls visible.
7. Rank only candidates with comparable evidence and explain every tie-breaker.

## Output

Return one table per evaluation group with inputs, scores, properties, threshold outcomes, warnings, and missing values. Add a short decision summary and identify experiments that would reduce the main uncertainty.

## Guardrails

- Never substitute an absent score with zero.
- Do not compare results produced with different targets, pockets, or scoring settings.
- Keep computational predictions distinct from experimental measurements.
- Report tool errors without inventing replacement values.
