"""Select one declared LLM boundary for a FROGENT runtime."""

import os
from pathlib import Path
from typing import Mapping

from agent.llm.codex_client import CodexClient
from agent.llm.deepseek_client import DeepSeekClient
from agent.llm.openrouter_client import OpenRouterClient

CODEX_EXECUTABLE = "/Applications/ChatGPT.app/Contents/Resources/codex"


def llm_settings_from_env() -> dict[str, str]:
    """Read non-secret model selection without materializing provider credentials."""
    return {
        "llm_backend": os.getenv("FROGENT_LLM_BACKEND", "deepseek").strip().lower(),
        "deepseek_model": (os.getenv("FROGENT_DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
                           or "deepseek-v4-flash"),
        "deepseek_base_url": (os.getenv("FROGENT_DEEPSEEK_BASE_URL",
                                         "https://api.deepseek.com").strip()
                              or "https://api.deepseek.com"),
        "codex_model": (os.getenv("FROGENT_CODEX_MODEL", "gpt-5.6-luna").strip()
                        or "gpt-5.6-luna"),
        "codex_reasoning_effort": (os.getenv("FROGENT_CODEX_REASONING_EFFORT", "max").strip()
                                   or "max"),
        "codex_executable": (os.getenv("FROGENT_CODEX_EXECUTABLE", CODEX_EXECUTABLE).strip()
                             or CODEX_EXECUTABLE),
        "openrouter_model": os.getenv("FROGENT_OPENROUTER_MODEL", "").strip(),
        "openrouter_base_url": (
            os.getenv("FROGENT_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
            or "https://openrouter.ai/api/v1"
        ),
    }


def build_llm_client(root: Path, *, backend: str, deepseek_model: str,
                     deepseek_base_url: str, deepseek_timeout: float | None,
                     codex_model: str, codex_reasoning_effort: str, codex_executable: str,
                     codex_timeout: float | None, runner=None,
                     openrouter_model: str = "",
                     openrouter_base_url: str = "https://openrouter.ai/api/v1",
                     openrouter_timeout: float | None = None,
                     openrouter_reasoning: Mapping[str, object] | None = None,
                     openrouter_max_tokens: int = 12000,
                     openrouter_provider_order: tuple[str, ...] = ()):
    if runner is not None or backend == "codex":
        options = {"timeout": codex_timeout, "executable": codex_executable,
                   "model": codex_model, "reasoning_effort": codex_reasoning_effort}
        if runner is not None:
            options["runner"] = runner
        return CodexClient(root, **options)
    if backend == "deepseek":
        return DeepSeekClient(root, model=deepseek_model, base_url=deepseek_base_url,
                              timeout=deepseek_timeout)
    if backend == "openrouter":
        return OpenRouterClient(
            root,
            model=openrouter_model,
            base_url=openrouter_base_url,
            timeout=openrouter_timeout,
            reasoning=openrouter_reasoning,
            max_tokens=openrouter_max_tokens,
            provider_order=openrouter_provider_order,
        )
    raise ValueError("FROGENT_LLM_BACKEND must be 'deepseek', 'codex', or 'openrouter'")
