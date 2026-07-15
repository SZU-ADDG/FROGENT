---
name: discover-target
description: Discover and standardize disease-associated protein targets with known ligands. Use when a drug-design request starts from a disease, phenotype, target alias, or target shortlist.
---

# Discover Target

Build a traceable target shortlist before starting structure-based design.

## Required inputs

- Disease or phenotype term
- Optional target aliases, organism, and selection constraints
- Whether a protein structure is needed for the next workflow

## Workflow

1. Normalize the disease term and record unresolved ambiguity.
2. Use `target.discover` for a focused target-and-ligand result.
3. Use `target.list-by-disease` when the request needs a broader shortlist.
4. Resolve every retained target with `target.standardize`.
5. Use `drug.list-by-target` to collect known ligands for the finalists.
6. Use `protein.download` only when a downstream structural workflow needs a file.
7. Rank targets using the available association evidence, ligand evidence, structure availability, and user constraints.

## Output

Return a compact table with the standardized target, identifiers, supporting evidence, known ligands, structure availability, and selection rationale. Separate the recommended target from viable alternatives. State unresolved aliases and missing evidence.

## Guardrails

- Preserve source identifiers exactly.
- Do not infer a disease-target or target-ligand relationship that a tool did not return.
- Treat an empty tool result as missing evidence.
- Ask for clarification when two standardized targets remain equally plausible.
