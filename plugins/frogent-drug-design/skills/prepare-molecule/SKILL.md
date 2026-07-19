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
5. Follow the returned ordered capability plan and surface every blocker. Each step must carry the exact candidate structure, candidate/baseline role order, any normalized baseline, and known target/pocket identifiers. Before docking, require an explicit RCSB-verified PDB target plus auth chain and an exact pocket binding with target artifact, residue or reference-ligand identity, and derived box provenance. UniProt or a protein name remains unverified until an exact structure mapping is supplied. Require a baseline for molecular comparison. For PLIP, require one exact current-message pose ID or rank and bind the resolved generated pose artifact before interaction analysis or fragment reconstruction.
   With configured project-contained tools, generate the exact selected single-fragment ligand from canonical isomeric SMILES using deterministic RDKit 3D preparation, verify its InChIKey again, and pass the resulting SDF to Meeko. Select one explicit auth chain from the current verified target artifact, remove the exact reference ligand and configured waters/components under a recorded policy, and fail on every unapproved cofactor, metal, interrupted residue, or identity drift before Vina. Preserve tool versions, commands, component counts/identities, sources, outputs and exact box lineage. Bind exact pre-existing prepared artifacts only when their equivalent provenance is available.
   For pH-aware docking, enumerate a bounded explicit ligand pH window and receptor pH state. Show each ligand state ID, canonical SMILES, charge, and pH window; require one exact current-message state ID or SMILES plus an explicit receptor pH. Preserve ligand and receptor state IDs, PQR charge artifact, force field, and pH through Meeko, Vina, and PLIP. Missing or ambiguous selection blocks execution.
6. For a ready `admet.predict` or `admet.compare` step, call the FROGENT ADMET workflow with the exact bound candidate and baseline. Preserve candidate-then-baseline order and request only supported endpoint IDs. The default panel is `HIA_Hou`, `Bioavailability_Ma`, `Solubility_AqSolDB`, `Caco2_Wang`, `BBB_Martins`, `PPBR_AZ`, `Clearance_Hepatocyte_AZ`, `CYP3A4_Veith`, `hERG`, `AMES`, and `DILI`.
   In chat, copy every candidate, baseline, and explicitly selected structure from the current user message exactly. Ask for clarification when the requested molecule or full/parent scope is ambiguous; never invent a name, SMILES, or fragment selection.
7. Keep ADMET, docking, protomer/tautomer enumeration, receptor pKa assignment, retrosynthesis, and SAR outputs labeled as computational predictions. Use screened literature for experimental evidence. Preserve model/import failures and identity gaps alongside the executable intake for recovery.

## Output

Return the original and normalized identities, parent candidate and removed fragments, symmetric candidate/baseline retrieval terms, ordered capability steps with exact molecular inputs, blockers, warnings, unresolved selections, and any typed computational evidence.
