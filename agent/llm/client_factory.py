"""Select one declared LLM boundary for a FROGENT runtime."""

import os
from pathlib import Path

from agent.llm.codex_client import CodexClient
from agent.llm.deepseek_client import DeepSeekClient

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
    }


def build_llm_client(root: Path, *, backend: str, deepseek_model: str,
                     deepseek_base_url: str, deepseek_timeout: float | None,
                     codex_model: str, codex_reasoning_effort: str, codex_executable: str,
                     codex_timeout: float | None, runner=None):
    if runner is not None or backend == "codex":
        options = {"timeout": codex_timeout, "executable": codex_executable,
                   "model": codex_model, "reasoning_effort": codex_reasoning_effort}
        if runner is not None:
            options["runner"] = runner
        return CodexClient(root, **options)
    if backend == "deepseek":
        return DeepSeekClient(root, model=deepseek_model, base_url=deepseek_base_url,
                              timeout=deepseek_timeout)
    raise ValueError("FROGENT_LLM_BACKEND must be 'deepseek' or 'codex'")
