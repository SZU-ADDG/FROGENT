# Paired base-model and FROGENT benchmark protocol

Date frozen: 2026-08-05
Status: implementation and canary in progress

## Scientific question

For each current base model, how does performance on the same exposed eight-task panel change when
the model runs directly versus when it is used as the reasoning boundary inside FROGENT?

## Paired arms

### Direct-model arm

The model receives the frozen task cases and output schema. FROGENT initialization, retrieval,
memory, scientific tools and web access are absent.

### FROGENT arm

The exact same model ID is bound to FROGENT's structured reasoning roles. The frozen FROGENT
workflow may route retrieval, evidence admission, molecular-property calculation, docking or
interaction analysis, qualitative scientific judgment and retrosynthesis tools when the task
requires them. Every tool result and failure is recorded. Gold answers remain unavailable until
deterministic scoring.

## Models

The paired panel contains GPT-5.4, GPT-5.5, GPT-5.6 Sol, DeepSeek V4 Flash, DeepSeek V4 Pro,
Kimi K2.5, Qwen3.7 Plus, GLM 5.2, MiniMax M3, MiMo V2.5, Kimi K3 and Qwen3.8 Max. Exact OpenRouter
IDs for the added models are `moonshotai/kimi-k3` and `qwen/qwen3.8-max`.

## Comparability rules

- Both arms use the same 20 exposed cases for each of eight task families.
- Both arms use the same output schema and deterministic task scorer.
- Each FROGENT model-task cell starts with isolated conversation and working memory.
- Tool artifacts that are deterministic and independent of the base model may be computed once,
  content-addressed and supplied identically to every FROGENT model.
- Model-specific retrieval choices, evidence admission, synthesis and scientific judgment remain
  part of the measured FROGENT execution.
- Successful direct cells are reused. Kimi K3 and Qwen3.8 Max receive new direct cells.
- A failed cell remains visible. Recovery requires a new amendment and may change transport
  compatibility only.

## Primary outputs

For each model and task, report:

1. direct-model score;
2. FROGENT score;
3. paired delta, `FROGENT - direct`;
4. completion, tool-use, latency and cost;
5. case-level errors and the tool or reasoning stage responsible.

The model-level macro mean remains descriptive because task metrics have different meanings.
Primary inference uses paired case-level deltas within each task and a pocket- or target-aware
cluster bootstrap where cases share a biological target.

## Exact-cell recovery amendment — 2026-08-05

The first 12-model FROGENT arm reached terminal state for all 96 model–task
cells: 85 succeeded and 11 failed. The failures comprise transient upstream
HTTP 429/disconnection errors and null or invalid structured-response content.
All 85 successful cells remain immutable.

Recovery is restricted to the 11 failed model–task pairs, each in a fresh run
root. No successful cell may be resubmitted. The direct Qwen3.8 Max extension
likewise preserves its seven successful cells and retries only
`retrieve_known_drugs`, whose provider response contained null message content.
Recovered cells are merged only at analysis time with explicit source-run
provenance.

### Recovery amendment r23

The r22 exact retry recovered five FROGENT cells and left six FROGENT cells
plus one direct Qwen3.8 cell unresolved. The unresolved structured-response
failures occurred under five-case requests; the two MiniMax cells failed under
upstream HTTP 429 rate limiting.

The r23 recovery changes request grain from five cases to one case for the
seven unresolved cells and enables bounded retry only for HTTP
429/502/503/504 or connection failures. Task inputs, exact model IDs, frozen
tool evidence, output schema, temperature, scoring code and gold isolation are
unchanged. Qwen3.8 direct retains low reasoning and increases the output token
ceiling to avoid a reasoning-only truncated response. Original r20–r22
failures remain immutable.

The author explicitly allowed switching OpenRouter suppliers for recovery.
Accordingly, r23 permits provider fallback while preserving each exact model
ID and records the returned provider per request. Provider switching is
reported as a recovery transport amendment and is not pooled silently with
the original provider route.

The single-case canary showed a provider schema quirk: several models returned
five outer `results` entries carrying the same requested `case_index`, apparently
confusing the outer result count with a nested five-item task field. Recovery
retains the complete unvalidated response, deterministically keeps the first
outer result in provider order, records whether discarded repetitions were
identical, and then applies the unchanged frozen schema and scorer. No gold or
score is consulted during normalization.

