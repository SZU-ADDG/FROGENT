# Error attribution and recovery — manuscript and rebuttal blocks

Date: 2026-08-03

Status: working draft. Numerical values are frozen to the evidence paths listed below. Final
section, table, page and line numbers remain `to verify` until the canonical manuscript is edited.

## AC-facing conclusion

FROGENT's evaluated reliability comes from explicit failure visibility and bounded recovery: the
revision retains retrieval, parsing, docking, generation and provider failures in their full
denominators, while restricting each claim to the layer that was actually validated.

## Proposed Results paragraph

We evaluated failure propagation at the retrieval, evidence-memory, tool-adapter, docking and
generation layers. Independent review of eight live retrieval tasks classified three as pass,
four as partial and one as fail. The failed case was the ACTT-1 temporal-update task, where PMID
32909010 was absent from the observable canonical evidence pool; the four partial cases retrieved
appropriate sources while their structured synthesis omitted requested scientific detail. In a
separate four-case propagation panel, conflict and revocation changed candidate ordering in two
cases, all four cases retained an actionable portfolio, and unsupported evidence-derived carry-
through and revoked-evidence leakage were both zero. Tool-layer failures were localized: direct
and adapter-invoked PLIP XML matched in 12/12 cases, while the typed path completed exactly in
8/12 cases because metal-complex and water-bridge identity fields were outside its schema. In the
five-complex redocking panel, 12/15 seed runs recovered the crystal pose within 2 Å; all three
1M17 runs converged to the same alternate pose family (5.862–5.928 Å RMSD). Generated-molecule
analysis retained 58 unreadable files among 9,825 primary SDFs and 157 among 47,333 Forge–Gauge
source SDFs; candidate-level exclusion preserved every frozen job or cell denominator. These
results identify concrete failure locations and prevent tool execution, parser coverage, pose
recovery and downstream scientific validity from being conflated.

## Proposed Methods paragraph

For each evaluated layer, we recorded the attempted-case denominator, terminal state, failure
location, retained evidence, recovery action and downstream claim consequence. Retrieval outputs
were independently adjudicated for entailment, conflict interpretation, PICO alignment, study
quality and task-level synthesis. Evidence-memory tests replayed consistent, conflicting,
revoked and missing-evidence fixtures through admission, reconciliation, calibration and final
rendering. PLIP reliability was separated into direct execution, XML equivalence and typed-schema
coverage. Docking failures were assessed using reference-pose RMSD, interaction recovery and
cross-seed pose consistency. Generated SDF parse failures were counted per source job; downstream
analysis continued only when the preregistered per-cell quota remained satisfied. Run-level
protocol failures and exact amendments were retained as separate evidence and were never merged
with successful source runs without complete logical-job coverage.

## Supplementary failure-attribution table

| Layer | Attempted denominator | Observed failure or variation | Recovery or handling | Supported conclusion | Required boundary |
|---|---:|---|---|---|---|
| Live retrieval and synthesis | 8 tasks | 3 pass, 4 partial, 1 fail; ACTT-1 lost the required temporal distinction | Failure retained; no replacement record introduced | Source gating, retraction exclusion, bounded null control and provider recovery are demonstrated on named cases | Broader biomedical-answer accuracy and temporal-update reliability are unmeasured |
| Evidence propagation | 4 cases | Candidate order changed in 2/4; confidence-field and decisive-experiment changes were 0/4 | Revoked evidence removed before recalibration and rendering | Conflict and revocation can alter ranking with zero revoked leakage in this panel | Typed uncertainty grade and general factual-support coverage are `not_measured` |
| Repeat variation | 5 paired repeats per main arm | Success agreement was 80–100%; mean absolute score change was 0.1–0.5; full-context plan-token Jaccard was 0.276 | Report repeat-level outcomes and avoid deterministic-sequence claims | Task outcome and score stability can be quantified for the exposed panel | Exact plan and recommendation wording are stochastic; broader robustness is unmeasured |
| PLIP typed adapter | 12 complexes | 8/12 end-to-end exact; four selected sites failed closed on metal/water identity fields | Direct XML retained; unsupported typed records rejected | Direct invocation is faithful and supported schema classes preserve exact tuples | Metal-complex and water-bridge typed coverage is unsupported |
| Small-molecule redocking | 15 seed runs across 5 complexes | 12/15 at RMSD ≤2 Å; 1M17 failed in 3/3 at 5.862–5.928 Å with 1/6 reference interaction keys | Alternate pose family retained as a negative result | Stable score and hinge contact alone do not establish reference-pose recovery | Prospective affinity and universal docking accuracy are unmeasured |
| Vina affinity ranking | 10 ABL1 ligands | Spearman rho 0.115, p=0.751 versus DAVIS | No score recalibration performed | Wrapper output matches direct Vina | Affinity discrimination is unsupported in this setup |
| Primary generator parsing | 9,825 SDFs | 58 unreadable molecule files | Counted and excluded at molecule level; 45/45 jobs remained analyzable | Diversity and pocket-geometry results apply to 9,767 parsed molecules | Parse failures remain in every reported denominator |
| Forge–Gauge geometry | 47,333 source SDFs; 45 cells | Strict r02 produced zero output; r03 recorded 157 unreadable SDFs | Parse-handling-only amendment; all 45 cells retained the frozen top-50 quota | Geometry applies to 2,250 selected coordinate-bearing candidates | Geometry does not establish affinity or causal model effects |
| MDockPeP2 historical audit | 3 runs; 25,000 scores; 3,000 retained models | No run reached native-frame CA RMSD ≤2 Å; best superposed value 2.721 Å | Negative history retained; prospective run deferred pending legal runtime | Existing evidence does not support a near-native claim | Prospective performance remains `not_measured` |
| ADCP reference redocking | 9 tasks | Mean top-1/top-5/top-10 RMSD 11.262/5.840/4.690 Å | Report top-k contact recovery together with weak ranking | Partial interface recovery is present in the tested reference panel | Native-pose ranking is weak; 29-residue use is exploratory |

