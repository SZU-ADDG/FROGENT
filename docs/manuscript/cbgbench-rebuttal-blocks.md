# CBGBench manuscript and rebuttal blocks

Status: evidence-frozen working text for R1-3c, R3-M6, and E-4. Final section,
table, page, and line numbers remain to be assigned after manuscript layout.

## Methods insertion

We compared the three deployed manuscript-scope generators—TargetDiff,
DiffSBDD, and Pocket2Mol—on five protein pockets. The primary experiment used
three seeds and 500 attempts per model–pocket–seed cell, for 45 jobs and 22,500
generation attempts. A separately declared post-outcome replication used three
new seeds under the same protocol. The primary and replication matrices were
also pooled to assess six-seed rank stability. Validity, QED, and RDKit
synthetic-accessibility score were computed with a common evaluator. The
three-seed matrix remains the primary analysis; the six-seed result is reported
as a stability extension.

## Results insertion

All 45 primary jobs and all 45 replication jobs completed successfully. In the
primary matrix, TargetDiff produced 7,263 valid molecules from 7,500 attempts
(valid rate 0.968), compared with 1,809 for DiffSBDD (0.241) and 753 for
Pocket2Mol (0.100). Mean job QED was 0.458, 0.234, and 0.128, respectively.
Mean raw RDKit SA was 5.168 for TargetDiff, 5.631 for DiffSBDD, and 5.149 for
Pocket2Mol, where lower values indicate easier predicted synthesis.

The relative ranking was retained in the independent three-seed replication
and the pooled six-seed analysis: validity and QED ranked TargetDiff above
DiffSBDD above Pocket2Mol, while synthetic accessibility ranked Pocket2Mol
above TargetDiff above DiffSBDD. Primary-versus-pooled model–pocket Spearman
correlations were 0.993 for valid rate, 0.971 for QED, and 0.704 for SA.
TargetDiff's pooled valid rate and QED were 0.949 and 0.408, compared with
0.968 and 0.458 in the primary matrix. The extension-minus-primary
pocket-cluster 95% confidence intervals were -0.188 to -0.004 for QED and
-0.073 to -0.006 for valid rate. We therefore retain the relative model
ranking and disclose seed-sensitive absolute performance, with the largest
pocket shifts occurring for TargetDiff on 2HYY and 3CS9.

Of 9,825 primary generated SDF files, 9,767 molecules were parsed and 58
candidate-level parse failures were retained. TargetDiff, DiffSBDD, and
Pocket2Mol identity uniqueness was 1.000, 1.000, and 0.965; unique-scaffold
density was 0.997, 0.866, and 0.458. Mean same-pocket reference-ligand ECFP4
similarity was 0.093, 0.065, and 0.055. All three models had a 1.000
10-Å pocket-compatibility rate. Severe-clash-free rates were 1.000, 0.942,
and 0.996, with a DiffSBDD minimum of 0.854 on pocket 1M17.

Against frozen target-matched ChEMBL 37 strong-active collections, all 9,767
parsed molecules had nearest-neighbor ECFP4 similarity below 0.5. Exact
active-scaffold overlap occurred in 2/7,253 TargetDiff, 0/1,771 DiffSBDD, and
1/743 Pocket2Mol molecules. Against the versioned executable CrossDocked
training proxy, no generated molecule had exact canonical identity. Exact
proxy-scaffold overlap was 0.772%, 7.510%, and 15.612%, respectively. These
comparisons support low identity and generally low fingerprint similarity to
the frozen collections while requiring explicit disclosure of model-specific
scaffold reuse.

## Main or supplementary table

| Generator | Primary valid / attempts | Primary valid rate | Mean job QED | Mean raw RDKit SA | Identity uniqueness | Unique-scaffold density | Severe-clash-free rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| TargetDiff | 7,263 / 7,500 | 0.968 | 0.458 | 5.168 | 1.000 | 0.997 | 1.000 |
| DiffSBDD | 1,809 / 7,500 | 0.241 | 0.234 | 5.631 | 1.000 | 0.866 | 0.942 |
| Pocket2Mol | 753 / 7,500 | 0.100 | 0.128 | 5.149 | 0.965 | 0.458 | 0.996 |

| Stability metric | Primary-to-pooled result |
| --- | --- |
| Valid-rate model–pocket Spearman correlation | 0.993 |
| QED model–pocket Spearman correlation | 0.971 |
| SA model–pocket Spearman correlation | 0.704 |
| TargetDiff valid rate | 0.968 primary; 0.949 pooled |
| TargetDiff QED | 0.458 primary; 0.408 pooled |

## Point-by-point response: R3-M6

We added a matched, multi-seed comparison of every deployed generator within
the manuscript scope. TargetDiff, DiffSBDD, and Pocket2Mol each completed 15
primary jobs and 15 independent replication jobs under identical pocket,
attempt, and evaluator settings. TargetDiff had the highest valid rate and QED
in the primary, replication, and pooled analyses; Pocket2Mol had the easiest
SA profile. The pooled six-seed analysis retained the model ranking, with
primary-to-pooled correlations of 0.993 for validity, 0.971 for QED, and 0.704
for SA. We will report the original three-seed matrix as primary and the pooled
analysis as a stability extension, including the observed seed and pocket
sensitivity of absolute values.

## Point-by-point response: R1-3c and E-4

We added explicit structural-diversity, pocket-geometry, known-active, and
declared-training-proxy analyses for all 9,767 parsed primary molecules.
Identity uniqueness ranged from 0.965 to 1.000, and no molecule had exact
canonical identity to the executable CrossDocked training proxy. All molecules
were below 0.5 ECFP4 similarity to the frozen ChEMBL target-matched strong
actives. We also report model-specific scaffold overlap, including 15.612% for
Pocket2Mol against the training proxy, and the DiffSBDD 1M17 clash signal.
These additions support collection-specific diversity and pocket-compatibility
claims. Novelty relative to undisclosed checkpoint training, pretraining,
fine-tuning, or other databases remains outside the measured scope.

## Failure accounting and evidence boundary

- Primary, replication, and pooled matrices contain 45/45, 45/45, and 90/90
  completed jobs.
- The primary molecule analysis retained 58 parse failures among 9,825 SDFs.
- Reconstruction errors were low-frequency AtomValenceException events; the
  largest cell rate was 11/1,500 (0.73%) for replication DiffSBDD–3CS9.
- QED and SA are molecular design descriptors and do not establish biological
  activity.
- Pocket compatibility and clash metrics do not establish binding affinity.
- ChEMBL and CrossDocked conclusions apply to the frozen versions and filters
  described above.

## Frozen evidence

- Commit: `7070ce0`
- Run: `runtime/evaluation/revision-20260731/gpu-final/cbgbench/`
- Final manifest: `runtime/evaluation/revision-20260731/gpu-final/cbgbench/final-manifest.json`
- Remote run: `/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260801/cbgbench-seed-extension-resume-r01/`
- Remote final manifests: `final-manifest.json` and `combined-six-seed-manifest.json`
- Remote run: `/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260802/cbgbench-six-seed-stability-r01/`
- Supporting final runs: `cbgbench-novelty-pocket-r01`,
  `cbgbench-known-active-neighbors-r03`, and
  `cbgbench-crossdocked-training-proxy-r04`
