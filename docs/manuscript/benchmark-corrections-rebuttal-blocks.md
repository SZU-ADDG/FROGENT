# Benchmark definitions and scoring corrections — manuscript and rebuttal blocks

Date: 2026-08-04

Status: working draft. This document separates independently reproduced results from submitted
headline values that require author source material. Final section, table, figure, page and line
numbers remain `to verify`.

## AC-facing conclusion

The revision replaces the ambiguous eight-task accuracy presentation with task-specific metrics,
explicit maxima and reproducibility status. The author-supplied pack now provides 20 exposed cases
and reference answers for every task, plus complete structure inputs for tasks 5–7. Submitted HLE
and retrosynthesis headline accuracy remain `not_measured` because the original outputs, scorers,
versions and judge records are absent. QED is treated as a deterministic descriptor, SA direction
is corrected, and virtual-screening ranking uses 19 valid pools after retaining one source-invalid
case in the attempted denominator.

## Proposed benchmark Methods paragraph

Each benchmark is defined by task identity, source/version, unit of analysis, sample count,
comparator, primary metric, score direction, maximum, failure handling and scorer provenance.
Per-sample observations must preserve case, replicate, arm, cluster, output, score and error status;
missing or failed pairs are counted and are not imputed. Paired binary outcomes use exact McNemar
with paired or cluster bootstrap intervals; paired continuous outcomes use sign-flip permutation;
paired ordinal/count outcomes use Wilcoxon signed-rank or paired permutation. Holm correction is
applied within declared hypothesis families. The validated statistics implementation currently
contains synthetic software fixtures only; manuscript inference begins after lineage-bound original
outputs and benchmark-specific scorers are supplied.

## Benchmark disposition table

| Task | Submitted record | Independently verified evidence | Revised metric/status | Required boundary |
|---|---|---|---|---|
| Foundational Biomedical Knowledge / claimed Humanity's Last Exam | 20 items; reported 6/20 | Twenty author-supplied exposed questions: 4 exact-match, 16 multiple-choice, with answers/rationales; official access and selection protocol audited separately | Official HLE performance `not_measured`; exposed-case rerun eligible | Official source/version/license, authorization, submitted inclusion mapping, rubric and judge records unavailable |
| Retrieve Known Drugs | 20 items; reported 83/100 | Twenty exposed queries with DrugBank-ID reference lists and SMILES; structured-resource/live panels reported separately | Original headline `not_measured`; exposed-case rerun eligible | Requires original outputs/failures, provider release, seed/retry policy and score aggregation |
| Retrieve Known Target | 20 items; reported 95/100 | Twenty exposed queries with two or three reference targets per case | Original headline `not_measured`; exposed-case rerun eligible | Requires original outputs/failures, provider release and scorer |
| Molecular Property Prediction | 20 items; reported 79.06 on an ambiguous scale | Twenty SMILES × five supplied endpoints; QED matches 20/20 at three decimals; ADMET-AI 2.0.1 exact-case rerun completed | Endpoint-specific post-hoc results reported; submitted aggregate `not_measured` | Caco-2 rho 0.501; classification balanced accuracy varies from 0.472 to 0.786; do not pool heterogeneous endpoints or reconstruct 79.06 |
| Virtual Screening | 20 groups; reported 6/20 | Twenty receptor structures and 11 candidates per group; row 13 lacks the exact gold stereochemistry although one candidate has matching connectivity; DAVIS identifies the exact JAK2 active moiety; independent DAVIS–ABL1 tool-fidelity result retained | Original attempted 20 and exact-valid denominator 19; one separately reported corrected replacement cell is available | Requires a frozen receptor preparation/grid/ranking protocol; original row remains a failure and the corrected cell is explicitly post-hoc |
| Binding Mechanism | 20 items; aggregate operation absent | Twenty ligand/protein pairs, reference interaction outputs and receptor-only PDBs; independent docking/PLIP panels reported separately | Original headline `not_measured`; pose-generation rerun required before PLIP-like analysis | Gold ligand poses, original outputs, component aggregation and scorer are absent |
| Molecular Design | 20 items; reported 32 with missing unit | Shared generate-five prompt and 20 pocket PDBs received; CBGBench and Forge–Gauge reported separately | Original headline `not_measured`; exact-pocket exposed rerun eligible | Requires original outputs, seeds and QED/SA/Vina aggregation |
| Retrosynthesis Planning | 20 items; reported 74 with missing unit | Twenty exposed targets/reference routes; DirectMultiStep flash/explorer completed 40/40 exact-case calls | Flash/explorer exact reference-route match 0.20/0.30; original accuracy `not_measured` | All calls target-rooted/RDKit-valid; exact alternative routes await blind semantic adjudication; original outputs/judge records absent |

