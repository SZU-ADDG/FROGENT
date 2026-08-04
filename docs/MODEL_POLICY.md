# FROGENT model policy

## Active roles

| Role | Pinned model | Purpose |
|---|---|---|
| FROGENT Agent | `deepseek-v4-flash` | Planning, reading, screening, synthesis and scientific workflow decisions |
| Codex engineering and acceptance | `gpt-5.6-terra` | Implementation, orchestration, diagnostics and independent acceptance |

Each benchmark protocol records one model per arm. Outputs from DeepSeek and Terra are not pooled
inside a comparison arm. Model substitutions require a new protocol or an explicit amendment.

## Runtime configuration

The active local runtime defaults to the DeepSeek backend and reads its credential only from
`DEEPSEEK_API_KEY`. It does not persist the credential in prompts, reports or manifests.

```text
FROGENT_LLM_BACKEND=deepseek
FROGENT_DEEPSEEK_MODEL=deepseek-v4-flash
FROGENT_DEEPSEEK_BASE_URL=https://api.deepseek.com
```

The Codex fallback is selected explicitly and defaults to Terra:

```text
FROGENT_LLM_BACKEND=codex
FROGENT_CODEX_MODEL=gpt-5.6-terra
```

The third-party production tree on `doomx_3nd` remains read-only. Its current provider selection
is an external deployment fact and is not silently rewritten by this local policy.

## Provider acceptance status

The exact model name, OpenAI-compatible endpoint, JSON output and tool-call capabilities are
defined in the official [DeepSeek API documentation](https://api-docs.deepseek.com/quick_start/pricing).
The 2026-08-04 local canary preserved one request-validation failure followed by two consecutive
HTTP 503 provider-availability failures. DeepSeek remains the pinned FROGENT Agent model; a run is
accepted only after a fresh canary reaches a valid terminal tool call. Terra runs are declared as
separate Codex-side work and are never merged into a DeepSeek benchmark arm.
