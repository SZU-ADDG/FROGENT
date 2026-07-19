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
   When PubChem is available, resolve the exact selected InChIKey or supplied name, require local RDKit identity agreement, and attach only the verified PubChem title and CID. Keep provider failures as coverage gaps.
5. Follow the returned ordered capability plan and surface every blocker. Each step must carry the exact candidate structure, candidate/baseline role order, any normalized baseline, and known target/pocket identifiers. Require target and pocket for docking, a baseline for molecular comparison, and interaction evidence for fragment reconstruction.
6. For a ready `admet.predict` or `admet.compare` step, call the FROGENT ADMET workflow with the exact bound candidate and baseline. Preserve candidate-then-baseline order and request only supported endpoint IDs. The default panel is `HIA_Hou`, `Bioavailability_Ma`, `Solubility_AqSolDB`, `Caco2_Wang`, `BBB_Martins`, `PPBR_AZ`, `Clearance_Hepatocyte_AZ`, `CYP3A4_Veith`, `hERG`, `AMES`, and `DILI`.
7. Keep ADMET, docking, retrosynthesis, and SAR outputs labeled as computational predictions. Use screened literature for experimental evidence. Preserve model/import failures and PubChem gaps alongside the executable intake for recovery.

## Output

Return the original and normalized identities, parent candidate and removed fragments, symmetric candidate/baseline retrieval terms, ordered capability steps with exact molecular inputs, blockers, warnings, unresolved selections, and any typed computational evidence.
