# Canonical manuscript edit map

Date: 2026-08-05

Source audited: `docs/manuscript/Arxiv_FROGENT_20251217.zip` (`main.tex` and
`sup.tex`). Line numbers below refer to the files inside that immutable archive. This map converts
the frozen revision evidence into concrete source edits; final page and line numbers will be
assigned after the revised manuscript is built.

## P0 claim corrections

| Source | Line | Current claim or problem | Required edit | Evidence block |
|---|---:|---|---|---|
| `main.tex` | 39 | Abstract claims consistent superiority across eight benchmarks, substantial efficiency/accuracy gains, generalization, and replacement of manual intervention. | Replace the benchmark and conclusion sentences with measured task-level results. Retain tool execution, retrieval ablations and matched-budget feedback allocation. Remove generalized superiority, efficiency, generalization and human-replacement claims. | `benchmark-corrections-rebuttal-blocks.md`; `architecture-retrieval-rebuttal-blocks.md`; `resource-efficiency-rebuttal-blocks.md` |
| `main.tex` | 51 | Introduction claims a paradigm-level advance, consistent substantial superiority, global priority and truly autonomous discovery. | Replace with the scoped contribution statement from Reviewer 1 comment 4. Remove the global `first` and priority language. Add Prompt-to-Pill, CLADD and Robin before the contribution paragraph. | `reviewer1-comments-3-4-rebuttal-blocks.md` |
| `main.tex` | 90, 94–98 | Figure caption and Results present all submitted eight-task headline values as validated superiority. | Replace with the benchmark-disposition table and post-hoc exposed results. Submitted headline reproduction, official HLE performance and cross-system numerical ranking remain `not_measured`. Report Luna/max 9/20 only as an exposed no-tool model-boundary panel. | `benchmark-corrections-rebuttal-blocks.md`; `provider-claim-matrix.md` |
| `main.tex` | 110–112, 117 | Luteolin is described as rediscovered, experimentally efficacious, and evidence for novel discovery; Compound (a) is called novel and superior using computational metrics. | Describe Luteolin as a known-candidate retrieval and evidence-integration example with preclinical PPARγ evidence. Replace efficacy and rediscovery language. Describe Compound (a) as a generated candidate prioritized by the reported computational signals; preserve affinity and experimental validation as unmeasured. | `reviewer1-comments-3-4-rebuttal-blocks.md`; `cbgbench-rebuttal-blocks.md` |
| `main.tex` | 127, 132 | Peptide scores are treated as binding affinity and superiority over approved agonists. | Replace with the ADCP, ESMFold and AF3 structural evidence and provider-disagreement result. Treat MDockPeP2 history as negative evidence and prospective accuracy as `not_measured`. Remove potency and binding-affinity ranking language. | `peptide-workflow-rebuttal-blocks.md` |
| `main.tex` | 162 | Related Work states that no unified end-to-end framework exists. | Replace with the source-grounded comparison of Prompt-to-Pill, CLADD and Robin. Position FROGENT by its evaluated workflow combination and explicit failure accounting. | `reviewer1-comments-3-4-rebuttal-blocks.md` |
| `main.tex` | 179–182 | Conclusion asserts superior performance over less integrated systems and potential reductions in time and cost. | Summarize only measured retrieval, tool-use, generation-ranking and feedback-allocation results. Remove broad external superiority and time/cost reduction claims. | `provider-claim-matrix.md`; `resource-efficiency-rebuttal-blocks.md` |

## Methods and capability corrections

