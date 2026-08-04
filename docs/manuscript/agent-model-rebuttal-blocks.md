# FROGENT Agent model boundary — manuscript and rebuttal blocks

Date: 2026-08-04

Status: working draft. The runtime boundary and canary outcomes are frozen. Production deployment
facts, training or few-shot history, final section/page/line numbers and benchmark-level Agent
performance remain `to verify` or `not_measured` as specified below.

## AC-facing conclusion

The revised implementation exposes two explicit, mutually exclusive FROGENT Agent
configurations: `deepseek-v4-flash`, or `gpt-5.6-luna` with
`model_reasoning_effort=max`. A run or benchmark arm freezes one configuration and does not pool
outputs across models. The Luna/max structured canary passed with the already installed
ChatGPT.app Codex executable. The DeepSeek canary reached request validation and provider
availability failures before verified inference, so DeepSeek-backed Agent performance remains
unmeasured until a new canary passes. This local model policy does not silently rewrite the
read-only production deployment on `doomx_3nd`.

## Proposed Methods paragraph

FROGENT selects its Agent model through an explicit runtime boundary. The DeepSeek configuration
uses `deepseek-v4-flash` through the OpenAI-compatible chat-completions interface and reads its
credential only from the `DEEPSEEK_API_KEY` environment variable. The Codex-compatible
configuration uses `gpt-5.6-luna` with literal `model_reasoning_effort=max` through the installed
ChatGPT.app Codex executable. Each protocol records the backend, exact model, reasoning effort
when applicable, executable/version, sandbox and persistence mode. One configuration is frozen
per run or comparison arm; outputs from different models are not pooled. Credentials are excluded
from prompts, reports and manifests. Model substitutions require a new protocol or an explicit
amendment.

## Proposed Results paragraph

The Luna/max structured canary completed with exit code zero using Codex
`0.146.0-alpha.9.2`, read-only sandboxing and ephemeral execution, and returned the exact
schema-valid object `{"status":"ok"}` without an observed project write. The PATH-selected Codex
`0.136.0` first rejected the literal `max` tier and then failed the Luna client-version gate; both
attempts were retained as negative compatibility evidence. For DeepSeek, the first canary returned
HTTP 400 because default thinking mode is incompatible with a forced `tool_choice`. A
compatibility-only amendment disabled thinking; that run and one identical retry both returned
HTTP 503 before inference. DeepSeek tool use and benchmark performance therefore remain
`not_measured`. The obsolete fallback sentence inside the immutable DeepSeek r03 failure artifact
is superseded by the active policy: the only accepted alternatives are DeepSeek V4 Flash and
Luna/max.

## Supplementary configuration and acceptance table

| Arm | Frozen configuration | Acceptance evidence | Current disposition |
|---|---|---|---|
| DeepSeek | `deepseek-v4-flash`; OpenAI-compatible endpoint; thinking disabled for the forced-tool canary | r01: HTTP 400 request-compatibility failure; r02/r03: HTTP 503 before inference | Configuration retained; live Agent/tool behavior and benchmark performance `not_measured` pending a fresh passing canary |
| Codex | `gpt-5.6-luna`; `model_reasoning_effort=max`; ChatGPT.app bundled Codex `0.146.0-alpha.9.2`; read-only; ephemeral | r03: exit zero, exact schema-valid `{"status":"ok"}`, no observed project write | Accepted as a runtime transport/schema configuration; scientific task quality requires the relevant frozen benchmark |
| Legacy PATH client | Codex `0.136.0` | r01 rejected literal `max`; r02 hit the Luna client-version gate | Ineligible for Luna/max FROGENT Agent runs |
| Production deployment | Read-only third-party deployment on `doomx_3nd` | Configuration source audit only | External deployment fact; must be reported separately and is not changed by the local policy |

## Point-by-point response blocks

### E-2 / model and runtime reproducibility

**Response.** We added an explicit model boundary and versioned acceptance evidence. Each FROGENT
run now freezes either DeepSeek V4 Flash or Luna with max reasoning, records the executable and
runtime mode, and prohibits pooling outputs across the two configurations. We also retain failed
provider/client attempts and exclude credentials from all reproducibility artifacts. The revised
Methods and Supplementary table distinguish a transport/schema canary from scientific benchmark
performance.

### E-5, R1-0d and R1-6 / manuscript-to-deployment consistency

**Response.** We separated the active local Agent model policy from the read-only third-party
production deployment. Luna/max passed the local structured canary; DeepSeek inference did not
reach a verified terminal result because two compatibility-correct requests returned HTTP 503.
Accordingly, the manuscript can describe both supported configuration boundaries, while live
DeepSeek performance and any unverified production-model assignment remain `not_measured` until
their own versioned runs pass.

### R1-0b / fine-tuning, few-shot and in-context terminology

**Response.** The model-selection evidence establishes runtime configuration only. It does not
establish whether the submitted experiments used parameter fine-tuning, few-shot examples,
in-context examples, cache reuse or persistent memory. We therefore retain those facts as an
author-input requirement and will use the corresponding term only after the training, prompt and
test-isolation record is supplied.

## Required claim changes

- Retain: two explicit FROGENT Agent configuration options; one frozen model per run/arm;
  Luna/max transport and structured-output acceptance with the recorded executable.
- Narrow: a successful canary supports configuration and tool transport, not scientific quality or
  benchmark superiority.
- Remove: any active fallback outside `deepseek-v4-flash` or `gpt-5.6-luna` with max reasoning;
  any implication that the local policy rewrote the production deployment.
- `not_measured`: DeepSeek inference/tool acceptance after the two HTTP 503 failures; comparative
  task performance between DeepSeek and Luna; production model identity not bound to a versioned
  run; fine-tuning, few-shot, cache and test-overlap history.

## Frozen evidence sources

- `docs/MODEL_POLICY.md`
- `runtime/evaluation/revision-20260804/deepseek-v4-flash-canary-r01/`
- `runtime/evaluation/revision-20260804/deepseek-v4-flash-canary-r02/`
- `runtime/evaluation/revision-20260804/deepseek-v4-flash-canary-r03/`
- `runtime/evaluation/revision-20260804/luna-max-structured-canary-r01/`
- `runtime/evaluation/revision-20260804/luna-max-structured-canary-r02/`
- `runtime/evaluation/revision-20260804/luna-max-structured-canary-r03/`