## Proposed Results paragraph

Numeric QA identified 30 benchmark issues: 10 confirmed, eight ambiguous and 12 missing-input;
15 were blocking and 15 major. The supplied source pack subsequently closed the case/gold gap:
all eight tasks contain 20 exposed cases/reference answers, and structure inputs are complete for
virtual screening, binding mechanism and molecular design. It did not include original outputs,
failures, seeds, scorers, versions/licenses or judge records, so it cannot reproduce the submitted
headlines. The virtual-screening audit found one invalid case whose exact isomeric gold is absent
although a connectivity-only form occurs in the pool; its attempted denominator is 20 and exact-
valid ranking denominator is 19. A separately supplied DAVIS archive identifies the matching JAK2
gold as CID 25127112 (pKd 10.443697, Kd 0.036 nM), enabling one transparent post-hoc corrected
replacement cell without rewriting the original input. For molecular
properties, all 20 SMILES parsed and RDKit QED matched the supplied three-decimal values in 20/20
cases. QED is therefore retained only as a deterministic descriptor. The verified SA
implementation runs from 1 (easier synthesis) to 10 (harder synthesis), so the submitted statement
that higher SA is favorable must be corrected.

The preregistered exposed-case ADMET-AI 2.0.1 rerun completed 20/20 cases. Caco-2 MAE/RMSE was
0.402/0.515 with rho 0.501. BBBP, CYP2D6-sub and SR-p53 balanced accuracy was
0.550/0.786/0.472 and MCC was 0.229/0.681/-0.076. SR-p53 recovered 0/2 positives despite nominal
accuracy 0.850. The endpoint-dependent behavior and class imbalance preclude a unified accuracy;
the submitted 79.06 remains unreconstructed.

In the independent DAVIS–ABL1 panel, both direct Vina and the FROGENT wrapper completed 10/10
ligands and produced identical pose-score vectors. Each arm selected imatinib, while DAVIS ranked
dasatinib first; Spearman rho was 0.115 (p=0.7514). This supports faithful typed tool execution and
shows that uncalibrated Vina score is a weak affinity discriminator in this panel. The repeated
DirectMultiStep/FragGen provider panel supports current executability and output validity; it does
not recover the original retrosynthesis accuracy without the original outputs and rubric. On the
20 exposed cases, flash/explorer completed 40/40 calls. Full canonical reference-route exact match
was 0.20/0.30 and mean top-5 best reference-reaction recall was 0.572/0.738. Alternative-route
equivalence remains pending blind adjudication.

## Point-by-point response blocks

### R1-8a and R3-M1 / HLE identity and scoring

**Response.** We documented the claimed Humanity's Last Exam source, access gate, schema and judge
protocol and preregistered a text-only Biology/Medicine selection procedure. The author-supplied
pack contains 20 exposed biomedical questions with answers and rationales. Their official HLE
source/version/license, authorization and submitted inclusion mapping remain unverified, and the
original model/judge records are absent. We therefore do not report the submitted 6/20 value as
reproduced. Any new score on these questions will be labelled as a post-hoc exposed-case rerun;
HLE-Verified Gold, if used, remains a distinct post-release audit set.

### R1-8b / QED is not a prediction task

**Response.** We agree and have removed QED from property-prediction accuracy. QED is now reported
only as a deterministic RDKit descriptor with its implementation and version. RDKit 2026.03.3
recomputed the supplied QED values exactly at three decimals for all 20 cases. The original
aggregate property-prediction score remains `not_measured` because the four model-dependent
endpoint original outputs and scale aggregation are unavailable. A post-hoc ADMET-AI 2.0.1 rerun
is reported endpoint by endpoint: Caco-2 rho was 0.501; classification balanced accuracy ranged
from 0.472 to 0.786, with SR-p53 recovering 0/2 positives. These results are not pooled into the
submitted 79.06 value.

### R1-8c / virtual screening may measure tool invocation

