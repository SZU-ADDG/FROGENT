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

1. Use `$prepare-molecule` for every small-molecule input; preserve original order and identity warnings.
2. Split small molecules and peptides into separate evaluation groups.
3. Bind one verified target structure and pocket to every small-molecule docking input. Preserve RCSB accession, auth chain, target artifact, residue or reference-ligand identity, deterministic Å box and margin, exact molecular scope, provider configuration, pose ID, score name, and score direction. Require the dynamically prepared ligand/receptor identities and Vina box to equal these bindings; keep explicit receptor component decisions in the tool evidence. Use `docking.generate-conformation` when pose artifacts are required, then `docking.score` under identical parameters.
4. Score peptides with `peptide.docking-score` under identical parameters.
5. Use the FROGENT ADMET executor for a ready `admet.predict` or `admet.compare` step. Keep the exact bound structures and candidate-then-baseline roles, report each requested endpoint value and candidate-minus-baseline delta, and retain missing or failed endpoints.
   For app chat requests, return the bound scope, canonical isomeric SMILES, and InChIKey for every arm. A failed identity check or model call returns these safe partial inputs and coverage gaps without a synthetic score.
6. Interpret endpoint values within their model-specific task definitions and uncertainty. Do not combine endpoint directions into an unsupported total score.
7. Apply user thresholds after collecting results, keeping failed calls visible.
8. Rank only candidates with comparable evidence and explain every tie-breaker.

## Output

Return one table per evaluation group with inputs, scores, properties, threshold outcomes, warnings, and missing values. Add a short decision summary and identify experiments that would reduce the main uncertainty.

## Guardrails

- Never substitute an absent score with zero.
- Do not compare results produced with different targets, pockets, or scoring settings.
- Keep computational predictions distinct from experimental measurements.
- Treat docking scores as ranking signals. Do not call them binding affinity or experimental evidence. Run `sar.analyze` only on an explicit current-message pose ID or pose rank; resolve a requested rank to the generated pose ID/artifact from that same docking run and report both. Keep a PLIP failure local and never turn the lowest score into a validated mechanism.
- Report tool errors without inventing replacement values.
