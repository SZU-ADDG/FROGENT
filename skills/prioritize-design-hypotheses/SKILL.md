---
name: prioritize-design-hypotheses
description: Generate and rank medicinal-chemistry, peptide, target, or route-design hypotheses when no reliable discriminator fully determines the answer. Use for lead optimization, unexplored modifications, mechanism-led design, portfolio choices, and requests that need expert judgment before wet-lab validation.
---

# Prioritize Design Hypotheses

Turn underdetermined scientific choices into an actionable, ranked experimental portfolio. Use model world knowledge, medicinal-chemistry experience, mechanistic reasoning, and relevant precedent as first-class design inputs.

## Workflow

1. Define the decision objective, immutable constraints, baseline, and desired biological or chemical change.
2. Classify the problem:
   - `quantitative`: an objective-aligned, calibrated discriminator covers the decision space;
   - `qualitative`: no reliable discriminator can select the design;
   - `hybrid`: measurements can compare candidates while key choices still require scientific judgment.
   For a quantitative problem, define the objective, constraints, and search space, then hand candidate optimization to the suitable algorithm, model, evolutionary loop, or reinforcement-learning loop.
3. For qualitative or hybrid work, generate three to six meaningfully different hypotheses before broad scoring. Draw on known SAR patterns, bioisosteres, physicochemical tradeoffs, conformational control, exposure, selectivity, stability, mechanism, and synthesis practicality as relevant.
4. Rank the hypotheses by expected decision value. For each one, state the exact modification, rationale, expected benefit, tradeoff, plausible failure mode, confidence, and the smallest decisive experiment.
5. Use literature, RDKit, identity resolution, structure analysis, docking, PLIP, ADMET, retrosynthesis, or other available tools to challenge assumptions, catch hard conflicts, and update priority. Keep each signal in its evidence tier.
6. Reject a hypothesis only for an immutable-constraint violation, identity error, chemically impossible construction, or strong contradictory evidence. Downgrade weaker contradictions. Preserve a useful recommendation when a tool is unavailable or inconclusive.
7. Diversify the final set across mechanisms or risk profiles so one wrong assumption does not collapse the whole experiment.

## Output

Lead with the ranked recommendations. For every hypothesis include:

- modification or design action;
- why it is worth doing;
- expected gain and main tradeoff;
- knowledge basis and any tool calibration;
- failure mode and falsification experiment.

Finish with a compact experiment order. Put routine uncertainty in one short section and expand it only when it changes rank, scope, or assay choice.

## Guardrails

- Label world-knowledge and expert-judgment statements as design hypotheses; reserve factual evidence claims for verified sources.
- Do not turn prediction uncertainty into repetitive disclaimers.
- Do not let a convenient proxy replace the user's biological objective.
- Ask for user input only when a missing choice would produce materially different chemistry or violate consent, identity, or safety boundaries.
