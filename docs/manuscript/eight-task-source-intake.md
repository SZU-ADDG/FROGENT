# Eight-task benchmark source intake

Date: 2026-08-04

Status: frozen author-supplied exposed test-data intake. The pack supplies cases and reference
answers. It does not supply the original FROGENT outputs, failure rows, seeds, scorer code,
benchmark versions/licenses or judge records needed to reproduce the submitted headline scores.

## Intake outcome

The supplied archive passed ZIP integrity and path-safety checks. It contains all eight manuscript
task definitions, with 20 cases per task. The task 5, 6 and 7 structure inputs are complete: 20/20
virtual-screening receptor structures, 20/20 binding-mechanism protein structures and 20/20
molecular-design pockets. The frozen intake is classified as `author-supplied_exposed_test_data`;
it must not be used as an unexposed or blinded evaluation set.

| Task | Received case material | Reference material | Immediate status |
|---|---|---|---|
| Foundational Biomedical Knowledge | 20 questions: 4 exact-match and 16 multiple-choice | Answers and rationales | Case-level rerun possible after the model/prompt/judge protocol is frozen; official HLE authorization, version and provenance remain unresolved |
| Retrieve Known Drugs | 20 queries | DrugBank-ID lists and SMILES | Case-level rerun possible; original provider release, aggregation and outputs remain missing |
| Retrieve Known Targets | 20 queries | Two or three targets per case | Case-level rerun possible; original provider release, scorer and outputs remain missing |
| Molecular Property Prediction | 20 SMILES × five endpoints | QED, Caco-2, BBBP, CYP2D6-sub and SR-p53 values | Deterministic QED verified 20/20; ADMET-AI 2.0.1 exact-case post-hoc rerun completed for the four model-dependent endpoints |
| Virtual Screening | 20 receptor/candidate groups; 11 candidates per group | One supplied gold molecule per group | Original attempted denominator 20 and exact-isomeric valid denominator 19; a DAVIS-backed corrected replacement cell is available separately |
| Binding Mechanism | 20 ligand/protein pairs and 20 protein PDBs | Five interaction-class outputs per case | Inputs/gold received; supplied PDBs contain receptor coordinates without the gold ligand pose, so direct PLIP reconstruction is not available |
| Molecular Design | One shared generate-five prompt and 20 pocket PDBs | No unique gold molecule required by the prompt | Exact pocket rerun possible under a frozen generator/scorer protocol; original outputs, seeds and aggregation remain missing |
| Retrosynthesis Planning | 20 target SMILES | One- to five-step reference routes | DirectMultiStep flash/explorer post-hoc rerun completed 40/40 calls; original outputs and semantic judge records remain missing |

## Source defect retained in the analysis population

Virtual-screening row 13 (`JAK2(JH1domain-catalytic)`, PDB `2b7a`) does not contain the exact
isomeric gold in its 11-member candidate pool. Candidate 3 has the same non-isomeric connectivity,
but its stereochemistry is unspecified. The original case therefore remains source-invalid for an
exact-identity scorer and stays in the attempted denominator; original-set ranking accuracy uses
the 19 exact-valid pools.

The separately supplied DAVIS archive resolves the molecular identity without altering the
original file. Exact-target ranking over its 68 JAK2 records identifies Drug Index 49 / PubChem CID
25127112 as the unique top-affinity entry (pKd 10.443697; Kd 0.036 nM). Its DAVIS representation is
a phosphate salt; largest-organic-fragment standardization gives an isomeric canonical SMILES
that exactly matches the source answer. A transparent correction therefore replaces only
candidate 3's connectivity-only representation with that exact DAVIS active moiety in a separate
post-hoc replacement cell. This corrected cell is eligible for a sensitivity or replacement-cell
rerun and is excluded from reconstruction of the originally submitted headline.

## Deterministic property audit

All 20 property-task SMILES parsed with RDKit 2026.03.3. Recomputed QED rounded to three decimals
matched the supplied QED in 20/20 cases; mean absolute error against the rounded supplied values
was 0.000259. This verifies the QED field as a deterministic descriptor. It does not validate the
four ADMET endpoints or reconstruct the submitted aggregate score.

## Exposed-case property rerun

