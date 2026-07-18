---
name: prepare-molecule
description: Normalize a user-supplied small-molecule SMILES, create exact identity retrieval terms, and route literature, ADMET, docking, retrosynthesis, or fragment/SAR tools with explicit prerequisites. Use before any small-molecule search, comparison, prediction, or structure-based workflow.
---

# Prepare Molecule

Normalize identity before retrieving evidence or choosing chemistry tools.

## Workflow

1. Preserve the literal submitted SMILES and normalize it through the FROGENT molecular intake runtime.
2. Inspect canonical identities, fragments, charge, and assigned or unresolved stereocenters. Keep salts and mixtures intact.
3. Treat any largest-organic-fragment parent as a derived candidate. Report every removed fragment. Bind downstream steps to either the exact full structure or an exact selected parent fragment. For multiple organic fragments, require the selected canonical fragment identity; a generic confirmation cannot choose it.
4. Search literature with verified canonical SMILES, InChIKey, and InChI. Use formula as a broad supplemental term. Require an external resolver before assigning a chemical name.
5. Follow the returned ordered capability plan and surface every blocker. Each step must carry the exact candidate structure, candidate/baseline role order, any normalized baseline, and known target/pocket identifiers. Require target and pocket for docking, a baseline for molecular comparison, and interaction evidence for fragment reconstruction.
6. Keep ADMET, docking, retrosynthesis, and SAR outputs labeled as computational predictions. Use screened literature for experimental evidence.

## Output

Return the original and normalized identities, parent candidate and removed fragments, symmetric candidate/baseline retrieval terms, ordered capability steps with exact molecular inputs, blockers, warnings, and unresolved selections.
