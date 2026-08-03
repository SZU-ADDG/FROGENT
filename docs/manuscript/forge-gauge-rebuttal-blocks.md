# Forge–Gauge manuscript and rebuttal blocks

Status: evidence-frozen working text for R3-M5c and R3-M6. Final section,
table, page, and line numbers remain to be assigned after manuscript layout.

## Methods insertion

We evaluated model routing and one round of feedback allocation under matched
sampling budgets. The panel contained five protein pockets and three
prospectively selected seeds, yielding 15 paired pocket–seed cells. Each
condition received 1,500 generation attempts per cell. The fixed-best
condition assigned all attempts to TargetDiff. The uniform single-pass
condition assigned 500 attempts to each of TargetDiff, DiffSBDD, and
Pocket2Mol. The feedback condition first assigned 250 attempts to each model,
then used the prespecified Gauge rule, based on validity, QED, and favorable
synthetic-accessibility score, to allocate the remaining 750 attempts. The
analysis unit was the paired pocket–seed cell. We report two-sided paired
Wilcoxon tests and 95% confidence intervals from pocket-cluster bootstrap
resampling. Geometry was assessed on the top 50 candidates in each cell using
the preregistered pocket-compatibility and severe-clash rules.

## Results insertion

The feedback allocation consistently selected TargetDiff in all 15 cells and
improved both yield and top-ranked molecular quality relative to uniform
single-pass allocation. Valid-molecule rate increased from 0.444 to 0.704, a
paired difference of 0.260 (15/15 cells positive; Wilcoxon
P = 6.10 × 10^-5; pocket-cluster bootstrap 95% CI, 0.231–0.276). Mean top-50
selection score increased from 0.620 to 0.686, a paired difference of 0.066
(13/15 cells positive; P = 0.0020; 95% CI, 0.029–0.106).

The known fixed-best TargetDiff condition retained the highest valid-molecule
rate (0.956). The feedback condition was 0.252 lower in valid rate than this
fixed-best reference. Its mean top-50 score was numerically 0.026 higher
(0.686 versus 0.661), while the paired comparison had no statistical support
(6/15 cells positive; P = 0.978; 95% CI, -0.015 to 0.068). These results support
the value of one feedback allocation round when the model choice is initially
unknown. They do not establish an advantage over a generator already known to
be best for this panel.

Geometry analysis completed all 45 condition–pocket–seed cells and all 2,250
selected candidates. Pocket compatibility was 1.000 in every condition;
severe-clash-free rates were 0.9987 for fixed-best, 0.9987 for feedback, and
1.0000 for uniform single-pass. Fixed-best and feedback top-50 sets contained
750/750 TargetDiff molecules each. The single-pass sets contained 743
TargetDiff, four Pocket2Mol, and three DiffSBDD molecules. These measurements
support pocket-placement and clash-compatibility statements only; binding
affinity and causal model effects were not evaluated.

## Main or supplementary table

| Condition | Allocation | Valid rate | Unique-valid rate | Mean top-50 score | Mean top-50 QED | Mean top-50 favorable SA |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Fixed-best | 1,500 TargetDiff attempts | 0.956 | 0.955 | 0.661 | 0.692 | 0.589 |
| Uniform single-pass | 500 attempts per model | 0.444 | 0.440 | 0.620 | 0.644 | 0.566 |
| Feedback allocation | 250 attempts per model + 750 Gauge-selected attempts | 0.704 | 0.702 | 0.686 | 0.716 | 0.618 |

| Paired contrast | Metric | Mean difference | Positive cells | Wilcoxon P | Pocket-cluster bootstrap 95% CI |
| --- | --- | ---: | ---: | ---: | --- |
| Feedback - uniform single-pass | Valid rate | +0.260 | 15/15 | 6.10 × 10^-5 | [0.231, 0.276] |
| Feedback - uniform single-pass | Mean top-50 score | +0.066 | 13/15 | 0.0020 | [0.029, 0.106] |
| Feedback - fixed-best | Valid rate | -0.252 | 0/15 | 6.10 × 10^-5 | [-0.274, -0.225] |
| Feedback - fixed-best | Mean top-50 score | +0.026 | 6/15 | 0.978 | [-0.015, 0.068] |

## Point-by-point response: R3-M5c

The requested matched-budget ablation now directly isolates the contribution
of one Forge–Gauge feedback round. Across five pockets and three prospective
seeds, feedback allocation improved valid rate by 0.260 over uniform
single-pass allocation (15/15 paired cells positive; P = 6.10 × 10^-5; 95% CI,
0.231–0.276) and improved mean top-50 score by 0.066 (13/15 cells positive;
P = 0.0020; 95% CI, 0.029–0.106). Gauge selected TargetDiff in all 15 cells.
The revised Results and Supplementary Information will report the full paired
protocol, condition-level outcomes, confidence intervals, and failure
accounting. We consequently limit the claim to deterministic model routing and
one feedback allocation round on this panel.

## Point-by-point response: R3-M6

We added direct comparisons among all three deployed manuscript-scope
generators and separated generator strength from orchestration. The primary
and stability matrices cover TargetDiff, DiffSBDD, and Pocket2Mol, while the
new prospective study compares fixed-best, uniform single-pass, and feedback
allocation under identical 1,500-attempt budgets. TargetDiff remained the
strongest generator for validity and was selected in all 15 Gauge decisions.
Feedback improved substantially over uniform allocation, while fixed-best
TargetDiff retained a 0.252 valid-rate advantage. The feedback-versus-fixed
top-50 score difference was unsupported (P = 0.978; 95% CI, -0.015 to 0.068).
The revision will therefore attribute the observed gain to improved allocation
relative to uniform model use and will avoid claiming superiority over a
known fixed-best generator.

## Failure accounting and evidence boundary

- The final recovery manifest contains 120/120 exit-zero jobs.
- Geometry analysis contains 45/45 cells and 2,250/2,250 selected candidates.
- The geometry source contained 47,333 SDF files; 157 unreadable files were
  retained as per-job parse failures.
- The zero-output geometry-r02 failure remains preserved. Geometry-r03 changed
  candidate-level parse-failure handling only and retained the frozen top-50
  selection requirement for every cell.
- Geometry supports pocket and clash compatibility. Affinity, experimental
  activity, and causal effects remain outside this analysis.

## Frozen evidence

- Commit: `7070ce0`
- Run: `runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-recovery-r06/`
- Final manifest: `runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-matched-budget-prospective-recovery-r06/final-manifest.json`
- Run: `runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-phase2-accelerator-r01/`
- Final manifest: `runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-phase2-accelerator-r01/final-manifest.json`
- Run: `runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-top-candidate-geometry-r03/`
- Final manifest: `runtime/evaluation/revision-20260731/gpu-followup-20260802/forge-gauge-top-candidate-geometry-r03/output/final-manifest.json`
