# Response to the Editor and Reviewers

Manuscript: **COMMSBIO-26-4686-T**
Title: **FROGENT: An End-to-End Full-process Drug Design Multi-Agent System**

We thank the Editor and Reviewers for the detailed and constructive assessment. We have revised
the scientific claims, repeated or extended the computational analyses where the original evidence
was insufficient, and made the current implementation and its boundaries explicit. The revised
manuscript no longer relies on the submitted radar or its unrecoverable headline scores. It uses
versioned exposed-case panels, matched base-model comparisons, task-aligned adaptations of recent
systems, independent tool validation, and explicit negative results. FROGENT uses pretrained base
models without task-specific parameter training.

The comments below are faithful summaries of the atomic issues in the decision material. Exact
reviewer wording can be substituted in the submission portal without changing the responses.

## Editor

### E-1 — Scientific novelty and the contribution of orchestration

We agree that integration alone does not establish a scientific contribution. We now position
FROGENT against CLADD, Prompt-to-Pill and Robin, compare current-model adaptations only on aligned
tasks, hold the base model fixed in the direct-versus-FROGENT panel, and report the Forge--Gauge
matched-budget feedback experiment separately. We removed the global-first framing. The retained
contribution is evidence-controlled orchestration across retrieval, molecular and peptide design,
evaluation and retrosynthesis.

**Changed in:** Abstract; Introduction; Results, “Evaluation of FROGENT”; Discussion; SI,
“Benchmark Construction and Evaluation Details” and Supplementary Tables 3--8.

### E-2 — Method transparency and reproducibility

We added explicit model, prompt, memory, tool, failure-recovery and isolation boundaries. FROGENT performs no
task-specific parameter training; its roles are specialized at inference time through instructions,
typed schemas, evidence gates and tool access. Code, tests, evaluation entry points and manuscript
assets are prepared for release at `https://github.com/SZU-ADDG/FROGENT`.

**Changed in:** Methods, “Prompt Engineering Strategy”, “Implementation Details” and
“Agent--Tool Interaction”; Code Availability; SI, “Agent Role Contracts and Scientific Action
Space”, Supplementary Table 1 and “Clean-install Validation”.

### E-3 — Definition and validation of the eight benchmarks

We audited all eight supplied 20-case categories and now report task-specific inputs, metrics,
denominators and invalid cases. The panels are explicitly described as exposed rather than hidden
held-out tests. We retired the unavailable submitted headline scores and replaced them with
versioned sample-level outputs and reproducible scorers.

**Changed in:** Results, “Evaluation of FROGENT”; Methods, “Evaluation Benchmarks Details”; SI,
Supplementary Tables 2--4 and the eight benchmark subsections.

### E-4 — Baseline fairness and ablation

The revised study separates three questions: same-model direct versus FROGENT performance,
component-level evidence and tool effects, and one feedback allocation versus uniform generation.
All claims are limited to the matched conditions tested. We do not interpret the fixed one-pass
paired arm as a ReAct ablation or an adaptive loop.

**Changed in:** Results evaluation and generation subsections; Discussion; SI, Supplementary
Tables 3--6.

### E-5 — Consistency between the manuscript and executable Agent behavior

We audited every retained provider and assigned it a measured, deferred, case-study-only or removed
status. Unverified generators and docking providers were removed from active claims. Historical
endpoint failures, schema gaps and provider disagreement remain visible.

**Changed in:** Methods, Retrieve/Forge/Gauge Agent descriptions; Discussion, “Limitations”; SI,
Supplementary Tables 1, 9 and 10 and the database, tool and model inventory.

### E-6 — Repetition

We reduced repeated performance and architecture claims and moved operational detail to Methods and
SI. The main text now emphasizes the scientific argument and its tested boundaries.

**Changed in:** Results, Discussion and Methods throughout.

## Reviewer 1

### R1-0a — Positioning against recent literature

We added CLADD, Prompt-to-Pill and Robin to the literature review and implemented current-model
adaptations of their public workflows. The comparison is task-aligned and does not claim to
reproduce their paper-era models or published scores.

### R1-0b — Fine-tuning, few-shot and in-context learning

FROGENT does not fine-tune or otherwise update the base-model parameters. Active roles use runtime
instructions, typed output schemas, evidence admission, project-scoped memory and tools and contain
no benchmark-specific demonstrations. Direct benchmark cells are stateless; paired FROGENT cells
receive frozen gold-blind evidence; gold is used only after inference.

