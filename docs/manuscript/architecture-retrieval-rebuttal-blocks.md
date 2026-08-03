# Architecture and retrieval contribution — manuscript and rebuttal blocks

Date: 2026-08-04

Status: working draft. Results are frozen to the matched-resource, real-agent ablation,
structured-retrieval, live-evidence and evidence-propagation panels. Final section, table, page
and line numbers remain `to verify`.

## AC-facing conclusion

The controlled evidence supports a strong Retrieve contribution on the five tested retrieval
cases, a smaller and uncertain Gauge contribution on five design cases, and only a small
global-context signal. Structured databases added coverage that bounded literature search missed,
while live and deterministic panels exposed both successful evidence controls and a temporal-
version failure. The revision therefore reports component-specific behavior and removes a broad
multi-agent-superiority interpretation.

## Proposed architecture Methods paragraph

We evaluated architecture contribution in two complementary settings. First, a deterministic
matched-resource panel gave fixed-script, ReAct-like, full FROGENT and Retrieve-removed arms the
same ordered evidence pool and per-case ceilings of two tool calls, four reader calls, five
seconds and zero same-query retries. Second, a real-model ablation froze 130 worker outputs across
direct, single-agent, global-context-removed, full-context, Retrieve-removed and Gauge-removed
conditions. The main-condition comparisons used matched case–replicate pairs; the Retrieve and
Gauge ablations were restricted to five retrieval and five design cases, respectively. Blind
scores were independently adjudicated, and paired bootstrap intervals and exact sign tests were
computed without treating the deterministic policy proxy as an LLM baseline. Multi-agent arms
used three workers per instance; direct, single-agent and component-removed arms used one.

## Proposed retrieval Methods paragraph

The retrieval workflow constructs entity-bound queries, normalizes canonical identifiers, parses
typed provider records, removes duplicate identifiers, packages provenance and admits only
qualified evidence into working memory. The structured-resource panel evaluated four disease-to-
target cases through Open Targets and four protein-to-drug-link cases through reviewed UniProt
records. Direct-provider, typed-adapter and 25-record Europe PMC literature-only arms were run for
each case. Reliability was evaluated separately on eight exposed live Europe PMC tasks covering
consistent, conflicting, temporal, retracted, missing and provider-failure conditions. A four-case
deterministic downstream panel tested consistent, conflicting, revoked and missing evidence through
the evidence ledger, reconciliation gate and qualitative-design calibration path.

## Proposed Results paragraph

All 130 real-model worker outputs passed contract validation. Full-context mean blind score was
9.367/10; paired differences versus direct, single-agent and global-context-removed conditions
were 0.067 (95% CI [-0.333, 0.500]), 0.033 ([-0.267, 0.333]) and 0.167
([0.000, 0.333]), respectively. These small effects do not support general architecture
superiority. On applicable cases, removing Retrieve reduced score by 7.000/10 (five wins, 95% CI
[5.200, 8.500]), while removing Gauge reduced score by 0.800/10 (three wins, one tie and one loss;
95% CI [0.000, 1.600]). The latter interval reaches the null boundary.

The structured-resource panel completed 24/24 logical calls with zero retries. The typed adapter
exactly reproduced every ordered direct-provider identifier set. A fixed 25-record literature
window recovered 22.5% of the 40 disease–target references and 9.22% of the 374 reviewed
protein–drug links, supporting a bounded structured-source coverage contribution. Independent
review of the eight live-evidence tasks yielded three pass, four partial and one fail. The failure
was the ACTT-1 temporal-version case, where the earlier report was absent from observable working
memory. In the four deterministic propagation cases, all outputs passed; two changed hypothesis
ordering, explicit unsupported evidence carry-through and revoked-evidence leakage were both zero,
and all four retained an actionable three-item portfolio. Confidence-field changes and decisive-
experiment changes remained zero, exposing a current downstream-calibration limitation.

## Supplementary contribution table

| Question | Denominator | Measured result | Interpretation boundary |
|---|---:|---|---|
| Full architecture versus direct | 15 matched pairs | +0.067/10; 95% CI [-0.333, 0.500] | No broad superiority support |
| Full architecture versus single agent | 15 matched pairs | +0.033/10; 95% CI [-0.267, 0.333] | No broad superiority support |
| Global context | 15 matched pairs | Full minus context-removed +0.167/10; 95% CI [0.000, 0.333] | Small signal; multi-agent worker count held at three in both arms |
| Retrieve | 5 applicable retrieval cases | +7.000/10; 95% CI [5.200, 8.500]; 5/0/0 wins/ties/losses | Applies to exposed evidence-dependent retrieval cases |
| Gauge | 5 applicable design cases | +0.800/10; 95% CI [0.000, 1.600]; 3/1/1 | Smaller signal with null-boundary uncertainty |
| Structured-source coverage | 8 cases; 24 calls | 24/24 calls; literature macro recall 22.5% and 9.22% | Exact-name recall in a fixed 25-record title/abstract window |
| Live evidence reliability | 8 tasks | 3 pass, 4 partial, 1 fail | Retains the ACTT-1 temporal-version failure |
| Downstream propagation | 4 cases | 4/4 pass; 2 ranking changes; 0 explicit unsupported carry-through; 0 revoked leakage | Confidence and decisive-experiment fields did not change |

