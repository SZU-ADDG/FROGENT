"""Contained ephemeral Codex subprocess boundary for structured roles."""

import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Mapping

Runner = Callable[[list[str], str, float | None, Path], str]


def _subprocess_runner(args: list[str], prompt: str, timeout: float | None, cwd: Path) -> str:
    completed = subprocess.run(args, input=prompt, text=True, capture_output=True, timeout=timeout,
                               cwd=cwd, check=False)
    if completed.returncode:
        detail = completed.stderr.strip()[-1000:] or f"exit status {completed.returncode}"
        raise RuntimeError("Codex role failed: " + detail)
    return completed.stdout


class CodexClient:
    """Generate one JSON object with gpt-5.6-sol under a read-only sandbox."""

    def __init__(self, project_root: Path, *, runner: Runner = _subprocess_runner,
                 executable: str = "codex", timeout: float | None = None) -> None:
        self.root = project_root.resolve()
        if not self.root.is_dir():
            raise ValueError("project root must be an existing directory")
        if not executable.strip():
            raise ValueError("Codex executable must be configured")
        valid_type = isinstance(timeout, (int, float)) and not isinstance(timeout, bool)
        if timeout is not None and (not valid_type or not math.isfinite(timeout) or timeout < 0):
            raise ValueError("Codex timeout must be zero, None, or a positive finite number")
        self.runner, self.executable = runner, executable
        self.timeout = None if timeout == 0 else timeout

    def generate(self, role: str, contract: str, payload: Mapping[str, object],
                 *, schema: Mapping[str, object] | None = None,
                 cwd: Path | None = None) -> Mapping[str, object]:
        workdir = (cwd or self.root).resolve()
        try:
            workdir.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Codex cwd must stay inside project root") from exc
        if not workdir.is_dir() or (cwd and cwd.is_symlink()):
            raise ValueError("Codex cwd must be a contained real directory")
        prompt = (f"Role: {role}\nReturn exactly one JSON object with no markdown.\n"
                  f"Contract: {contract}\nINPUT:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}")
        args = [self.executable, "exec", "--model", "gpt-5.6-sol", "-c",
                'model_reasoning_effort="medium"', "-c", 'approval_policy="never"',
                "--ephemeral", "--ignore-user-config", "--sandbox", "read-only",
                "--cd", str(workdir)]
        schema_path = self._schema_file(schema) if schema is not None else None
        if schema_path:
            args.extend(("--output-schema", str(schema_path)))
        args.append("-")
        try:
            raw = self.runner(args, prompt, self.timeout, workdir)
        finally:
            if schema_path:
                schema_path.unlink(missing_ok=True)
        try:
            value = json.loads(raw.strip())
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("Codex role must return valid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("Codex role JSON must be an object")
        return value

    def _schema_file(self, schema: Mapping[str, object]) -> Path:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix=".codex-schema-",
                                         suffix=".json", dir=self.root, delete=False) as output:
            json.dump(schema, output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            return Path(output.name)