### R1-0c — Benchmark reproducibility

We provide the eight case definitions, task-specific scorers, denominators, exposed-data status,
failed-case accounting and versioned analysis entry points. The original unrecoverable headline
scores have been withdrawn.

### R1-0d — Differences between Agent outputs and manuscript claims

We replaced conversational or inventory-level claims with provider-bound execution evidence.
Capabilities lacking a verified executable route are now deferred or removed.

### R1-0e — Repetition

We consolidated repeated architecture and workflow descriptions and moved prompt, provider and SOP
detail to Methods and SI.

### R1-1a — Spacing, spelling and grammar

We performed a source-level and rendered-manuscript language pass and corrected the identified
spacing, spelling and grammar defects.

### R1-1b — Concatenated words

The concatenated terms were corrected and checked in the compiled manuscript.

### R1-1c — Figures 8--9 and “provided below”

The figure references and directional wording were synchronized with the final figure order.

### R1-2 — Statistical support for the eight tasks

We no longer attach one significance claim to heterogeneous task metrics. The paired panel reports
case-level paired estimates and a model-level macro summary; individual task results retain their
own denominators and uncertainty. Descriptive external cells are not converted into a global rank.
The complete task- and model-level values are reported in Supplementary Tables 3 and 4.

### R1-3a — Luteolin is a known DrugBank candidate

We agree. Luteolin is now described as exposed known-candidate evidence recovery, not rediscovery
or novel repositioning.

### R1-3b — References for the known candidate

We added stable chemical identifiers and the preclinical PPAR$\gamma$ mechanism reference. We do
not describe the evidence as clinical efficacy.

### R1-3c — Similarity of generated molecules to known inhibitors

We analyzed 9,767 parsed generated molecules against a frozen ChEMBL 37 target-active collection
and a versioned CrossDocked training proxy using ECFP4 similarity and scaffold overlap. The revised
text reports low identity and generally low similarity together with model-specific scaffold reuse
and the exact reference-collection boundary (Supplementary Table 5).

### R1-3d — DrugBank-free literature-driven repositioning

The literature-only Luteolin arm is retained as evidence recovery, while its exposed candidate name
precludes a blinded novel-repositioning claim. We state this limitation directly.

### R1-4a — Missing Prompt-to-Pill, CLADD and Robin

All three systems are now discussed and shown in the aligned comparison. Each adaptation could use
its public files, native components and public web resources; FROGENT-private resources and gold
answers were excluded.

### R1-4b — Overstated first claim

We removed the global “first” claim. The novelty statement is now limited to the demonstrated
combination of evidence control, multi-stage molecular and peptide workflows, and same-model
system evaluation.

### R1-4c — Benchmarking recent systems

We report six aligned current-model cells: one for CLADD, three for Prompt-to-Pill and two for
Robin. The comparison figure retains the full eight-task axis for Direct LLMs and FROGENT;
unaligned external-system cells remain unmeasured rather than being assigned zero or inferred
scores. Supplementary Tables 7 and 8 report the accepted cell values and aligned FROGENT endpoints.

### R1-5a — Generation of small-molecule and peptide conformations

Methods and SI now distinguish generator coordinates, receptor-frame docking poses, structure
prediction and post-hoc geometry analysis, including the exact tools and evaluated providers
(Supplementary Table 9 and Supplementary Figure 1).

### R1-5b — Source and validation of the glucagon secondary structure

The peptide case now identifies the 4ZGM structural context, sequence mapping, missing residues and
provider disagreement. It no longer treats one predicted pose as an experimentally validated
secondary structure.

### R1-5c — Why dock molecules after 3D generation

We clarify that generation and docking answer different questions. Redocking is used as a
geometry and interaction-sensitivity check, not as proof of affinity; failure cases and PLIP changes
are reported.

### R1-6 — Resource, tool and model inventory for each Agent

The revised Methods and SI bind each retained Agent capability to a provider, model/tool version,
input/output contract and measured status. Supplementary Table 1 gives the verified role-specific
action space, and deferred entries are explicitly identified.

### R1-7 — Memory and synthesis in Algorithm 1

