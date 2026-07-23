---
name: optimize-peptide
description: Propose and prioritize peptide sequence, terminal, side-chain, backbone, stereochemical, or conformational modifications using expert peptide-design reasoning and calibrated tools. Use when a baseline peptide and optimization goal are supplied.
---

# Optimize Peptide

Explore a small, interpretable peptide-design portfolio around a baseline sequence.

## Required inputs

- Baseline peptide sequence
- Optional standardized target or protein structure when the mechanism is target-bound
- Activity context such as membrane-active, phenotypic, intracellular, receptor-bound, or enzyme-bound
- Optimization objective and protected residues
- Sequence length, charge, or motif constraints

## Workflow

1. Classify the activity context. Use a target-bound branch only when a specific protein interaction is biologically meaningful; use a membrane, phenotypic, stability, or target-independent branch for AMPs and other peptides without one protein target.
2. Resolve a supplied target with `target.standardize` and obtain its structure with `protein.download` only for the target-bound branch. Validate the baseline sequence and protected positions in every branch.
3. Use `$prioritize-design-hypotheses` to reason about charge distribution, amphipathicity, helicity or turn propensity, protease exposure, aggregation, membrane activity, target contacts, selectivity, and manufacturability as relevant.
4. Propose a compact, diverse set. Consider substitutions and, when chemically appropriate, terminal capping, D-residues, N-methylation, cyclization or stapling, lipidation, and side-chain modifications. State exact positions and preserve protected residues.
5. For a target-bound mechanism, score the baseline first with `peptide.docking-score`, then score executable variants with the same target and settings. Use `$run-trioworkspace` for a bounded TrioPep generation arm when the exact receptor, chains, and length satisfy its contract. For membrane, phenotypic, or stability-led work, use mechanism-relevant measurements such as physiological-salt activity, serum stability, protease mapping, hemolysis, membrane leakage, aggregation, and structural response; protein docking is not a prerequisite.
6. Use applicable docking, sequence calculators, and assay data as calibration signals. Rank the full portfolio with expert peptide judgment, stated constraints, plausible developability, and experiment value.
7. Recommend the smallest wet-lab panel that separates the leading mechanisms, including activity and the most decision-relevant liability assay.
8. Stop after one batch unless the results justify a second bounded round.

## Output

Lead with the variants or modifications to make first. Return representation, exact changes, rationale, expected benefit, tradeoff, constraint checks, available scores, failure mode, and decisive assay for every design.

## Guardrails

- Preserve the exact residue numbering supplied by the user.
- Do not mutate protected positions.
- Keep docking scores framed as computational proxies and let them change priority only when they address the design rationale.
- Label expected affinity, selectivity, stability, or safety gains as design hypotheses until measured.