## Point-by-point response blocks

### R3-M2a / structured-database resource advantage

**Response.** We have separated database access from orchestration quality. Across eight exposed
cases, direct Open Targets or UniProt calls and the typed adapter completed 24/24 logical calls,
and the adapter reproduced every ordered identifier set. The matched 25-record Europe PMC window
recovered 22.5% of disease–target references and 9.22% of protein–drug links. We report this as a
bounded coverage contribution of structured sources. Direct DrugBank access returned 403 and
DrugBank-specific retrieval performance remains `not_measured`.

### R3-M2b / Retrieve query, parsing and integration

**Response.** The revised Methods now specifies entity binding, query construction, canonical-ID
normalization, typed parsing, deduplication, provenance packaging, evidence admission, conflict
retention and revocation. The Supplementary material links each stage to its executed artifact and
failure behavior. This replaces the previous high-level description with an auditable retrieval
and working-memory path.

### R3-M3 / reliability, uncertainty and conflict propagation

**Response.** Independent review of eight live tasks produced three pass, four partial and one
fail; we retain the ACTT-1 temporal-version failure. A separate four-case deterministic panel
passed all cases, changed hypothesis ordering under conflict and revocation, and produced zero
explicit unsupported carry-through and zero revoked-evidence leakage. The same panel showed no
changes to confidence or decisive-experiment fields, which we report as a current limitation
rather than inferring complete uncertainty propagation.

### R3-M4 and R2-3a / orchestration versus tools and databases

**Response.** Under matched case inputs, evidence and decision limits, full-context score differed
from direct and single-agent conditions by +0.067/10 and +0.033/10, with confidence intervals
crossing zero. Full context exceeded the three-worker context-removed arm by +0.167/10, with a
95% CI of [0.000, 0.333]. We therefore removed the broad claim that multi-agent orchestration is
generally superior. The retained claim is component-specific: Retrieve had a large effect on the
five evidence-dependent retrieval cases, and context showed a small signal on this exposed panel.

### R3-M5a / Retrieve ablation

**Response.** Removing Retrieve reduced blind score by 7.000/10 across five applicable retrieval
cases (five wins; 95% CI [5.200, 8.500]). Evidence recall and counterevidence retention also fell
to zero in the Retrieve-removed arm. This supports Retrieve as necessary for the tested
evidence-dependent tasks; it does not estimate performance on every manuscript benchmark.

### R3-M5b / Gauge ablation

**Response.** Removing Gauge reduced blind score by 0.800/10 across five applicable design cases,
with three wins, one tie, one loss and a 95% CI of [0.000, 1.600]. We report Gauge as a smaller
design-quality signal whose uncertainty reaches the null boundary. The separate Forge–Gauge
matched-budget experiment supplies the generation-allocation result.

### R3-M5d / global-context ablation

**Response.** Full context exceeded the global-context-removed condition by 0.167/10 across 15
matched pairs (95% CI [0.000, 0.333]; five wins, nine ties and one loss). Both conditions used
three workers. We describe this as a small context signal on the tested panel and remove any
general claim that shared context alone establishes architecture superiority.

## Required claim changes

- Retain: Retrieve contribution on the five tested retrieval cases; bounded structured-source
  coverage; tested provenance, revocation and recovery behavior.
- Narrow: Gauge to a smaller design-quality signal; global context to a small exposed-panel signal;
  live reliability to the eight audited tasks.
- Remove: general multi-agent superiority and any implication that a deterministic stopping-policy
  proxy measures LLM reasoning quality.
- `not_measured`: original eight-task benchmark recomputation, direct DrugBank performance,
  broader factual entailment of every generated statement and general biomedical truth.

## Frozen evidence sources

- `runtime/evaluation/revision-20260730/nongpu-final/matched-resource/REPORT.md`
- `runtime/evaluation/revision-20260730/nongpu-final/real-agent-ablation/REPORT.md`
- `runtime/evaluation/revision-20260730/nongpu-final/real-agent-ablation/results/paired-comparisons.json`
- `runtime/evaluation/revision-20260730/nongpu-final/structured-retrieval/REPORT.md`
- `runtime/evaluation/revision-20260730/nongpu-final/live-evidence/independent-adjudication/REPORT.md`
- `runtime/evaluation/revision-20260730/nongpu-final/evidence-propagation/report/REPORT.md`
