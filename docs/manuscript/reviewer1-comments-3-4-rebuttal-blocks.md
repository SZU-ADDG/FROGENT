# Reviewer 1 comments 3–4: rebuttal and manuscript blocks

Status: evidence-grounded working text. Final section, table, page, and line
numbers remain to be assigned after manuscript layout.

## Comment 3: DrugBank, Luteolin, and generated-molecule novelty

### Response

We agree that Luteolin is a previously reported candidate and have removed the
terms “rediscovered,” “novel,” and any implication of clinically validated
efficacy from this case. The revised text identifies Luteolin as a
known-candidate retrieval and evidence-integration example. Its entity record
is linked to DrugBank DB15584, PubChem CID 5280445, ChEMBL CHEMBL151, and ChEBI
CHEBI:15864. The disease-mechanism statement is supported by Wang et al.
(2023; PMID 36998980; PMCID PMC10043402; DOI
10.3389/fcvm.2023.1130635), which reports a 2,570-compound screen,
cardiomyocyte and mouse experiments, direct Luteolin–PPARγ interaction, and
loss of the protective effect after PPARγ inhibition or knockdown. We describe
this evidence as preclinical and make no human clinical-efficacy claim.

We also performed a controlled resource-ablation study. The literature-only
arm admitted no structured drug–target or drug–indication relations and
recovered the cited cardiac PPARγ evidence with citation existence and support
of 1.0, zero unsupported inferences, and zero hallucinated citations. Adding
public structured identity references improved exact entity alignment. The
candidate name was exposed in this five-task study; the result therefore tests
evidence recovery and disciplined synthesis rather than blinded candidate
discovery. We have limited the revised claim accordingly. General novel
drug-repurposing discovery from an unknown candidate set remains unmeasured.

In response to the request for molecular similarity analysis, we evaluated all
9,767 parsed molecules from the primary TargetDiff, DiffSBDD, and Pocket2Mol
panel. Against frozen target-matched ChEMBL 37 strong-active collections, mean
nearest-neighbor ECFP4 similarities were 0.176, 0.143, and 0.120, and maxima
were 0.405, 0.256, and 0.217; all molecules were below 0.5. Exact
active-scaffold overlap was 2/7,253, 0/1,771, and 1/743. Against the executable
CrossDocked training proxy, no generated molecule had exact canonical identity;
exact scaffold overlap was 0.772%, 7.510%, and 15.612%, respectively. We will
report both the low identity/fingerprint similarity and the model-specific
scaffold reuse.

### Manuscript actions

- Replace the Luteolin discovery wording with “known-candidate retrieval and
  evidence integration.”
- Add Wang et al. (2023) and the traceable chemical identifiers.
- State that the literature-only arm evaluates evidence recovery with an
  exposed candidate and does not measure blinded discovery recall.
- Add the ChEMBL known-active and CrossDocked training-proxy results to Results,
  Discussion, Table 3, and Supplementary Information.
- Preserve collection and training-data boundaries: other assay types,
  databases, undisclosed pretraining, and checkpoint-exact membership remain
  unmeasured.

## Comment 4: recent systems, novelty, and external baselines

### Response

We agree that the submitted global priority claim was too broad. We have
removed “the first” and added Prompt-to-Pill, CLADD, and Robin to Related Work
and to a source-grounded capability matrix.

Prompt-to-Pill presents a modular DPP-4 proof of concept spanning molecular
generation, docking, descriptors, ADMET, optimization, and clinical
simulation. Its Target Identification Agent and several later-stage agents are
reported as conceptual placeholders, and its public study does not define a
unified sample-level full-pipeline scorer. CLADD combines molecular RAG,
PrimeKG/PubChem resources, GNN retrieval, and specialized agent routing for
target prediction, molecular captioning, toxicity, and binary bioactivity.
Robin integrates literature-grounded hypothesis generation, human-executed
wet-lab testing, experimental-data analysis, and iterative hypothesis
refinement. These systems materially narrow the novelty context and are now
treated as core related work.

The revised contribution statement is limited to the demonstrated combination
of evidence retrieval, target validation, small-molecule generation, peptide
optimization, interaction analysis, retrosynthetic planning, and dynamic
Forge–Gauge allocation, together with task-level evaluation and explicit
failure accounting. It does not claim global priority over end-to-end agentic
drug-discovery systems.