## Point-by-point response blocks

### R2-3b / error propagation

**Response.** We now report where errors enter the workflow and whether they propagate. Across
four frozen evidence-memory cases, conflict or revocation changed candidate order in two cases,
while unsupported evidence-derived carry-through and revoked-evidence leakage were both zero.
The live retrieval panel separately retained one temporal-version failure and four incomplete-
synthesis outcomes among eight tasks. We will add the full denominator, failure location,
recovery action and downstream consequence to Supplementary Table [to verify], and will limit the
claim to the tested control behavior rather than broad biomedical-answer accuracy.

### R2-5 / robustness and recovery

**Response.** The revision evaluates recovery as a typed state transition rather than counting a
successful final answer alone. Provider failure was retained before a later valid retrieval;
revoked evidence was removed from working memory before recalibration; malformed or schema-
incomplete PLIP records failed closed; and generated-molecule parse failures remained in the
source denominators. We will describe these gates in Methods [to verify] and report negative cases
alongside recovered cases in Supplementary Table [to verify].

### R3-m1 / task-decomposition variation

**Response.** Repeated runs show stable task-level outcomes with variable execution traces. Across
five paired repeats per main arm, success agreement ranged from 80% to 100% and mean absolute
score changes ranged from 0.1 to 0.5; the full-context arm had a plan/action token Jaccard of
0.276. We will therefore report repeat-level success, score and trace variation and will avoid a
deterministic-planning claim. Model version, temperature, cache and retry fields unavailable from
the original runs will remain marked `not_measured`.

### R3-M3 / uncertainty and downstream decisions

**Response.** The current evidence gate changes calibration state and candidate ordering, while
the tested design schema does not update hypothesis-confidence or decisive-experiment fields.
This boundary is directly measured: 2/4 conflict/revocation cases changed order, and confidence-
field and decisive-experiment changes were 0/4. We will state this distinction in the revised
architecture description and treat typed uncertainty propagation as a future extension, without
using it to support the present performance claims.

## Claim audit

- Retain: explicit failure visibility, fail-closed unsupported schemas, revocation without leakage,
  provider-failure recovery, bounded repeat variation and per-case structural error attribution.
- Narrow: retrieval reliability to the eight named tasks; evidence propagation to four fixtures;
  docking to tool execution/reference-pose recovery; geometry to coordinate compatibility.
- Remove: deterministic planning, universal recovery, comprehensive typed uncertainty,
  affinity-prediction and broad docking-accuracy implications.
- `not_measured`: original eight-task failure attribution, broader factual carry-through, typed
  uncertainty grade, prospective MDockPeP2 performance and unrecorded model/cache parameters.

## Frozen evidence sources

- `runtime/evaluation/revision-20260730/nongpu-final/live-evidence/independent-adjudication/REPORT.md`
- `runtime/evaluation/revision-20260730/nongpu-final/evidence-propagation/report/REPORT.md`
- `runtime/evaluation/revision-20260730/nongpu-final/real-agent-ablation/results/repeat-variation.json`
- `runtime/evaluation/revision-20260730/nongpu-final/plip-parser-baseline/report/REPORT-final.md`
- `runtime/evaluation/revision-20260730/nongpu-final/multitarget-docking/summary/FAILURE_ANALYSIS.md`
- `runtime/evaluation/revision-20260730/nongpu-final/davis-screening/results/analysis.json`
- `/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-followup-20260801/cbgbench-novelty-pocket-r01/output/final-manifest.json` (remote frozen evidence)
- `runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-top-candidate-geometry-r03/output/final-manifest.json`
- `runtime/evaluation/revision-20260731/gpu-final/mdockpep2/`
- `/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-final/adcp-reference-formal-r01-score-r01/` (remote frozen evidence)
