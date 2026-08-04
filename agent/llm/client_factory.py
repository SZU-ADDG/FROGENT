"""Select one declared LLM boundary for a FROGENT runtime."""

from pathlib import Path

from agent.llm.codex_client import CodexClient
from agent.llm.deepseek_client import DeepSeekClient


def build_llm_client(root: Path, *, backend: str, deepseek_model: str,
                     deepseek_base_url: str, deepseek_timeout: float | None,
                     codex_model: str, codex_executable: str,
                     codex_timeout: float | None, runner=None):
    if runner is not None or backend == "codex":
        options = {"timeout": codex_timeout, "executable": codex_executable,
                   "model": codex_model}
        if runner is not None:
            options["runner"] = runner
        return CodexClient(root, **options)
    if backend == "deepseek":
        return DeepSeekClient(root, model=deepseek_model, base_url=deepseek_base_url,
                              timeout=deepseek_timeout)
    raise ValueError("FROGENT_LLM_BACKEND must be 'deepseek' or 'codex'")