We installed exact public commits for the three systems and used GPT-5.6 Sol/high
as the common current base model. Each adaptation could use its own frozen public
files, available native components, and public web resources, while FROGENT/private
resources and gold answers remained excluded. Post-run command auditing rejected
two filesystem-contaminated cells; an exact recovery reran only those two cells.
The accepted panel completed 6/6 aligned cells. CLADD obtained 0.8239 on
molecular-property prediction. Prompt-to-Pill obtained 0.8540, 0.8947, and 0.8383
on molecular-property prediction, virtual screening, and molecular design. Robin
obtained 0.6650 and 0.2833 on known-drug and known-target retrieval. Each number
uses the revised exposed cases and frozen task-specific scorer. We report these as
current-model resource-enabled adaptations; the original paper models and scores
were not reconstructed. Human- and assay-dependent Robin outcomes remain
`not_measured`.

For direct alignment, the revised heatmap displays all 12 direct LLMs
individually. FROGENT uses GPT-5.5 as its base model and obtained 0.833, 0.526,
0.939, 0.540, and 0.250 on property prediction, virtual screening, molecular
design, known-drug retrieval, and known-target retrieval. The aligned external-system
results show complementary strengths rather than uniform
dominance by one workflow. Hatched cells identify tasks that are not implemented by the
corresponding public workflow. In Prompt-to-Pill, DrugGen generates candidate
SMILES from a supplied UniProt target and the name resolver maps supplied
compound names or SMILES; the public workflow contains no target-to-DrugBank
retrieval or disease-to-target discovery agent.

### Related Work insertion

Recent systems demonstrate complementary forms of agentic drug discovery.
CLADD uses collaborative RAG agents, biomedical knowledge graphs, and molecular
representations for target and property-oriented inference. Prompt-to-Pill
connects modular molecular-generation, docking, ADMET, optimization, and
clinical-simulation components in a DPP-4 proof of concept. Robin connects
literature-grounded therapeutic hypothesis generation with human-executed
experiments and autonomous analysis of flow-cytometry and RNA-seq data.
FROGENT is evaluated here for a different combination of retrieval, target
validation, small-molecule and peptide design, interaction analysis, tool use,
and feedback-based model allocation. We consequently position the contribution
through its demonstrated workflow and evaluation scope rather than a global
priority claim.

### Capability-matrix note

| System | Public code status | Primary evaluated scope | Peptide design | Molecular generation | Wet-lab feedback | Eight-task numerical status |
| --- | --- | --- | --- | --- | --- | --- |
| CLADD | Apache-2.0 repository; commit `a7ee2e5` | Molecular RAG, target/property prediction | No | No | No | Property cell 0.8239; other cells `not_measured` |
| Prompt-to-Pill | Public repository; commit `817e177`; code license unverified | DPP-4 modular target-to-clinical simulation | No | DrugGen component | No | Property/screening/design 0.8540/0.8947/0.8383; other cells `not_measured` |
| Robin | Apache-2.0 repository; commit `4a5cce3` | Literature hypothesis, wet lab, experimental-data analysis | No | No | Yes, human executed | Known-drug/known-target retrieval 0.6650/0.2833; wet-lab cells `not_measured` |
| FROGENT | Submitted system | Retrieval, target validation, small-molecule and peptide design, docking, ADMET, retrosynthesis | Yes | Yes | No | Submitted task suite |

## Evidence

- Luteolin run: `runtime/evaluation/revision-20260730/nongpu-final/luteolin-comparison/`
- Luteolin final manifest: `runtime/evaluation/revision-20260730/nongpu-final/luteolin-comparison/manifest.json`
- Recent-system audit: `runtime/evaluation/revision-20260730/nongpu-final/recent-baselines/`
- Recent-system final manifest: `runtime/evaluation/revision-20260730/nongpu-final/recent-baselines/manifest.json`
- Current-model adaptation final manifest: `runtime/evaluation/revision-20260810/external-sol-resource-enabled-recovery-r05/analysis/combined-final-manifest.json`
- Generated-molecule blocks: `docs/manuscript/cbgbench-rebuttal-blocks.md`
- Prompt-to-Pill: https://doi.org/10.1093/bioadv/vbaf323
- CLADD: https://arxiv.org/abs/2502.17506
- Robin: https://doi.org/10.1038/s41586-026-10652-y