ADMET-AI 2.0.1 was run once on the frozen 20-case batch under an endpoint mapping fixed before
execution. Caco-2 MAE/RMSE was 0.402/0.515 with Spearman rho 0.501 (p=0.0245). BBBP accuracy,
balanced accuracy and MCC were 0.550/0.550/0.229. CYP2D6-sub reached
0.850/0.786/0.681. SR-p53 nominal accuracy was 0.850, while balanced accuracy was 0.472 and MCC
was -0.076 because the model recovered 0/2 positives. The heterogeneous three-endpoint pooled
accuracy of 0.750 is retained only as a secondary accounting value and is not a primary metric.
These values support endpoint-specific reporting and show why a single aggregate score is
misleading. They are a post-hoc rerun against supplied labels, not a reconstruction of the
submitted experiment or independent validation of the labels.

## Exposed-case foundational-knowledge rerun

The 20 supplied foundational-knowledge questions were run through the pinned FROGENT structured
no-tool model boundary using `gpt-5.6-luna` with maximum reasoning effort. Gold answers,
rationales and subject labels were withheld from model input. All 20 calls returned schema-valid
answers; 9/20 were exact-correct (0.450; Wilson 95% CI 0.258–0.658). Exact-match and
multiple-choice subsets were 1/4 and 8/16. Every response selected the `high` confidence label,
while only nine were correct, so that label was not a reliable correctness indicator on this
panel. This is a post-hoc exposed, no-tool rerun. It does not establish official HLE performance,
reproduce the submitted 6/20 result, or measure retrieval and multi-agent orchestration.

## Exposed-case retrosynthesis rerun

DirectMultiStep `generate_routes_flash` and `generate_routes_explorer` each completed 20/20 live
calls. Every call returned a nonempty, target-rooted route set whose parsed molecules were
RDKit-valid. After canonicalizing forward reference reactions and retrosynthetic predictions,
flash top-1/top-5 complete reference-reaction-set exact match was 0.200/0.200, while explorer was
0.300/0.300. Mean top-5 best exact-reference reaction recall was 0.572 for flash and 0.738 for
explorer; corresponding precision was 0.575 and 0.592. Exact matching is intentionally
conservative. Routes with different valid precursors or step decompositions require frozen blind
semantic adjudication and are not automatically classified as chemically wrong.

## Remaining source-of-truth gaps

- Original per-case FROGENT and baseline outputs, including failed and missing rows.
- Original random seeds, retry policy, model/provider release and prompt version.
- Original task scorer/aggregation code and the mapping from sample scores to Figure 1/3.
- Task versions, licenses and source provenance, including HLE authorization.
- Retrosynthesis and free-form task judge prompts, versions and adjudication records.

The source pack therefore closes the case-input and reference-answer gap. It does not by itself
reproduce any submitted headline score. New runs on these now-exposed cases are reported as
post-hoc source-grounded reruns and are never represented as the original test execution.

## Frozen evidence

- `runtime/evaluation/revision-20260804/source-material/eight-task-benchmark-r01/source/test_data.zip`
- `runtime/evaluation/revision-20260804/source-material/eight-task-benchmark-r01/source/test_data.zip.sha256`
- `runtime/evaluation/revision-20260804/source-material/eight-task-benchmark-r01/report/source-audit.json`
- `runtime/evaluation/revision-20260804/source-material/eight-task-benchmark-r01/report/property-gold-audit/summary.json`
- `runtime/evaluation/revision-20260804/source-material/davis-gold-replacement-r01/protocol/selection-protocol.json`
- `runtime/evaluation/revision-20260804/source-material/davis-gold-replacement-r01/report/replacement-case.json`
- `runtime/evaluation/revision-20260804/eight-task-property-exposed-r01/protocol/protocol.json`
- `runtime/evaluation/revision-20260804/eight-task-property-exposed-r01/output/summary.json`
- `runtime/evaluation/revision-20260804/eight-task-foundational-luna-exposed-r01/protocol/protocol.json`
- `runtime/evaluation/revision-20260804/eight-task-foundational-luna-exposed-r01/output/summary.json`
- `runtime/evaluation/revision-20260804/eight-task-foundational-luna-exposed-r01/output/analysis.json`
- `runtime/evaluation/revision-20260804/eight-task-retrosynthesis-exposed-r01/protocol/protocol.json`
- `runtime/evaluation/revision-20260804/eight-task-retrosynthesis-exposed-r01/output-v02/summary.json`
- `evaluation/benchmarks/eight_task_source.py`
- `evaluation/benchmarks/davis_gold_replacement.py`
- `scripts/analyze_eight_task_property_gold.py`
- `tests/test_eight_task_source.py`
- `tests/test_davis_gold_replacement.py`
