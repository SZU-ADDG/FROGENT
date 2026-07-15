---
name: plan-retrosynthesis
description: Generate and compare retrosynthetic routes for a target molecule with fast and deeper search modes. Use for synthesis feasibility checks, route planning, or finalist triage.
---

# Plan Retrosynthesis

Build a route set with explicit search depth, assumptions, and stopping conditions.

## Required inputs

- Valid target structure, preferably canonical SMILES
- Route constraints, available starting materials, and forbidden chemistry
- Desired search depth or time budget

## Workflow

1. Validate the target structure and preserve the submitted representation.
2. Start with `retrosynthesis.flash` for a fast, shallow route set.
3. Check every route against user constraints and record unsupported steps.
4. Use `retrosynthesis.explorer` when the fast search has no viable route, low confidence, or insufficient depth.
5. Compare viable routes by step count, constraint fit, starting-material availability, and unsupported assumptions.
6. Stop when a satisfactory route is found or the agreed search budget is exhausted.

## Output

Return structured route trees with intermediates, transformations, starting materials, search mode, constraint violations, and confidence notes. Recommend a route only when its evidence is complete enough for the stated decision.

## Guardrails

- Keep alternative branches intact.
- Do not invent reagents, conditions, yields, or availability data.
- Mark chemically implausible or tool-incomplete steps for expert review.
- Treat generated routes as planning hypotheses until experimentally assessed.
