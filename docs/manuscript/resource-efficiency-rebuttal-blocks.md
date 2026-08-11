# Resource and efficiency reporting — manuscript and rebuttal blocks

Date: 2026-08-04

Status: working draft. Values are frozen to the non-GPU telemetry package. Final section, table,
page and line numbers remain `to verify`.

## AC-facing conclusion

The revision replaces the unsupported general efficiency claim with measured component-level
resource reporting. The available telemetry characterizes wall time, CPU time, peak resident
memory and explicit provider/tool calls for the retained CPU and live-provider panels. Tokens,
private-provider queue time, closed-provider cost and cloud energy were not exposed and remain
`not_measured`.

## Proposed Methods paragraph

We aggregated 70 per-run telemetry records from the retained non-GPU evaluation package. A record
entered a resource summary only when execution succeeded, the execution context was valid and at
least one resource field was measured; 49 records met these criteria. Local process telemetry was
captured with macOS `/usr/bin/time -lp`, and remote Python 3.11 process telemetry with GNU
`/usr/bin/time -v`. Wall-only live-provider panels used stored POSIX timing files or monotonic
elapsed values from result JSON. Medians were reported for measured fields, Q1–Q3 and IQR at
`n >= 3`, and descriptive linearly interpolated P95 at `n >= 5`. Missing fields were recorded
literally as `not_measured`. Setup failures and invalid shared-tree attempts were retained in a
separate exclusion ledger.

## Proposed Results paragraph

The telemetry package contains 70 per-run records and 49 valid resource-summary records. Wall
time was available for 50 records, total CPU time for 32 and peak resident memory for 19; 25 setup
or shared-tree attempts were excluded from the resource summaries and retained separately. In
five-run local panels, the 63-test evidence group had median wall time 0.47 s, total CPU time
0.46 s and peak RSS 75,296 KiB; the 89-test molecular group had corresponding medians of 1.15 s,
1.12 s and 169,088 KiB. The five-run Vina stability panel had median wall and total CPU times of
20.01 s and 43.27 s, respectively. The live RCSB panel had median wall time 3.427 s across three
runs and two explicit provider calls per run. Europe PMC multitask query medians ranged from
1.710 to 2.481 s with one provider call per query. These measurements describe the executed
components; they do not establish lower end-to-end cost or greater efficiency than another
framework.

## Supplementary resource table

| Panel | Valid runs | Median wall time | Median total CPU time | Median peak RSS | Calls recorded | Boundary |
|---|---:|---:|---:|---:|---:|---|
| Evidence functional tests (63 tests) | 5 | 0.47 s | 0.46 s | 75,296 KiB | `not_measured` | Functional subset excludes 10 repository-architecture checks |
| Molecular tests (89 tests) | 5 | 1.15 s | 1.12 s | 169,088 KiB | `not_measured` | Local CPU test panel |
| Web optional tests | 5 | 0.65 s | 0.63 s | 92,208 KiB | `not_measured` | Six tests passed and one SQLAlchemy test was skipped per run |
| Vina 1IEP seed stability | 5 | 20.01 s | 43.27 s | `not_measured` | 1 tool call/run | CPU parallelism permits CPU time to exceed wall time |
| PDB2PQR 1IEP pH panel | 3 | 0.73 s | 0.66 s | `not_measured` | 1 tool call/run | Three pH conditions |
| Live RCSB target-pocket stability | 3 | 3.427 s | `not_measured` | `not_measured` | 2 provider calls/run | Provider queue time unavailable |
| Live Europe PMC multitask queries | 3/query | 1.710–2.481 s | `not_measured` | `not_measured` | 1 provider call/query | Four heterogeneous queries summarized separately |

## Point-by-point response blocks

### R2-1b / matched resources and efficiency claims

**Response.** We agree that workflow quality and efficiency require explicit resource accounting.
We have added component-level telemetry for the retained CPU and live-provider panels, including
wall time, CPU time, peak resident memory and explicit provider/tool calls when exposed. The
package contains 70 per-run records and 49 valid resource-summary records, with exclusions and
missing fields retained. These data do not provide a matched end-to-end comparison against the
external frameworks. We therefore removed the general efficiency-superiority claim and limit the
revision to measured resource characteristics of the executed FROGENT components.

### R2-4 / time, resources, cost and energy

**Response.** We have added the measurement method, per-panel denominators, robust summaries and
the exclusion ledger to Supplementary Table [to verify]. Tokens, private-provider queue time,
closed-provider prices and cloud energy were not exposed by the executed interfaces and are
reported as `not_measured`; we do not infer them from wall time or call counts. Public interfaces
used in the reported live panels did not incur a measured usage charge. We make no cross-system
cost or energy comparison.

## Required claim changes

- Retain: component-level wall-time, CPU, peak-RSS and explicit call-count measurements.
- Narrow: resource statements to the exact panels, hosts and captured fields in the telemetry
  package.
- Remove: general efficiency superiority, lower end-to-end cost and energy-efficiency claims.
- `not_measured`: LLM input/output tokens, private-provider queue time, closed-provider monetary
  cost, cloud energy and a hardware-matched end-to-end external-system comparison.

## Frozen evidence sources

- `runtime/evaluation/revision-20260730/nongpu-final/telemetry/REPORT.md`
- `runtime/evaluation/revision-20260730/nongpu-final/telemetry/METHODS.md`
- `runtime/evaluation/revision-20260730/nongpu-final/telemetry/telemetry.json`
- `runtime/evaluation/revision-20260730/nongpu-final/telemetry/per-run.csv`
- `runtime/evaluation/revision-20260730/nongpu-final/telemetry/summary.csv`
- `runtime/evaluation/revision-20260730/nongpu-final/telemetry/excluded-attempts.csv`
