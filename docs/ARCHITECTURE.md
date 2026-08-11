# FROGENT Agent Architecture

## 产品边界

FROGENT 的产品核心由三类能力组成：

1. retrieval 与 Deep Research；
2. 定性科学判断和方案优先级；
3. 科学工具的可靠执行与结果解释。

Harness 统一管理 context、policy、memory、evidence、tool budget、events、停止条件
和恢复。App、Skills 与 MCP 都通过这条边界进入 runtime。

```text
User / web app / Skill
          |
          v
agent.app     request routing, sessions, SSE, persistence
          |
          v
agent.core    context, harness, evidence, registry, tool events
          |
    +-----+----------+-------------+
    |                |             |
 research          design       molecular / docking
    |                |             |
 providers       hypotheses     RDKit / ADMET / Vina / PLIP
    +----------------+-------------+
                     |
                     v
        admitted evidence + decision memory
```

## Python domains

| Package | Responsibility |
|---|---|
| `agent.app` | Web bridge, request routing, persistent conversation memory, service factory |
| `agent.core` | Stable contracts, capability catalog, harness, evidence ledger, retrieval |
| `agent.research` | Literature providers, OA readers, screening, expansion, synthesis |
| `agent.design` | Qualitative hypothesis generation, calibration, prioritization, design memory |
| `agent.molecular` | Molecular identity, PubChem binding, deterministic descriptors and similarity, ADMET workflow and molecular chat |
| `agent.docking` | Target/pocket identity, preparation states, Vina execution and PLIP analysis |
| `agent.llm` | Typed Codex roles, native schemas and fail-closed model boundary |
| `agent.evaluation` | Active evaluation schema, integrity checks, metrics and replay |

Each domain is a flat package. Modules stay at or below 260 lines and keep control-flow nesting
bounded. Optional scientific dependencies load inside adapters so the control plane remains
importable with the standard library.

Domain dependencies follow one direction:

```text
core -> research -> llm -> design / molecular -> docking -> app
evaluation
```

`evaluation` stays independent. Higher workflow layers may use the layers to their left; lower
layers cannot import product routing or feature handlers from layers to their right. Architecture
tests enforce this dependency budget so orchestration cannot leak back into `core`.

The web surface keeps transport concerns split: `app/server.py` owns HTTP/auth/routes,
`app/chat.py` owns SSE/history/attachment context, `app/report_export.py` owns deterministic
Markdown/PDF/Word rendering, and `app/models.py` owns persistent web records. `agent.app`
connects that transport surface to typed Agent workflows.

## Decision workflow

Every scientific request is classified as `qualitative`, `quantitative`, or `hybrid`.

- A calibrated discriminator that covers the requested design space may drive quantitative search.
- Missing or partial discriminators trigger knowledge-led hypothesis generation.
- Tools verify identity, hard constraints, contradictions and comparative signals.
- The Agent returns ranked recommendations, expected gains, tradeoffs, likely failure modes and
  the most informative experiment.
- Uncertainty changes rank, confidence or experiment choice; it does not erase useful proposals.

Model memory may seed retrieval candidates. External sources must verify them before evidence
admission.

## Research flow

```text
Question
  -> typed search plan
  -> provider queries and author/citation expansion
  -> canonical study-family deduplication
  -> JATS / BioC / repository PDF / abstract preparation
  -> bounded parallel Readers
  -> Screener
  -> EvidenceLedger
  -> synthesis with exact evidence IDs
  -> checkpoint and cross-chat memory
```

Reader identity, record identity and task identity are checked before admission. Retractions,
corrections, abstract-only evidence and provider gaps remain explicit. Revocation preserves the
checkpoint while removing affected evidence from future synthesis.

The project-contained `structured-retrieval` MCP adds two typed routes to this flow. Disease
queries resolve to canonical Open Targets records and retain the provider-ranked associated
targets. Protein queries resolve to reviewed human UniProtKB records and retain their DrugBank
cross-references. Exact identifier-list contracts bind these validated records deterministically;
the Agent remains responsible for query planning, ambiguity resolution, biological interpretation
and evidence synthesis. This prevents free-form generation from silently reordering a canonical
database answer.

## Molecular and docking flow

```text
User-selected structure
  -> RDKit normalization
  -> optional PubChem verification
  -> exact full/parent binding
  -> deterministic physicochemical descriptors / Morgan-Tanimoto similarity
  -> ADMET or verified target/pocket workflow
  -> ligand/receptor state preparation
  -> Vina poses
  -> explicit pose selection
  -> PLIP interactions
```

Every tool result retains molecule scope, canonical SMILES, InChIKey, target/pocket artifacts,
preparation provenance and role order. Predictions remain computational evidence. The Agent uses
them to adjust a recommendation while preserving medicinal-chemistry judgment.

The project-contained `chemistry` MCP exposes deterministic RDKit descriptors,
explicit-reference Morgan similarity, target-aware ChEMBL known-active similarity and RCSB PDB
co-crystal ligand matching through stable capability IDs. These calls support drug-likeness
checks, novelty triage and target-conditioned virtual-screening prioritization. Retrieved records
retain target or PDB resolution, activity filters, chemical-component identity and provenance.
Similarity remains a retrieval signal and does not establish affinity. Optional pKa/logD
predictors and learned molecular proxy models remain deferred until their dependencies and live
execution are verified.

## Repository surfaces

- `skills/` contains user-facing workflows and tool policies.
- `mcp/` contains executable MCP integration code.
- `app/` contains the maintained web surface.
- `evaluation/` contains current capability cases and benchmark code.
- `runtime/` contains local execution state and project-contained tools.

The tracked tree contains the current product and current quality evidence. Previous repository
states remain recoverable through Git.