**Response.** We ran a preregistered matched-backend DAVIS–ABL1 study. The FROGENT wrapper exactly
reproduced direct Vina pose-score vectors for all 10 ligands, establishing execution fidelity.
Both arms showed weak agreement with the experimental affinity ranking (rho=0.115, p=0.7514) and
selected imatinib while DAVIS ranked dasatinib first. We therefore describe this result as tool
execution with a weak affinity discriminator, and remove any implication that a correct Vina call
alone establishes screening quality. The author-supplied exact benchmark now contains 20 receptor
structures and 11 candidates per case; one case lacks the exact gold stereochemistry even though
candidate 3 has matching connectivity. In the supplied DAVIS archive, the same JAK2 target has 68
assayed drugs and a unique top entry, CID 25127112 (pKd 10.443697; Kd 0.036 nM). Removing its
phosphate counterion yields the exact isomeric source gold. We preserve the original case as a
source failure (attempted 20, exact-valid 19) and report the one-field DAVIS-backed correction only
as a separate post-hoc replacement/sensitivity cell.

### R1-8d / SA direction

**Response.** We corrected the SA definition throughout the revision: the verified RDKit Contrib
SA score runs from 1 (easier synthesis) to 10 (harder synthesis), so lower values are favorable.
Submitted QED/SA table and figure values will be recomputed only after their original scorer and
sample-level inputs are supplied; unsupported original values are removed in the interim.

### R1-8e / retrosynthesis correctness

**Response.** The current live provider panel establishes executability, target-rooted nonempty
routes, RDKit-valid molecular strings and repeat stability. It does not establish the submitted
retrosynthesis accuracy. Twenty exposed targets and reference routes are now available. The
original model outputs, failure rows, route-equivalence rubric, judge prompt/version and per-case
decisions remain absent. We therefore mark the original accuracy `not_measured` and retain the
independently verified reliability result. A post-hoc rerun will use a frozen automatic rule where
possible and blinded dual adjudication for semantic route equivalence. The deterministic phase is
complete: 40/40 flash/explorer calls were nonempty, target-rooted and RDKit-valid; full exact
reference-route match was 0.20/0.30, with higher reference-reaction recall for explorer.

### R2-1a, R2-3c and R2-7a/b / task names, maxima and score interpretation

**Response.** We replaced the radar-style aggregate interpretation with a task table that reports
the canonical task name, source, unit, sample count, metric, direction, maximum, comparator,
failures and reproducibility status. Direct-tool results are labelled as baselines, not theoretical
upper bounds. Values that cannot be tied to original sample-level outputs and scorers are omitted
or marked `not_measured`; independently reproduced CPU/live panels are reported separately and are
not pooled with the submitted headline numbers.

## Required claim changes

- Retain: independently reproduced tool fidelity, descriptor calculation, current provider
  executability and separately reported CBGBench/Forge–Gauge results.
- Narrow: every metric to its exact task, denominator, direction, maximum and scorer.
- Remove: QED prediction accuracy, higher-is-better SA wording, unqualified virtual-screening
  accuracy and unreproducible eight-task aggregate superiority.
- `not_measured`: submitted HLE, retrieval, property-prediction, binding-mechanism, molecular-design
  and retrosynthesis headline values until original outputs/failures, scorers, versions and judge
  records are supplied. New results on the received pack are post-hoc exposed-case reruns.

## Frozen evidence sources

- `runtime/evaluation/revision-20260730/nongpu-final/manuscript-qa/README.md`
- `runtime/evaluation/revision-20260730/nongpu-final/manuscript-qa/issue-ledger.json`
- `runtime/evaluation/revision-20260730/nongpu-final/manuscript-qa/validation.json`
- `runtime/evaluation/revision-20260730/nongpu-final/hle-text-subset/report/REPORT.md`
- `runtime/evaluation/revision-20260730/nongpu-final/molecular-properties/REPORT.md`
- `runtime/evaluation/revision-20260730/nongpu-final/davis-screening/report/REPORT.md`
- `runtime/evaluation/revision-20260731/gpu-final/live-weighted-mcp/REPORT.md`
- `runtime/evaluation/revision-20260731/gpu-final/live-weighted-mcp/REPEAT_REPORT.md`
- `runtime/evaluation/revision-20260804/source-material/eight-task-benchmark-r01/report/source-audit.json`
- `runtime/evaluation/revision-20260804/source-material/eight-task-benchmark-r01/report/property-gold-audit/summary.json`
- `runtime/evaluation/revision-20260804/eight-task-property-exposed-r01/output/summary.json`
- `runtime/evaluation/revision-20260804/eight-task-retrosynthesis-exposed-r01/output-v02/summary.json`
- `docs/manuscript/eight-task-source-intake.md`
