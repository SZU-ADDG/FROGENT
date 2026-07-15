---
name: optimize-peptide
description: Propose and compare a small set of peptide variants against a protein target using controlled mutations and peptide docking evidence. Use when a baseline sequence and optimization goal are supplied.
---

# Optimize Peptide

Explore a small, interpretable peptide neighborhood around a baseline sequence.

## Required inputs

- Baseline peptide sequence
- Standardized target or protein structure
- Optimization objective and protected residues
- Sequence length, charge, or motif constraints

## Workflow

1. Resolve the target with `target.standardize` and obtain its structure with `protein.download` when needed.
2. Validate the baseline sequence and protected positions.
3. Propose a compact variant set, changing one to three unprotected positions per variant.
4. Score the baseline first with `peptide.docking-score`.
5. Score every variant with the same target and docking settings.
6. Compare variants to the baseline, applying sequence constraints before ranking.
7. Stop after one batch unless the user explicitly requests a second bounded round.

## Output

Return the sequence, mutations, constraint checks, docking score, score delta from baseline, and rationale for every variant. Identify the recommended variants and the main unresolved risks.

## Guardrails

- Preserve the exact residue numbering supplied by the user.
- Do not mutate protected positions.
- Keep docking scores framed as computational proxies.
- Avoid claiming affinity, selectivity, stability, or safety without supporting evidence.
