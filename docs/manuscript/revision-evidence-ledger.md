# FROGENT major-revision evidence ledger

Date: 2026-07-31

CPU-only run root: `runtime/evaluation/revision-20260730/nongpu-final/`

GPU/provider run root: `runtime/evaluation/revision-20260731/gpu-final/`

Source commits: CPU final `4a3daabc30673ad9258d964c8d8dca71b89b6f48`; GPU execution base `8174bf3`

This ledger maps reviewer concerns to completed evidence, the claim that the evidence can support,
and the planned manuscript destination. A `not_measured` result is an explicit boundary and must
remain visible in the response letter.

| Concern | Evidence | Result | Claim disposition | Destination |
|---|---|---|---|---|
| E-3, R1-2, R1-8a | `semantic-adjudication/`, `manuscript-qa/` | 28 exposed mismatches double judged; agreement 22/28; Cohen’s κ 0.647; exact McNemar, paired tests, bootstrap, Holm and effect-size runner validated | Separate dataset-exact scoring from semantic adjudication; recompute headline statistics after sample-level outputs arrive | M-BENCH, M-STAT, T-1, SI-3, SI-4 |
| R1-8a, R3-M1 | `hle-text-subset/` | Official access is contact-sharing gated; 24 metadata candidates met the frozen text-only allowlist; complete 20-case content unavailable | Report the access and selection protocol; HLE performance remains `not_measured` until authorized cases are supplied | M-BENCH, F-3, SI-3 |
| R1-8b | `molecular-properties/` | RDKit QED reproduced deterministically for 11 traceable records | Present QED as a calculated descriptor and remove it from predictive-accuracy language | M-BENCH, M-RES, T-1 |
| R1-8d | `molecular-properties/` | RDKit SA uses 1 as easier synthesis and 10 as harder synthesis | Correct the direction in text, tables and figures; recompute affected results with the original scorer | M-BENCH, M-RES, F-3, SI-4 |
| E-4, R3-M4 | `matched-resource/`, `real-agent-ablation/` | 130/130 worker outputs completed. Full context scored 9.367/10; paired differences versus direct, single and no-context were 0.067, 0.033 and 0.167. The no-context CI was [0.000, 0.333] | Report a small context signal on this panel; avoid a broad superiority claim; disclose that multi-agent arms use three workers | M-ARCH, M-RES, T-2, SI-4, SI-5 |
| R3-M5a, R3-M5b | `real-agent-ablation/` | Removing Retrieve reduced five retrieval cases by 7.000/10, CI [5.200, 8.500]; removing Gauge reduced five design cases by 0.800/10, CI [0.000, 1.600] | Support Retrieve as essential on the tested retrieval cases and Gauge as a smaller design-quality signal with boundary-touching uncertainty | M-RES, T-2, SI-4 |
| R3-m1 | `real-agent-ablation/results/repeat-variation.json` | Five stratified repeats per main arm; success agreement 80–100%; full-context mean absolute score change 0.500 | Report run variation and model-runtime fields that were unavailable; avoid single-run architecture conclusions | M-ARCH, M-RES, SI-4 |
| R3-M2a | `structured-retrieval/`, `luteolin-comparison/` | Open Targets and UniProt direct/typed arms completed 24 live calls; literature-only arms retained; DrugBank direct returned 403 | Separate structured-resource availability from orchestration performance; keep DrugBank direct as `not_measured` | M-BENCH, M-RES, T-2, SI-4 |
| R3-M2b, R3-M3 | `live-evidence/`, `evidence-propagation/` | 8 live tasks were repeat-stable; 7/8 mechanical gates passed; 4/4 propagation cases passed; unsupported carry-through and revoked leakage were 0 | Support retrieval provenance, conflict retention, revocation and recovery; retain the ACTT-1 temporal-version failure | M-ARCH, M-RES, SI-4, SI-5 |
| R1-3a, R1-3b, R1-3d | `luteolin-comparison/` | Luteolin identifiers and PMID 36998980 are traceable; fixed/literature/structured-proxy scores were 1.4, 1.8 and 2.0 of 2.0 | Label Luteolin as a known candidate with preclinical PPARγ mechanism evidence; avoid clinical-efficacy language | M-RES, M-DISC, SI-4 |
| R1-8c, R2-3a | `davis-screening/` | Direct Vina and FROGENT wrapper matched exactly for 10 ABL1 ligands; Spearman ρ 0.115, p 0.751 against DAVIS affinity ranking | Claim reliable tool execution; disclose that uncalibrated docking score is a weak affinity discriminator in this panel | M-RES, M-DISC, T-2, T-3 |
| R1-5c | `pose-plip/` | Seven-pose raw/local/redocking panel showed low crystal RMSD for seed 17 and repeatable loss of the ASP381 salt bridge at seeds 23/31 | Retain redocking as a stability and interaction-sensitivity analysis; avoid presenting a single score as conclusive | M-CONF, M-RES, T-3, SI-4 |
| R1-5a, R2-3b | `multitarget-docking/` | 12/15 poses had RMSD ≤2 Å; EGFR 1M17 failed stably at 5.886 Å with PLIP recall 0.167 | Report success and failure by complex; include the stable alternate-pose failure in error attribution | M-CONF, M-RES, T-3, SI-4 |
| R2-3b | `plip-parser-baseline/` | Direct and adapter XML matched 12/12; typed end-to-end exact rate was 0.667; metal and water-bridge fields are schema gaps | Keep parser fail-closed behavior and disclose unsupported interaction classes | M-TOOLS, M-RES, SI-1, SI-4 |
| R1-5b, R1-9d/e | `glp1r-peptide-audit/` | 4ZGM provenance, missing residues, interface geometry and sequence chemistry audited; figure/text inconsistencies identified | Correct the figure, sequence chemistry and source description; full peptide-docking performance awaits the actual provider/model | M-CONF, M-RES, T-3, SI-1 |
| R1-6, E-5 | `gpu-final/live-weighted-mcp/` | Three repeats completed 39/39 typed live calls; every repeat had 10/10 nonempty target-rooted RDKit-valid retrosynthesis calls and 15/15 valid FragGen molecules; 12/13 call definitions had identical text across all repeats; DirectMultiStep route-set and FragGen molecule-set mean pairwise Jaccard were 0.973 and 1.000 | Support current provider executability, parse validity and within-panel stability; retain original manuscript retrosynthesis accuracy as `not_measured` | M-TOOLS, M-RES, SI-1, SI-4 |
| R1-5b, R1-9d/e | `gpu-final/mdockpep2/` | Three read-only historical glucagon runs contained 25,000 scores and 3,000 retained models; none reached native-frame CA RMSD ≤2 Å and best superposed CA RMSD was 2.721 Å | Report the provider trace and negative structural audit; remove any unsupported near-native docking-performance implication | M-CONF, M-RES, M-DISC, T-3, SI-4 |
| R1-9e, R1-9f | `gpu-final/provider_inventory.json` | The two declared production roots contain MDockPeP2 but no HADDOCK, pepATTRACT or rDock installation, endpoint or checkpoint; MDockPeP2 prospective isolation lacks an authorized Modeller license | Keep the verified retrospective MDockPeP2 evidence; remove unverified HADDOCK, pepATTRACT, rDock and live RNA–ligand capability claims | M-TOOLS, F-1, SI-1 |
| R2-1b, R2-4 | `telemetry/` | 70 per-run records and 49 valid summary rows cover wall time, CPU, RSS and calls; token, queue and energy fields are unavailable | Report measured CPU/live-provider resource data and mark unavailable telemetry as `not_measured` | M-RES, M-DISC, SI-4 |
| R1-9c | `safety-contract/` | 23/23 contract cases passed, including refusals, degradation, recovery, provenance and synthetic-secret leakage | Describe the tested safety boundary and limit effectiveness claims to the preregistered matrix | M-TOOLS, M-DISC, SI-1, SI-4 |
| R1-4a/b/c | `recent-baselines/` | CLADD, Prompt-to-Pill and Robin mapped; fair numerical reproduction is unavailable; one public implementation had a compile failure | Add the systems to Related Work and the capability matrix; remove global priority claims; keep score comparison `not_measured` | M-INT, M-DISC, T-2, SI-1 |
| R2-3a, R2-3c | `admet-cpu/`, `molecular-properties/` | ADMET-AI completed 18/18 workflows across 41 endpoints; all deterministic repeats matched; invalid inputs failed before prediction | Separate model prediction, deterministic descriptors and validation failures in the benchmark table | M-BENCH, M-RES, T-1, SI-4 |
| E-5, R1-6, R2-2 | CPU and GPU/provider manifests | CPU/live paths, weighted providers, running GPU studies, parser gaps and unavailable source inputs are explicitly classified | Align manuscript capability statements with final terminal states and preserve every `not_measured` boundary | M-TOOLS, F-1, SI-1 |

## Inputs still required for manuscript-level recomputation

- Eight benchmark sample-level outputs, case IDs, seeds, failure rows and scorer code.
- Original HLE and retrosynthesis samples, rubric, judge records and adjudication decisions.
- Original QED/SA values and the implementation used to generate the submitted figures.
- Production model/provider configuration for de novo generation and peptide/RNA docking.
- Author confirmation of fine-tuning, few-shot examples, cache policy and test-set overlap.

These missing inputs constrain the affected headline claims. They do not invalidate the completed
CPU experiments, negative results, access audits or reproducibility evidence listed above.
