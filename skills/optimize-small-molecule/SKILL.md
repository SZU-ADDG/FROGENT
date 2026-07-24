---
name: optimize-small-molecule
description: Improve a small-molecule lead through interaction analysis, fragment reconstruction, bounded generation, docking, and ADMET comparison. Use when a baseline lead and explicit optimization objective are available.
---

# Optimize Small Molecule

Run a knowledge-led, tool-calibrated lead-optimization loop while preserving the baseline.

## Required inputs

- Baseline molecule and target pocket
- Primary objective, acceptance thresholds, and immutable constraints
- Maximum candidate count and iteration limit

## Workflow

1. Use `$prepare-molecule` on the baseline and resolve every identity or stereochemistry blocker.
2. Use `$prioritize-design-hypotheses` to create three to six interpretable modifications from the objective, baseline liabilities, target biology, known SAR, medicinal-chemistry heuristics, and plausible mechanism. Include conservative, mechanism-led, and orthogonal options when chemistry permits.
3. Verify the target accession/chain and bind an explicit residue or artifact pocket before calling `docking.generate-conformation`. Preserve every pose ID, artifact, score, and direction.
   With pH-aware tools, show the bounded ligand states and require an exact current-message state ID or SMILES plus receptor pH before conformer, Meeko, Vina, or PLIP execution. Carry both selected state IDs and receptor pH/force field through every result.
4. Require one explicit current-message pose ID or pose rank, resolve rank to the generated ID/artifact from that docking run, then inspect that exact artifact with `sar.analyze`. Treat PLIP interactions as computational evidence and preserve local failures without discarding the docking poses.
5. Select fragment changes from the ranked design rationale. Use bound interaction evidence when executing `fragment.reconstruct`; keep chemically plausible conceptual hypotheses available when interaction tooling cannot judge them.
6. Prepare the retained scaffold with `fragment.reconstruct` and generate a bounded analogue set with `ligand.generate-from-fragments`. Use `$run-trioworkspace` for a bounded TrioMol2 generation arm when the exact receptor and verified pocket satisfy its contract.
7. Evaluate the parent and analogues together with `docking.score` and `admet.compare` or `admet.predict`.
8. Rerank using the biological objective, medicinal-chemistry rationale, literature precedent, computational signals, hard constraints, and experiment value.
9. Stop when a candidate passes the thresholds, the iteration limit is reached, or the remaining hypotheses no longer justify another synthesis batch.

## Output

Lead with what to make first and why. Return a lineage table linking each analogue to its parent, changed fragment, rationale, expected benefit, tradeoff, docking result, ADMET deltas, constraint checks, failure mode, decisive experiment, and disposition. Keep the original lead in every comparison.

## Guardrails

- Default to at most two refinement rounds.
- Change one interpretable region per round when practical.
- Reject candidates that violate immutable constraints even when a score improves.
- Preserve failed candidates and explain why the workflow stopped.
- Do not invent a pocket, choose a best-scoring pose as a mechanism, or reconstruct a fragment without interaction evidence bound to the selected pose.
