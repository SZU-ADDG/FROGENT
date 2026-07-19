---
name: optimize-small-molecule
description: Improve a small-molecule lead through interaction analysis, fragment reconstruction, bounded generation, docking, and ADMET comparison. Use when a baseline lead and explicit optimization objective are available.
---

# Optimize Small Molecule

Run a traceable lead-optimization loop while preserving the baseline.

## Required inputs

- Baseline molecule and target pocket
- Primary objective, acceptance thresholds, and immutable constraints
- Maximum candidate count and iteration limit

## Workflow

1. Use `$prepare-molecule` on the baseline and resolve every identity or stereochemistry blocker.
2. Verify the target accession/chain and bind an explicit residue or artifact pocket before calling `docking.generate-conformation`. Preserve every pose ID, artifact, score, and direction.
3. Require the user or upstream workflow to select a pose, then inspect that exact artifact with `sar.analyze`. Treat PLIP interactions as computational evidence and preserve local failures without discarding the docking poses.
4. Select a fragment for replacement only when the interaction evidence supports it.
5. Prepare the retained scaffold with `fragment.reconstruct`.
6. Generate a bounded analogue set with `ligand.generate-from-fragments`.
7. Evaluate the parent and analogues together with `docking.score` and `admet.compare` or `admet.predict`.
8. Stop when a candidate passes the thresholds, the iteration limit is reached, or no measured improvement remains.

## Output

Return a lineage table linking each analogue to its parent, changed fragment, docking result, ADMET deltas, constraint checks, and disposition. Keep the original lead in every comparison.

## Guardrails

- Default to at most two refinement rounds.
- Change one interpretable region per round when practical.
- Reject candidates that violate immutable constraints even when a score improves.
- Preserve failed candidates and explain why the workflow stopped.
- Do not invent a pocket, choose a best-scoring pose as a mechanism, or reconstruct a fragment without interaction evidence bound to the selected pose.