We clarified project-scoped working/persistent memory, evidence admission and revocation, state
transitions, stopping and final synthesis. Private model reasoning is not presented as an auditable
scientific trace.

### R1-8a — Scoring subjective HLE questions

Official HLE identity and submitted judge records were unavailable. We therefore renamed the set
Foundational Biomedical Knowledge, used exact scoring on the exposed supplied questions, and
removed the official-HLE claim.

### R1-8b — QED is a calculated descriptor

We agree. QED is reported as a deterministic RDKit descriptor, with prediction endpoints such as
Caco-2 and classification tasks reported separately.

### R1-8c — Virtual screening may measure tool invocation

The independent ABL1 panel showed exact agreement between the FROGENT wrapper and direct Vina,
while Vina ranking correlated weakly with DAVIS affinity. We therefore claim reliable tool
execution, not affinity prediction.

### R1-8d — Incorrect SA-score direction

The direction was corrected: lower SA indicates easier predicted synthesis. Affected text and
comparisons use this convention.

### R1-8e — Retrosynthesis route correctness

DirectMultiStep was scored against the existing human-selected reference routes using exact route
match, reaction recall and precision. Non-exact routes are not labelled chemically impossible, and
no additional human panel is claimed.

### R1-9a — Report download

The maintained application exports the canonical conversation report as Markdown, PDF and genuine
OOXML Word; owner-scoped access and cross-user denial were tested.

### R1-9b — Molecular visualization and structure download

The application now supports owner-scoped PDB/SDF/MOL/MOL2 downloads and a first-party coordinate
viewer. These interface tests do not add claims about pose correctness or affinity.

### R1-9c — Safety guardrails

We added the preregistered safety contract and report its tested refusal, degradation, recovery,
provenance and synthetic-secret leakage boundaries.

### R1-9d — Peptide-conformation performance and runtime

The revision reports ESMFold, AlphaFold3, ADCP and licensed MDockPeP2 results, including timing,
top-1/top-$k$ behavior and provider disagreement. Claims are limited to computational
prioritization (Supplementary Table 9 and Supplementary Figure 1).

### R1-9e — MDockPeP2/ADCP consistency

Direct licensed MDockPeP2 completed all three reference jobs and ADCP completed all nine. The old
endpoint failure and inconsistent top-1 MDockPeP2 ranking are retained as limitations.

### R1-9f — rDock and RNA--ligand capability

Unverified rDock and live RNA--ligand claims were removed. Only provider routes with observed
execution remain in the manuscript.

## Reviewer 2

### R2-1a — Ambiguous contributions, pipeline and accuracy

We reorganized the evidence by scientific question and use task-specific metrics rather than a
single undefined accuracy. The Abstract states the problem, advance, core result and scope.

### R2-1b — Unsupported efficiency claim

The broad efficiency-superiority claim was removed. We report measured wall time, CPU, memory and
calls where available; token, queue, energy and unmatched external costs remain unmeasured.

### R2-2a — System capability versus formal evaluation

Capability inventory, executable status and formal benchmark evidence are now separated. Presence
in an architecture diagram no longer implies measured performance.

### R2-2b — Mapping workflow figures to benchmarks

Figure legends and the Results table now state which workflow components were independently tested
and which figures are illustrative case studies.

### R2-3a — Agent value versus underlying tool performance

We added direct-tool checks, same-model direct comparisons and typed adapter tests. Tool fidelity is
reported separately from orchestration or scientific quality.

### R2-3b — Tool failures versus Agent errors

Failures are attributed to planning/routing, tool/provider, parsing/schema, entity alignment,
evidence support and synthesis/format categories where the evidence permits. Preserved provider and
parser failures are not counted as model reasoning errors. Supplementary Table 10 reports the
denominator, failure location, handling rule and supported scope for each retained layer.

### R2-3c — Maximum and absolute task scores

Each task now states its metric, direction, denominator and observed result. Heterogeneous task
metrics are not treated as one absolute performance scale.

### R2-4 — Time, resources, cost and energy

We report component-level telemetry from the available records and explicitly mark unavailable
token, queue and energy fields as unmeasured (Supplementary Table 11).

### R2-5 — Fixed SOP versus dynamic planning

Methods now distinguish role/SOP constraints from runtime planning. The paired FROGENT arm is
labelled evidence-conditioned fixed one-pass; adaptive evidence is supplied by the separate
Forge--Gauge feedback experiment.

