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

1. Use `$prepare-molecule` to validate the target structure and preserve the submitted representation.
2. Use `$prioritize-design-hypotheses` to propose distinct disconnection strategies from reaction knowledge, functional-group compatibility, stereochemical control, protecting-group burden, convergence, and likely starting-material accessibility.
3. Start with `retrosynthesis.flash` for a fast, shallow route set and compare it with the expert route families.
4. Check every route against user constraints and record unsupported steps.
5. Use `retrosynthesis.explorer` when the fast search has no viable route, low confidence, or insufficient depth.
6. Search papers, patents, and purchasable starting materials for the decision-critical transformations.
7. Rank viable routes by chemical plausibility, convergence, step count, constraint fit, starting-material availability, operational risk, and verification cost.
8. Stop when a route is actionable for the stated decision or the agreed search budget is exhausted.

## Output

Lead with the route to try first and the strongest alternative. Return structured route trees with intermediates, transformations, starting materials, search mode, constraint violations, expert rationale, failure-prone steps, confidence, and the first experiment or literature check.

## Guardrails

- Keep alternative branches intact.
- Provide plausible reagent classes and condition families as expert route hypotheses when they make the proposed transformation actionable. Keep exact reported reagents, conditions, yields, and availability claims tied to verified literature, patents, catalogs, or tool results.
- Mark chemically implausible or tool-incomplete steps for expert review.
- Treat generated routes as planning hypotheses until experimentally assessed.
