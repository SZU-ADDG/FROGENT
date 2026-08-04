# FROGENT model policy

## Active roles

| FROGENT Agent arm | Pinned model | Purpose |
|---|---|---|
| DeepSeek arm | `deepseek-v4-flash` | Planning, reading, screening, synthesis and scientific workflow decisions |
| Codex arm | `gpt-5.6-luna` with `model_reasoning_effort=max` | The same FROGENT Agent roles through the Codex-compatible boundary |

Each benchmark protocol records one model per arm. Outputs from DeepSeek and Luna are not pooled
inside a comparison arm. Model substitutions require a new protocol or an explicit amendment.

## Runtime configuration

The active local runtime defaults to the DeepSeek backend and reads its credential only from
`DEEPSEEK_API_KEY`. It does not persist the credential in prompts, reports or manifests.

```text
FROGENT_LLM_BACKEND=deepseek
FROGENT_DEEPSEEK_MODEL=deepseek-v4-flash
FROGENT_DEEPSEEK_BASE_URL=https://api.deepseek.com
```

The Luna/max alternative is selected explicitly:

```text
FROGENT_LLM_BACKEND=codex
FROGENT_CODEX_EXECUTABLE=/Applications/ChatGPT.app/Contents/Resources/codex
FROGENT_CODEX_MODEL=gpt-5.6-luna
FROGENT_CODEX_REASONING_EFFORT=max
```

The third-party production tree on `doomx_3nd` remains read-only. Its current provider selection
is an external deployment fact and is not silently rewritten by this local policy.

## Provider acceptance status

The exact model name, OpenAI-compatible endpoint, JSON output and tool-call capabilities are
defined in the official [DeepSeek API documentation](https://api-docs.deepseek.com/quick_start/pricing).
The 2026-08-04 local canary preserved one request-validation failure followed by two consecutive
HTTP 503 provider-availability failures. `deepseek-v4-flash` remains pinned for the DeepSeek arm;
that arm is accepted only after a fresh canary reaches a valid terminal tool call.

The Luna/max alternative passed a structured live canary on 2026-08-04 with the installed
ChatGPT.app bundled `codex-cli 0.146.0-alpha.9.2`. The PATH-selected `codex-cli 0.136.0` is too old
for Luna. The accepted runtime therefore uses the bundled executable, literal `max` reasoning,
read-only sandbox and ephemeral execution. Luna runs remain separate from DeepSeek benchmark arms.
