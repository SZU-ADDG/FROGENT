# PLAN forward v2 aborted prompt-assembly run

Status: `ABORTED_INPUT_IDENTITY_MISMATCH`

This run was stopped before an official v2 effect result was created. The pre-worker lock remains commit `e1304fc` and was not modified.

## Why the run is excluded

- The three `no_skill` workers received the locked common contract and baseline instruction in full.
- The three `single_skill` workers received compressed restatements of the common contract, Skill, and reference instead of their locked bytes.
- Worker identity was supplied as untyped `key=value` lines instead of the canonical JSON receipt. Two single-skill attempts consequently emitted numeric `replicate_label` values and failed schema validation.
- The actual arm inputs therefore violated the preregistered sole-variable and worker-input identity assumptions.

These attempts cannot support Skill-effect, retrieval-quality, or promotion claims. They are retained to preserve the negative experiment and orchestration failure.

## Preserved evidence

- `inputs/` contains the six raw worker responses without semantic repair.
- `result.json` is the deterministic evaluator result over those six inputs.
- Evaluator completion: `completed`.
- Worker completion: `incomplete` (`4` accepted/completed, `2` schema-invalid, `8` missing).
- Effect outcome: `rejected`.
- Promotion eligible: `false`.

The corrected run must restart all twelve workers with the exact locked common prompt, canonical JSON receipt, candidate task and constraint, plus the exact baseline instruction or exact Skill/reference bytes.
