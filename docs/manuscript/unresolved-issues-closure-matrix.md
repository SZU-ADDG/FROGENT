# FROGENT unresolved-issue closure matrix

Date: 2026-08-03

This matrix separates remaining decision risks from completed experimental evidence. It is an
internal drafting control document: claims marked `not_measured` must remain visible in the
manuscript and response letter unless the listed source material becomes available.

## Author-input blockers

| Priority | Concern | Reviewer IDs | Available evidence | Missing source of truth | Closure if supplied | Claim disposition if absent |
|---|---|---|---|---|---|---|
| P0 | Eight-task headline benchmark | E-3; R1-0c; R1-2; R2-1a; R2-3c; R2-7a/b | Benchmark datasheet, semantic-adjudication panel and statistics runner | Official task/version/license, case IDs, seeds, raw outputs, failure rows, scorer code and Figure 1/3 mapping | Recompute sample-level scores, failures, paired effects, 95% CIs and Holm families | Withdraw unrecomputed headline numbers; report only independently reproduced panels |
| P0 | HLE task and score | R1-8a; R3-M1 | Access audit and 59-to-24 text-only metadata screen | Authorized complete cases, original included cases, gold/rubric and judge records | Reconstruct inclusion flow and score every authorized case under a frozen rubric | HLE performance remains `not_measured`; report access and selection boundary only |
| P0 | Retrosynthesis headline accuracy | R1-8e | DirectMultiStep live executability, parse-validity and stability panel | Original samples, gold/rubric, judge prompt/version and adjudication records | Deterministic scoring where possible; blinded dual review for semantic cases | Original accuracy remains `not_measured`; retain current tool-reliability result |
| P0 | Training, prompting and test isolation | R1-0b | Runtime behavior and current provider inventory | Fine-tuning fact, base-model date, few-shot source/count, prompt version, cache/memory policy and overlap checks | Complete exposure/leakage audit and use exact method terminology | Remove or narrow fine-tuning, few-shot, leakage-free and generalization claims |
| P1 | Submitted QED/SA values and figures | R1-8b; R1-8d | Deterministic RDKit QED check and verified SA direction | Submitted per-sample values, scorer/version/parameters and source tables | Recompute affected tables/figures and quantify the correction | Keep QED as a descriptor and SA with corrected direction; remove unsupported original values |
| P1 | Production/provider and release facts | E-2; E-5; R1-0d; R1-6; R1-9f; R2-8b; R2-9a/b | Provider-claim matrix and source-only audit | Production configuration, stable public release/data URLs, allowed prompts/SOP and MDockPeP2 authorization | Finalize capability status, Code/Data Availability and reproducibility package | Remove unverified providers; mark unavailable releases or performance as deferred/`not_measured` |

## Agent-owned closure work

| Priority | Concern | Reviewer IDs | Current evidence | Remaining deliverable | Acceptance-oriented closure |
|---|---|---|---|---|---|
| P0 | Manuscript, SI and response synchronization | All 67 atomic comments | Evidence ledger and reviewer-specific result blocks | Edit canonical manuscript; generate clean/marked copies, SI and page/line-indexed responses | Every response ends in one outcome and cites one exact revised location |
| P0 | Claim-boundary consolidation | E-1; E-4; E-5; R1-3; R1-4; R3-M4–M6 | CBGBench, Forge–Gauge, Luteolin and recent-system response blocks | Apply the same canonical numbers and boundaries across Abstract, Results, Discussion, tables and response letter | Retain measured routing/tool-use claims; remove global first, affinity, causal and unmeasured superiority claims |
| P1 | Error attribution and dynamic-planning presentation | R2-3b; R2-5; R3-m1; R3-M3 | Double adjudication, repeat variation, propagation, parser and docking failure panels | One failure taxonomy table/figure with case denominator, cause, recovery and downstream consequence | Present tested recovery and variation without implying full benchmark coverage |
| P1 | Peptide workflow and provider disagreement | R1-5a/b/c; R1-9d/e | MDockPeP2 historical negative audit, ADCP 9/9, ESMFold and AF3 panels | Consolidated workflow, preparation details, timing/failure table and provider-disagreement discussion | Report ADCP partial top-k recovery and MDockPeP2 negative history; prospective MDockPeP2 stays `not_measured` without authorization |
| P1 | Output, viewer and reproducibility surface | R1-9a/b; R2-8b; R2-9a/b | Existing report/structure export entry points and source checks | Clean Python 3.11+ install, minimal example, downloadable formats, Mol*/JSmol and run-consistency smoke tests | Claim only interfaces that pass clean-environment and downloadable-artifact validation |
| P2 | Efficiency and editorial cleanup | R1-1a/b/c; R2-1b; R2-4; R3-m2/m3 | 70 telemetry records; known spelling, naming and figure issues | Measured-component cost table; delete unsupported efficiency sentence; language, figure and cross-reference QA | Report wall-time/CPU/RSS/calls where measured; token, queue and energy remain `not_measured` |

## Optional experiment decision

The existing literature-only Luteolin arm exposed the candidate name. It supports evidence
recovery and prioritization, not blinded novel-repurposing discovery. A preregistered hidden-
candidate literature-only panel is warranted only if the revised manuscript retains a claim that
FROGENT can originate novel repurposing hypotheses without DrugBank. If that claim is removed,
the existing evidence closes the concern without another experiment.

## Execution order

1. Request the P0 source materials through `author-input-request.md` and freeze each unavailable
   field as `not_measured` at the author deadline.
2. Decide whether to retain the novel-repurposing claim; run the hidden-candidate panel only for
   that decision role.
3. Apply the provider and scientific claim boundaries to the canonical manuscript and figures.
4. Build the failure-attribution, peptide-workflow and measured-resource tables from frozen
   evidence.
5. Complete clean-install, exports/viewer, cross-reference and synchronized response-package QA.

