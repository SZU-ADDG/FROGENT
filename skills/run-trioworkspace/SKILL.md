---
name: run-trioworkspace
description: Submit, monitor, and retrieve results from the private TrioWorkspace engines through the FROGENT MCP boundary. Use for TrioMol2 structure-based molecule generation, TrioPep receptor-conditioned peptide design, the accepted BRD4 TrioPROTAC task, CrPV or PSIV TrioIRES design, or exact-context TrioDNA sequence design.
---

# Run TrioWorkspace

## Choose an aligned engine

- Use TrioMol2 with an exact receptor PDB and verified pocket center and size.
- Use TrioPep with an exact receptor PDB, receptor chain, distinct peptide chain, and peptide length.
- Use TrioPROTAC only for the accepted `brd4-8g46` target system.
- Use TrioIRES only for the accepted `CrPV` or `PSIV` family.
- Use TrioDNA with an exact 200-base reference, accepted cell context, and 1-indexed editable interval.
- Call `trio_capabilities` when the accepted contract is unclear. Do not invent unsupported targets or widen an engine contract.

## Prepare the scientific decision

Classify the request as qualitative, quantitative, or hybrid. Generate and rank the scientific
hypotheses before execution whenever important design choices remain. Use TrioWorkspace as a
quantitative candidate-generation or evaluation arm within that reasoning; keep world knowledge,
mechanistic rationale, medicinal-chemistry judgment, tradeoffs, and decisive experiments in the
final recommendation.

Place receptor PDB inputs inside the FROGENT project. Verify molecular, target, chain, pocket,
sequence, and role identities with the existing FROGENT Skills before submission.

## Execute asynchronously

1. Call exactly one typed `trio_submit_*` tool with the accepted parameters.
2. Preserve the returned task ID, contract version, engine, and input summary.
3. Poll `trio_get_task`; use `trio_list_tasks` only to recover an owned task ID.
4. Continue until `succeeded`, `failed`, or `cancelled`. Do not impose a fixed wall-clock timeout.
5. Download each required artifact with `trio_download_artifact`. Use only the returned verified
   project-local path and retain artifact ID, byte size, content type, and SHA-256 provenance.

Never resubmit a running task merely because it takes time. A submission changes the private
remote queue, so report the task ID immediately and avoid duplicate calls.

## Interpret results

Treat engine outputs as computational evidence. Compare them with the ranked knowledge-led
hypotheses, experimental evidence, counterevidence, and known applicability limits. Tool failure
reduces confidence or changes the next experiment while preserving useful expert recommendations.
Lead with the prioritized scientific action and use only the uncertainty that changes ranking,
scope, or the next decisive experiment.
