# Clean ten-model benchmark protocol

Date frozen: 2026-08-05
Status: complete; r03 primary plus r04-r17 compatibility/recovery evidence preserved

## Scientific question

How do ten current reasoning models compare on the same exposed, author-supplied eight-task
benchmark when prior FROGENT prompts, task memories, tools, web access, gold answers and persistent
sessions are excluded?

This panel measures clean model capability. It is a new baseline comparison and does not inherit
the submitted radar values or establish a FROGENT-system advantage.

## Frozen models

| Display name | Transport | Exact model ID | Reasoning setting |
|---|---|---|---|
| GPT-5.4 | bundled Codex | `gpt-5.4` | `low` |
| GPT-5.5 | bundled Codex | `gpt-5.5` | `low` |
| GPT-5.6 Sol | bundled Codex | `gpt-5.6-sol` | `low` |
| DeepSeek V4 Flash | OpenRouter | `deepseek/deepseek-v4-flash-0731` | `low`; compatibility recovery: disabled |
| DeepSeek V4 Pro | OpenRouter | `deepseek/deepseek-v4-pro` | `low`; compatibility recovery: disabled |
| Kimi K2.5 | OpenRouter | `moonshotai/kimi-k2.5` | `low`; compatibility recovery: disabled |
| Qwen3.7 Plus | OpenRouter | `qwen/qwen3.7-plus` | `low`; compatibility recovery: disabled |
| GLM 5.2 | OpenRouter | `z-ai/glm-5.2` | `low` |
| MiniMax M3 | OpenRouter | `minimax/minimax-m3` | `low` |
| MiMo V2.5 | OpenRouter | `xiaomi/mimo-v2.5` | `low`; compatibility recovery: disabled |

The three GPT arms use Codex authentication and never use the OpenRouter API. OpenRouter model IDs
are pinned; aliases ending in `latest` are excluded. Claude, Kimi K3, Grok and Gemini are excluded
by author instruction. Kimi K2.5 is explicitly permitted.

The r01 GPT-5.4/high success and r01/r02 DeepSeek length failures are compatibility pilots and do
not enter the comparison. The r03 panel requested `low` reasoning for all ten models and imposed a
12,000-token completion ceiling. Five OpenRouter models consumed the answer budget on hidden
reasoning and returned no answer content. Their failed r03 calls remain preserved; r04-r06 froze a
request-level compatibility change to `reasoning.enabled=false` before recovery output. R07-r17
freeze five-case request chunks for oversized or truncated Kimi, MiMo, GPT-5.5, GPT-5.6 Sol,
DeepSeek Pro and MiniMax cells, plus exact transient-rate-limit and provider-route recoveries. These
amendments do not change the cases, answer schema, gold data or scorer.

## Clean-execution boundary

- Every model--task cell starts from one stateless request.
- No submitted FROGENT system prompt, few-shot example, memory, thread history or project
  initialization is included.
- Gold fields are loaded only by the deterministic scorer after inference.
- Web search, user-defined tools and scientific tools are unavailable to the model.
- Codex uses the bundled executable, `--ephemeral`, `--ignore-user-config`, read-only sandboxing,
  disabled web search and an isolated nested working root with project-document loading set to
  zero. JSON event logs are retained to verify that no tool call contributed to an answer.
- OpenRouter receives one user message, a strict JSON Schema and `provider.allow_fallbacks=false`.
  Credentials remain in `OPENROUTER_API_KEY` and are never serialized.
- Failed calls remain failed. A compatibility-only retry requires a new amendment and cannot
  change model, prompt, cases or scorer.

## Cases and statistical unit

The source is the received `test_data.zip` extraction under
`runtime/evaluation/revision-20260804/source-material/eight-task-benchmark-r01/extracted`.
All eight task files contain 20 exposed cases. One invalid virtual-screening source row, whose gold
ligand is absent from its candidate pool, remains visible to the model and is excluded from that
task's accuracy denominator.

The statistical unit is a case. The primary request grain is all 20 cases for one task. For cells
that exceeded provider context, transport or answer-length constraints, preregistered
compatibility amendments use four isolated five-case requests. Outputs remain case-indexed and
are scored independently; batching is a transport compatibility factor and is reported rather
than interpreted as model quality.

## Task outputs and frozen primary scores

1. Foundational knowledge: normalized exact accuracy.
2. Known-drug retrieval: DrugBank-ID recall at five, averaged by case.
3. Known-target retrieval: exact-set macro F1, averaged by case.
4. Molecular properties: mean of five endpoint scores using the submitted capped-relative rule
   for QED and Caco-2 and exact accuracy for three binary endpoints.
5. Virtual screening: exact selected-ligand accuracy over the 19 valid cases.
6. Binding mechanism: exact field accuracy across the five submitted interaction-count fields.
7. Molecular design: mean of validity, within-case uniqueness, mean QED and normalized
   lower-is-easier SA. This is a computational molecule-quality score without docking or activity
   interpretation.
8. Retrosynthesis: mean of target-rooted parse validity and exact-reference reaction recall.
   Alternative chemically valid routes remain outside exact-reference scoring.

Every task score is reported on a 0--1 scale. The across-task macro mean is descriptive because the
eight axes use different scientific units.

## Figure contract

- Claim: current models show task-specific strengths and error profiles under a clean common
  protocol.
- Primary panel: 10-by-8 heatmap with exact cell values.
- Secondary panel: per-model macro mean with bootstrap 95% intervals over cases clustered by task.
- Statistical unit: case; task-cluster sensitivity is reported separately.
- Final width: 178 mm, vector PDF and SVG, plus 600 dpi PNG preview.
- Color: one sequential, colorblind-safe scale for 0--1 performance; transport is encoded by a
  small neutral annotation rather than performance color.
- Missing or failed cells are hatched and never imputed.

## Stopping rule

The panel stops after all 80 model--task cells reach a terminal state and deterministic scoring,
or after an unrecoverable provider/model incompatibility is preserved. No model is replaced after
observing scores.
