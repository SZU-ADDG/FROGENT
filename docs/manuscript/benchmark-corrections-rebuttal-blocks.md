# Benchmark definitions and scoring corrections — manuscript and rebuttal blocks

Date: 2026-08-04

Status: working draft. This document separates independently reproduced results from submitted
headline values that require author source material. Final section, table, figure, page and line
numbers remain `to verify`.

## AC-facing conclusion

The revision replaces the ambiguous eight-task accuracy presentation with task-specific metrics,
explicit maxima and reproducibility status. HLE and retrosynthesis headline accuracy remain
`not_measured` without original cases and scoring records; QED is treated as a deterministic
descriptor, SA direction is corrected, and the independent DAVIS panel shows faithful Vina tool
execution together with weak affinity-ranking performance.

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
| Foundational Biomedical Knowledge / Humanity's Last Exam | 20 items; reported 6/20 | Official access and selection protocol audited; 668 Gold metadata records, 59 text-only Biology/Medicine records and 24 after the frozen subject allowlist | HLE performance `not_measured` | Original item IDs, authorized cases, rubric and judge records unavailable; do not substitute HLE-Verified Gold for the submitted set |
| Retrieve Known Drugs | 20 items; reported 83/100 | Structured-resource and live-retrieval panels reported separately | Original headline `not_measured` | Requires original cases, gold mappings, provider release and score aggregation |
| Retrieve Known Target | 20 items; reported 95/100 | Structured-resource and live-retrieval panels reported separately | Original headline `not_measured` | Requires original cases, target gold, provider release and scorer |
| Molecular Property Prediction | 20 items; reported 79.06 on an ambiguous scale | Eleven traceable records parsed; QED/SA and other RDKit descriptors reproduced byte-identically | QED is a descriptor; SA uses 1 easier to 10 harder | Remove QED from prediction-accuracy language; original endpoint labels, values and scale conversion unavailable |
| Virtual Screening | 20 groups; reported 6/20 | Independent DAVIS–ABL1 panel: direct and wrapped Vina 10/10 exact; rho 0.115, p=0.7514 | Tool fidelity measured; affinity discrimination weak | Original candidate pools and seeds unavailable; do not call direct Vina a theoretical upper bound |
| Binding Mechanism | 20 items; aggregate operation absent | Independent docking/PLIP panels reported separately | Original headline `not_measured` | Requires original complexes, component aggregation and scorer |
| Molecular Design | 20 items; reported 32 with missing unit | CBGBench and Forge–Gauge results reported separately | Original headline `not_measured` | Requires original pockets, outputs, seeds and QED/SA/Vina aggregation |
| Retrosynthesis Planning | 20 items; reported 74 with missing unit | DirectMultiStep: 39/39 repeated typed calls; 10/10 nonempty target-rooted RDKit-valid route calls per repeat | Executability/parse stability measured; original accuracy `not_measured` | Requires original cases, gold/rubric, judge configuration and per-case adjudication |

## Proposed Results paragraph

Numeric QA identified 30 benchmark issues: 10 confirmed, eight ambiguous and 12 missing-input;
15 were blocking and 15 major. The submitted benchmark record used incompatible or incompletely
defined scales across the eight tasks. The HLE audit fixed the benchmark identity as Humanity's
Last Exam and froze a text-only selection and scoring protocol, while official authorized content
and the submitted item IDs were unavailable; no replacement accuracy was computed. For molecular
properties, all 11 traceable records parsed, and two CPU runs produced byte-identical descriptors.
QED was therefore retained only as a deterministic RDKit drug-likeness descriptor. The verified
SA implementation runs from 1 (easier synthesis) to 10 (harder synthesis), so the submitted
statement that higher SA is favorable must be corrected.

In the independent DAVIS–ABL1 panel, both direct Vina and the FROGENT wrapper completed 10/10
ligands and produced identical pose-score vectors. Each arm selected imatinib, while DAVIS ranked
dasatinib first; Spearman rho was 0.115 (p=0.7514). This supports faithful typed tool execution and
shows that uncalibrated Vina score is a weak affinity discriminator in this panel. The repeated
DirectMultiStep/FragGen provider panel supports current executability and output validity; it does
not recover the original retrosynthesis accuracy without the submitted cases and rubric.

## Point-by-point response blocks

### R1-8a and R3-M1 / HLE identity and scoring

**Response.** We have identified the task explicitly as Humanity's Last Exam and documented its
official source, access gate, schema and judge protocol. We also preregistered a text-only
Biology/Medicine selection and scoring procedure. Complete authorized cases and the submitted
20 item IDs were unavailable, so we do not report the submitted 6/20 value or a replacement
accuracy. HLE-Verified Gold, if later used, will be labelled as a distinct post-release audit set
and will not be presented as the submitted benchmark.

### R1-8b / QED is not a prediction task

**Response.** We agree and have removed QED from property-prediction accuracy. QED is now reported
only as a deterministic RDKit descriptor with its implementation and version. Two independent CPU
runs on 11 traceable records were byte-identical. The original aggregate property-prediction score
remains `not_measured` until endpoint labels, values, units and scale conversion are supplied.

### R1-8c / virtual screening may measure tool invocation

**Response.** We ran a preregistered matched-backend DAVIS–ABL1 study. The FROGENT wrapper exactly
reproduced direct Vina pose-score vectors for all 10 ligands, establishing execution fidelity.
Both arms showed weak agreement with the experimental affinity ranking (rho=0.115, p=0.7514) and
selected imatinib while DAVIS ranked dasatinib first. We therefore describe this result as tool
execution with a weak affinity discriminator, and remove any implication that a correct Vina call
alone establishes screening quality.

### R1-8d / SA direction

**Response.** We corrected the SA definition throughout the revision: the verified RDKit Contrib
SA score runs from 1 (easier synthesis) to 10 (harder synthesis), so lower values are favorable.
Submitted QED/SA table and figure values will be recomputed only after their original scorer and
sample-level inputs are supplied; unsupported original values are removed in the interim.

### R1-8e / retrosynthesis correctness

**Response.** The current live provider panel establishes executability, target-rooted nonempty
routes, RDKit-valid molecular strings and repeat stability. It does not establish the submitted
retrosynthesis accuracy. The original cases, gold routes or rubric, judge prompt/version and
per-case decisions were unavailable. We therefore mark the original accuracy `not_measured` and
retain only the independently verified reliability result. Any semantic route score will require
blinded dual adjudication or a frozen validated automatic rule applied to every scored case.

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
  and retrosynthesis headline values until original per-sample inputs and scorers are supplied.

## Frozen evidence sources

- `runtime/evaluation/revision-20260730/nongpu-final/manuscript-qa/README.md`
- `runtime/evaluation/revision-20260730/nongpu-final/manuscript-qa/issue-ledger.json`
- `runtime/evaluation/revision-20260730/nongpu-final/manuscript-qa/validation.json`
- `runtime/evaluation/revision-20260730/nongpu-final/hle-text-subset/report/REPORT.md`
- `runtime/evaluation/revision-20260730/nongpu-final/molecular-properties/REPORT.md`
- `runtime/evaluation/revision-20260730/nongpu-final/davis-screening/report/REPORT.md`
- `runtime/evaluation/revision-20260731/gpu-final/live-weighted-mcp/REPORT.md`
- `runtime/evaluation/revision-20260731/gpu-final/live-weighted-mcp/REPEAT_REPORT.md`
