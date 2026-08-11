# FROGENT unresolved-issue closure matrix

Date: 2026-08-05

This matrix separates remaining decision risks from completed experimental evidence. It is an
internal drafting control document: claims marked `not_measured` must remain visible in the
manuscript and response letter unless the listed source material becomes available.

Scope decision, 2026-08-06: the submitted radar, submitted eight-task headline values, original
HLE score and original scorer reconstruction are retired from the revision. The replacement
figure and statistical claims use the frozen 12-model direct and same-model + FROGENT panels.
Missing submitted-run materials no longer block completion.

## Author-input blockers

| Priority | Concern | Reviewer IDs | Available evidence | Missing source of truth | Closure if supplied | Claim disposition if absent |
|---|---|---|---|---|---|---|
| Closed | Training, prompting and test isolation | R1-0b | Author-confirmed no parameter training; active role contracts; clean-panel protocol; gold-blind paired evidence builder; project-scoped memory factory | None for retained exposed-panel claim | Methods and SI now distinguish inference-time specialization, production memory and benchmark isolation | No held-out generalization or leakage-free claim; exposed scope remains explicit |
| P1 | Production/provider and release facts | E-2; E-5; R1-0d; R1-6; R1-9f; R2-8b; R2-9a/b | Provider-claim matrix and source-only audit | Production configuration, stable public release/data URLs, allowed prompts/SOP and MDockPeP2 authorization | Finalize capability status, Code/Data Availability and reproducibility package | Remove unverified providers; mark unavailable releases or performance as deferred/`not_measured` |

## Agent-owned closure work

| Priority | Concern | Reviewer IDs | Current evidence | Remaining deliverable | Acceptance-oriented closure |
|---|---|---|---|---|---|
| P0 | Manuscript, SI and response synchronization | All 67 atomic comments | Evidence ledger, reviewer-specific result blocks, active `revision-source/`, synchronized P0 Results/Methods/SI claim edits, prompt/training-isolation and availability text | Synchronize the response; generate clean/marked copies and page/line-indexed responses | Every response ends in one outcome and cites one exact revised location |
| P0 | Claim-boundary consolidation | E-1; E-4; E-5; R1-3; R1-4; R3-M4–M6 | CBGBench, Forge–Gauge, Luteolin and recent-system response blocks | Apply the same canonical numbers and boundaries across Abstract, Results, Discussion, tables and response letter | Retain measured routing/tool-use claims; remove global first, affinity, causal and unmeasured superiority claims |
| Closed | Fixed one-pass and explicit feedback allocation | R2-5; R3-M4; R3-M5 | Code audit identifies the 12-model evidence-conditioned FROGENT arm as fixed one-pass; Forge–Gauge matched-budget panel compares uniform single-pass with one feedback allocation round and known fixed-best | No duplicate 12-model arm; relabel the radar accurately and report Forge–Gauge separately | Attribute only the measured feedback-allocation difference; do not call one-pass evidence synthesis an adaptive loop or claim removal of model-native reasoning |
| Closed | External-system current-model adaptations | R1-4a/c | Exact public commits, isolated installs, first-run failure evidence and recovery-r02 `6/6 scored` manifest | No further experiment; integrate the six aligned cells into SI and response figures | Report task-aligned numeric cells as current-model adapted implementations; retain original paper scores and global ranking outside scope |
| Closed | Retrosynthesis reference-route scoring | R1-8e; R2-3c | Forty current DirectMultiStep calls with exact-reference metrics; reference routes already reflect human judgment | No additional human adjudication | Report exact match, reaction recall and precision against the existing gold; do not equate non-exactness with chemical impossibility |
| P1 | Error attribution and dynamic-planning presentation | R2-3b; R2-5; R3-m1; R3-M3 | Double adjudication, repeat variation, propagation, parser and docking failure panels | One failure taxonomy table/figure with case denominator, cause, recovery and downstream consequence | Present tested recovery and variation without implying full benchmark coverage |
| Closed | Peptide workflow and provider disagreement | R1-5a/b/c; R1-9d/e | MDockPeP2 direct licensed 3/3 panel, historical negative audit, ADCP 9/9, ESMFold and AF3 panels | No further experiment; synchronize direct timing, top-1/top-k pose recovery and provider disagreement | Report limited prioritization/top-k recovery, inconsistent top-1 ranking and the historical endpoint failure; exclude affinity and broad superiority |
| Closed | Output, viewer and reproducibility surface | R1-9a/b; R2-8b; R2-9a/b | Owner-scoped structure downloads; first-party PDB/SDF/MOL/MOL2 viewer; Markdown/PDF/OOXML Word exports; browser evidence; clean-install recovery-r02 with Python 3.12.13, `npm ci`, no-credential Flask/core smoke, 295 tests and exact replay all passing | No further experiment; add stable release/data URLs when supplied by the authors | Claim the implemented interfaces and tested clean-install path; keep live providers and public release availability bounded separately |
| P2 | Efficiency and editorial cleanup | R1-1a/b/c; R2-1b; R2-4; R3-m2/m3 | 70 telemetry records; known spelling, naming and figure issues | Measured-component cost table; delete unsupported efficiency sentence; language, figure and cross-reference QA | Report wall-time/CPU/RSS/calls where measured; token, queue and energy remain `not_measured` |

## Optional experiment decision

Decision closed on 2026-08-05: the revised manuscript limits the Luteolin case to known-candidate
retrieval, evidence recovery and prioritization. It removes the claim that this exposed-candidate
arm demonstrates origination of novel repurposing hypotheses without DrugBank. The existing
literature-only evidence therefore closes the reviewer concern, and no hidden-candidate panel is
scheduled for this revision.

## Execution order

1. Experimental panels are closed: direct/fixed-one-pass radar, Forge–Gauge feedback allocation,
   three current-model adapted external implementations at 6/6, and direct licensed MDockPeP2 at 3/3.
2. Apply `canonical-manuscript-edit-map.md` and the provider/scientific claim boundaries to the canonical manuscript and replacement figures.
3. Build the failure-attribution, peptide-workflow and measured-resource tables from frozen
   evidence.
4. Clean-install and exports/viewer gates are closed; complete cross-reference and synchronized
   response-package QA.