| Source | Line | Current claim or problem | Required edit | Evidence block |
|---|---:|---|---|---|
| `main.tex` | 194 | Retrieve Agent lists DrugBank as an active structured source without a verified direct run. | Separate verified Open Targets/UniProt paths from DrugBank. State that direct DrugBank access returned 403 in the tested configuration and that DrugBank-specific performance is `not_measured`. | `architecture-retrieval-rebuttal-blocks.md`; `provider-claim-matrix.md` |
| `main.tex` | 197 | Forge Agent lists DiffBP, MolCRAFT, DecompDiff and PocketFlow as active generators. | Restrict the evaluated generator list to TargetDiff, Pocket2Mol and DiffSBDD. Mark the remaining providers deferred or remove them from active capability wording because executable checkpoints were not verified. | `cbgbench-rebuttal-blocks.md`; `revision-evidence-ledger.md` |
| `main.tex` | 200 | Gauge Agent states that docking predicts binding affinity and lists MDockPeP2 as an active peptide path. | Define docking as a computational ranking/geometry signal. Report ADCP as the completed peptide reference-redocking path and MDockPeP2 as an audited provider with a blocked prospective endpoint. | `peptide-workflow-rebuttal-blocks.md`; `provider-claim-matrix.md` |
| `main.tex` | 299; `sup.tex` | 35 | The supplied foundational task is identified as HLE without source/version/license and original judge records. | Name it `Foundational Biomedical Knowledge` in the post-hoc panel. Keep official HLE identity and submitted-score reproduction `not_measured` pending author source materials. | `benchmark-corrections-rebuttal-blocks.md`; `eight-task-source-intake.md` |
| `main.tex` | 308–313; `sup.tex` | 47 | QED is pooled with model-dependent ADMET endpoints under one aggregate accuracy. | Report QED as a deterministic RDKit descriptor and report each ADMET endpoint separately with its own metric. Remove reconstruction of the submitted 79.06 aggregate. | `benchmark-corrections-rebuttal-blocks.md` |
| `main.tex` | 315–316 | Virtual screening describes 10 random molecules per case and a validated affinity winner without exposing invalid inputs or score limitations. | Report attempted, valid and failed inputs at the case level. Add the DAVIS/Vina rank-correlation result and limit the conclusion to tool execution because the score was a weak affinity discriminator. | `benchmark-corrections-rebuttal-blocks.md`; `error-attribution-rebuttal-blocks.md` |
| `main.tex` | 318–319 | PLIP ground truth and all five interaction types are presented as uniformly supported. | Report 12/12 direct XML/adapter agreement and 0.667 typed end-to-end exactness. Mark metal and water-bridge schema classes as unsupported. | `error-attribution-rebuttal-blocks.md`; `provider-claim-matrix.md` |
| `main.tex` | 321–322; `sup.tex` | 64 | Higher SA is treated as better synthetic accessibility. | Reverse the SA direction: lower SA is easier. Recompute or withdraw every submitted aggregate that used the incorrect direction. Keep QED/SA as design descriptors rather than biological-activity evidence. | `benchmark-corrections-rebuttal-blocks.md` |
| `main.tex` | 324–325 | Retrosynthesis uses an undocumented five-point error rubric and asserts route correctness. | Replace with the exposed DirectMultiStep results and exact-reference reaction recall/precision. State that alternative-route equivalence awaits a frozen blind adjudication and that the original headline accuracy is `not_measured`. | `benchmark-corrections-rebuttal-blocks.md` |
| `sup.tex` | 94 | DrugBank is described as an active knowledge foundation. | Apply the same tested-access boundary as `main.tex` line 194. | `provider-claim-matrix.md` |
| `sup.tex` | 103 | QVina and MDockPeP2 are described as accurate binding evaluation tools. | Describe QVina/Vina and peptide docking as computational signals with the observed validation limits. Add ADCP and the MDockPeP2 provider failure boundary. | `peptide-workflow-rebuttal-blocks.md` |
| `sup.tex` | 118 | Seven generators are presented as active production capabilities. | Restrict evaluated live generators to TargetDiff, Pocket2Mol and DiffSBDD; classify the other named models as unverified/deferred. | `cbgbench-rebuttal-blocks.md` |

## Editorial and figure actions

1. Update Figure 2/evaluation caption and source data together with `main.tex` lines 90–98; the
   current radar-style superiority narrative cannot remain after the score-disposition audit.
2. Update Figure 3 caption with the known-candidate Luteolin wording and computational-signal
   boundary.
3. Update Figure 4 caption and labels so MDockPeP2 scores are not presented as binding affinity or
   evidence of superiority over Semaglutide/Tirzepatide.
4. Add the measured error-attribution table, generator comparison table and peptide-provider table
   from the existing rebuttal blocks before final numbering.
5. Run the naming, `agentfunctions`, BioData crop, cross-reference and clean/marked-copy checks
   after the canonical source is revised.

## Current gate

The verified submitted archive has now been materialized as the active
`docs/manuscript/revision-source/` tree. The first P0 pass has revised the Abstract, Introduction,
Luteolin case, Related Work and Conclusion; the new Prompt-to-Pill and Robin references resolve,
and the source completes a 36-page `latexmk` build. The eight-task Results, Methods, SI, figure
regeneration, clean/marked copies and final page/line indexing remain pending.