### R2-6 — Agentic baseline configuration

The external adaptations and direct models now have explicit model, resource and isolation
contracts. Comparisons are limited to aligned cells.

### R2-7a — Inconsistent task names

The eight task names were standardized across the main text, figures, Methods, SI and scorers.

### R2-7b — Score scales and absolute quality

Scores are displayed with task-specific interpretation boundaries. The macro mean is descriptive
and no global cross-system rank is claimed.

### R2-8a — Excessive cross-referencing

The central argument is presented in the main reading path; detailed protocols and complete tables
are placed in SI without requiring repeated figure hopping.

### R2-8b — Missing SOPs and prompts

Role contracts, SOPs, budgets, recovery and stopping rules and benchmark isolation are now described in Methods
and SI. Supplementary Table 1 summarizes the role-specific scientific action spaces, and the full
prompt/SOP assets are included in the release package where licensing permits.

### R2-9a — Broken code link

The public repository is `https://github.com/SZU-ADDG/FROGENT`, and the immutable revision release
is `https://github.com/SZU-ADDG/FROGENT/releases/tag/commsbio-revision-20260811`; Code Availability
now records both locations.

### R2-9b — Anonymous link under single-blind review

The revision uses the stable public repository rather than an unnecessary anonymous mirror.

## Reviewer 3

### R3-M1 — HLE identity and Figure 3 labels

The official-HLE claim was removed and the task renamed Foundational Biomedical Knowledge. Figure
and text labels now use the same eight task names.

### R3-M2a — Unequal structured-database access

We report access conditions explicitly and compare structured retrieval only within matched or
clearly labelled settings. DrugBank live execution returned HTTP 403 and is not counted as a
measured provider result.

### R3-M2b — Retrieve query, parsing and integration

Methods now describe planned queries, typed provider records, entity validation, evidence
admission, conflicts, provenance and memory eligibility.

### R3-M3 — Retrieval reliability, uncertainty and conflict handling

Repeated live-evidence tests retain provider failures, counterevidence and revoked records. The
The temporal-version failure remains reported rather than being hidden by aggregate success.

### R3-M4 — Orchestration versus tools and databases

The same-model paired panel isolates the system-level effect, while direct-tool and provider tests
separate execution fidelity. Claims do not attribute every gain causally to multi-agent routing.

### R3-M5a — Retrieve Agent ablation

Removing Retrieve caused the largest observed component effect on the matched retrieval cases. We
report the small exposed denominator and avoid generalizing beyond those cases.

### R3-M5b — Gauge Agent ablation

Removing Gauge produced a smaller design-quality signal with boundary-touching uncertainty. The
claim is correspondingly limited.

### R3-M5c — Forge--Gauge iteration

The matched-budget 15-cell panel shows that one feedback allocation improved validity and top-50
score over uniform single pass. Fixed-best TargetDiff retained a validity advantage, and iterative
top-50 superiority over fixed-best was unsupported (Supplementary Table 6).

### R3-M5d — Global-context ablation

The no-context comparison showed a modest context signal in the tested panel. We report resource
and worker differences and do not claim broad multi-agent superiority.

### R3-M6 — Contribution of underlying generative models

TargetDiff, DiffSBDD and Pocket2Mol were evaluated across pockets and six seeds. We report
model-specific validity, QED/SA, novelty, scaffold reuse and clash behavior; generator identity is
therefore not hidden behind a single FROGENT score (Supplementary Tables 5 and 6).

### R3-m1 — Randomness in task decomposition

Repeat-variation and deterministic binding analyses now distinguish model variation from fixed
provider and scoring behavior. Seed and repeat counts are reported where available.

### R3-m2 — `agentfunctions` spelling

The spelling was corrected throughout the source and rendered manuscript.

### R3-m3 — Cropped BioData label in Figure 1

Figure 1 was regenerated and checked in the compiled manuscript so that the label is visible.

## Final claim boundary

The revised manuscript supports an evidence-controlled computational framework that improves the
same pretrained base models on the exposed paired panel, executes typed scientific tools, and uses
evaluation feedback to reallocate generation effort under matched budgets. It does not claim wet-lab
efficacy, docking-derived affinity, hidden held-out generalization, global superiority over all
agent systems, or task-specific language-model training.