With provider fallback enabled, a second observed variant expanded a one-case
request into outer results for neighboring case indices. The normalization
therefore selects the first result whose `case_index` equals the sole requested
case and discards every out-of-scope result. Counts and the full unvalidated
response remain recorded before frozen-schema validation.

Qwen3.8 direct r23 completed cases 1–4 and then returned null content for case
5. The subsequent direct recovery uses up to five stateless attempts per
single-case batch, retains every attempt envelope, and accepts the first
schema-valid response without consulting gold or score.

The sequential direct recovery was stopped after preserving its partial
attempt envelopes because Qwen3.8 required several minutes per independent
case. The replacement run dispatches at most five independent one-case
batches concurrently. This changes wall-clock scheduling only; model,
provider policy, seed, prompt, schema, attempts and scoring remain frozen.

For paired Qwen3.8 and DeepSeek Flash, validated single-case batches from a
failed recovery root may be reused by exact payload hash and source path.
Only missing or invalid batches are requested again. Qwen3.8's output ceiling
is raised to 48,000 tokens for the remaining batches because five attempts for
case 5 ended with null structured content; reasoning remains low and the
schema is unchanged.

DeepSeek Flash exposed multiple live suppliers. After the default route stalled
on case 5, the recovery prioritizes BaseTen, DeepInfra and Baidu while allowing
fallbacks, with the actual returned supplier recorded per request. The exact
model ID remains `deepseek/deepseek-v4-flash-0731`.

DeepSeek Flash repeatedly spent the full request on uncertain long mTOR
structures. The final recovery makes the existing “when known” instruction
explicit: return fewer entries when an exact ID or SMILES is unknown and do
not approximate a long structure. The schema already permits up to five
entries, so this clarification changes neither the accepted output domain nor
the scorer.

### DeepSeek Flash provider failover amendment r38

The DeepInfra-pinned r36 recovery produced and validated cases 1–12 of the
20-case `retrieve_known_drugs` task. Its case-13 request remained live without
a response for more than seven minutes after the preceding cases had completed
normally. The process was stopped without altering any validated output. The
exact continuation uses a new run root, reuses only the twelve validated r36
case outputs, and routes cases 13–20 to BaseTen. The model identifier, frozen
evidence, prompts, concise-response instruction, token ceiling, scorer and all
other conditions remain unchanged. This is provider failover, not a model or
benchmark change.

The first failover candidate, BaseTen, returned an immediate OpenRouter 404 for
the exact model despite appearing in the live endpoint catalogue; r38 is
retained as failure evidence. During process shutdown, the in-flight DeepInfra
worker completed and validated cases 13–19. A byte-for-byte r39 resume bundle
therefore combines validated cases 1–4 from r29 and cases 5–19 from r36. The
runner accepts one resume root, so this bundle changes no response content and
exists only to prevent resubmission. The fresh r40 continuation requests only
case 20 from the live GMICloud endpoint for the same exact model.

GMICloud also returned the same immediate OpenRouter 404 under the frozen
structured-output request. The r41 exact continuation permits provider fallback
in the live order Novita, Cloudflare, then DeepInfra and still requests only
case 20. The actual provider is retained in request metadata.

## Final outcome

Both arms completed `96/96` scored model–task cells. All twelve base models had
a higher eight-task macro mean inside FROGENT. The fixed-panel average changed
from 0.3714 for direct inference to 0.4660 with FROGENT, a delta of +0.0946.
The preregistered case-level analysis first averages the paired delta over the
twelve fixed models for each exposed case, then resamples target/pocket
clusters within each task for 10,000 deterministic bootstrap iterations
(seed 20260805). The macro delta across eight tasks has a 95% percentile
interval of [0.0678, 0.1201].

Mechanism, molecular-property prediction and retrosynthesis have task-level
intervals above zero. The intervals for foundational knowledge, known-drug
retrieval, known-target retrieval, virtual screening and molecular design
include zero. The result therefore supports a system-level gain on this fixed
exposed-case panel together with substantial task heterogeneity. It does not
establish performance on unseen tasks, provider reliability, biological
efficacy or an unconditional base-model ranking. The complete manifest,
case-level statistics and figure are stored under
`runtime/evaluation/revision-20260805/paired-twelve-model-frogent-final-r42/analysis/`.
