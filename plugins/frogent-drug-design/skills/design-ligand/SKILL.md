---
name: design-ligand
description: Design and rank small-molecule ligands for a protein pocket using generation, docking, ADMET, and optional synthesis evidence. Use for pocket-based hit generation or lead ideation.
---

# Design Ligand

Create a small, evidence-backed candidate set with bounded refinement.

## Required inputs

- Standardized target or protein structure
- Design objective and chemical constraints
- Optional reference ligand, pocket coordinates, and ADMET priorities

## Workflow

1. Resolve the target with `target.standardize` and obtain a structure with `protein.download` when needed.
2. Use `pocket.find` for an unknown pocket. Use `pocket.prepare` only when coordinates and dimensions are explicit.
3. Generate a compact candidate batch with `ligand.generate-in-pocket`.
4. Score all candidates under one docking setup with `docking.score`.
5. Predict the same requested properties for every retained candidate with `admet.predict`.
6. Run one focused refinement round only when the evidence identifies a clear weakness.
7. Use `retrosynthesis.flash` for finalists when synthesis feasibility is part of the request.

## Output

Return structures, docking evidence, ADMET evidence, constraint checks, and a ranked shortlist. Explain each rejection and identify the parent candidate for every refinement.

## Guardrails

- Keep tool parameters comparable across candidates.
- Retain failed and missing measurements as explicit cells.
- Avoid ranking compounds on a metric that was unavailable for part of the set.
- Present docking and predicted properties as computational evidence with uncertainty.
