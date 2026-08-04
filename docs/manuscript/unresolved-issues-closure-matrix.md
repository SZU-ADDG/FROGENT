# FROGENT unresolved-issue closure matrix

Date: 2026-08-05

This matrix separates remaining decision risks from completed experimental evidence. It is an
internal drafting control document: claims marked `not_measured` must remain visible in the
manuscript and response letter unless the listed source material becomes available.

## Author-input blockers

| Priority | Concern | Reviewer IDs | Available evidence | Missing source of truth | Closure if supplied | Claim disposition if absent |
|---|---|---|---|---|---|---|
| P0 | Eight-task headline benchmark | E-3; R1-0c; R1-2; R2-1a; R2-3c; R2-7a/b | Author-supplied 8 × 20 exposed cases/reference answers, complete task 5/6/7 structures, source audit and statistics runner | Official task/version/license, original outputs, failure rows, seeds, scorer code and Figure 1/3 mapping | Recompute post-hoc source-grounded reruns and, if original outputs arrive, reproduce submitted sample-level scores, failures, paired effects, 95% CIs and Holm families | Withdraw unrecomputed headline numbers; label all new runs as exposed-case reruns; report independently reproduced panels separately |
| P0 | HLE task and score | R1-8a; R3-M1 | Access audit, 59-to-24 metadata screen, 20 author-supplied biomedical questions with answers/rationales, and a frozen Luna/max no-tool rerun with 20/20 successful calls and 9/20 exact (Wilson 95% CI 0.258–0.658) | Official source/version/license, authorization, submitted inclusion mapping, original model/prompt, rubric and judge records | Reconstruct provenance and inclusion flow, then score each authorized case under a frozen rubric | Report the 9/20 result only as a post-hoc exposed model-boundary panel; official HLE performance and submitted-score reproduction remain `not_measured` |
| P0 | Retrosynthesis headline accuracy | R1-8e | Twenty author-supplied targets/reference routes plus DirectMultiStep live executability, parse-validity and stability panel | Original outputs/failures, route-equivalence rubric, judge prompt/version and adjudication records | Deterministic scoring where possible; blinded dual review for semantic cases | Original accuracy remains `not_measured`; retain current tool-reliability result and label any new case rerun post-hoc |
| P0 | Training, prompting and test isolation | R1-0b | Runtime behavior and current provider inventory | Fine-tuning fact, base-model date, few-shot source/count, prompt version, cache/memory policy and overlap checks | Complete exposure/leakage audit and use exact method terminology | Remove or narrow fine-tuning, few-shot, leakage-free and generalization claims |
| P1 | Submitted QED/SA values and figures | R1-8b; R1-8d | All 20 supplied QED values reproduced at three decimals with RDKit 2026.03.3; verified SA direction | Original aggregate scorer/version/parameters, SA inputs and Figure 1/3 source tables | Recompute affected tables/figures and quantify the correction | Keep QED as a descriptor and SA with corrected direction; remove unsupported aggregate values |
| P1 | Production/provider and release facts | E-2; E-5; R1-0d; R1-6; R1-9f; R2-8b; R2-9a/b | Provider-claim matrix and source-only audit | Production configuration, stable public release/data URLs, allowed prompts/SOP and MDockPeP2 authorization | Finalize capability status, Code/Data Availability and reproducibility package | Remove unverified providers; mark unavailable releases or performance as deferred/`not_measured` |

## Agent-owned closure work

| Priority | Concern | Reviewer IDs | Current evidence | Remaining deliverable | Acceptance-oriented closure |
|---|---|---|---|---|---|
| P0 | Manuscript, SI and response synchronization | All 67 atomic comments | Evidence ledger and reviewer-specific result blocks | Edit canonical manuscript; generate clean/marked copies, SI and page/line-indexed responses | Every response ends in one outcome and cites one exact revised location |
| P0 | Claim-boundary consolidation | E-1; E-4; E-5; R1-3; R1-4; R3-M4–M6 | CBGBench, Forge–Gauge, Luteolin and recent-system response blocks | Apply the same canonical numbers and boundaries across Abstract, Results, Discussion, tables and response letter | Retain measured routing/tool-use claims; remove global first, affinity, causal and unmeasured superiority claims |
| P1 | Error attribution and dynamic-planning presentation | R2-3b; R2-5; R3-m1; R3-M3 | Double adjudication, repeat variation, propagation, parser and docking failure panels | One failure taxonomy table/figure with case denominator, cause, recovery and downstream consequence | Present tested recovery and variation without implying full benchmark coverage |
| P1 | Peptide workflow and provider disagreement | R1-5a/b/c; R1-9d/e | MDockPeP2 historical negative audit, ADCP 9/9, ESMFold and AF3 panels | Consolidated workflow, preparation details, timing/failure table and provider-disagreement discussion | Report ADCP partial top-k recovery and MDockPeP2 negative history; prospective MDockPeP2 stays `not_measured` without authorization |
| P1 | Output, viewer and reproducibility surface | R1-9a/b; R2-8b; R2-9a/b | Owner-scoped structure downloads; first-party PDB/SDF/MOL/MOL2 viewer; Markdown/PDF/OOXML Word exports; browser, content-consistency and visual-render smoke evidence | Run the full clean Python 3.11+ plus `npm ci` installation and minimal example from an empty environment | Claim the implemented interfaces now; reserve clean-install portability until the independent environment gate passes |
| P2 | Efficiency and editorial cleanup | R1-1a/b/c; R2-1b; R2-4; R3-m2/m3 | 70 telemetry records; known spelling, naming and figure issues | Measured-component cost table; delete unsupported efficiency sentence; language, figure and cross-reference QA | Report wall-time/CPU/RSS/calls where measured; token, queue and energy remain `not_measured` |

## Optional experiment decision

Decision closed on 2026-08-05: the revised manuscript limits the Luteolin case to known-candidate
retrieval, evidence recovery and prioritization. It removes the claim that this exposed-candidate
arm demonstrates origination of novel repurposing hypotheses without DrugBank. The existing
literature-only evidence therefore closes the reviewer concern, and no hidden-candidate panel is
scheduled for this revision.

## Execution order

1. Request the P0 source materials through `author-input-request.md` and freeze each unavailable
   field as `not_measured` at the author deadline.
2. Apply the provider and scientific claim boundaries to the canonical manuscript and figures.
3. Build the failure-attribution, peptide-workflow and measured-resource tables from frozen
   evidence.
4. Complete clean-install, exports/viewer, cross-reference and synchronized response-package QA.
