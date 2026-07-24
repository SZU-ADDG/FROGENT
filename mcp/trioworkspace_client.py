"""SSH client for the private TrioWorkspace loopback control plane."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


SAFE_HOST = re.compile(r"^[A-Za-z0-9_.@-]+$")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,63}$")
Runner = Callable[..., subprocess.CompletedProcess[bytes]]


@dataclass(frozen=True, slots=True)
class TrioConfig:
    runtime_root: Path
    project_root: Path
    ssh_host: str
    ssh_executable: str
    remote_python: str
    user_id: str
    user_email: str
    max_artifact_bytes: int
    timeout: float | None

    @classmethod
    def from_env(cls, project_root: Path) -> "TrioConfig":
        root = project_root.resolve(strict=True)
        project = Path(os.environ.get("FROGENT_PROJECT_ROOT", str(root))).resolve(strict=True)
        host = os.environ.get("FROGENT_TRIO_SSH_HOST", "doomx_3nd").strip()
        executable = os.environ.get("FROGENT_TRIO_SSH_EXECUTABLE", "ssh").strip()
        remote_python = os.environ.get(
            "FROGENT_TRIO_REMOTE_PYTHON",
            "/work/doomx/TrioWorkspace/runtime/envs/control-plane/current/bin/python",
        ).strip()
        timeout = _optional_timeout(os.environ.get("FROGENT_TRIO_SSH_TIMEOUT", ""))
        maximum = _positive_int(
            os.environ.get("FROGENT_TRIO_MAX_ARTIFACT_BYTES", "20971520"),
            "FROGENT_TRIO_MAX_ARTIFACT_BYTES",
        )
        config = cls(
            root, project, host, executable, remote_python,
            os.environ.get("FROGENT_TRIO_USER_ID", "frogent-mcp").strip(),
            os.environ.get("FROGENT_TRIO_USER_EMAIL", "frogent-mcp@localhost.invalid").strip(),
            maximum, timeout,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.project_root != self.runtime_root and self.project_root not in self.runtime_root.parents:
            raise ValueError("runtime root must be contained in the FROGENT project")
        if not SAFE_HOST.fullmatch(self.ssh_host):
            raise ValueError("FROGENT_TRIO_SSH_HOST is invalid")
        for name, value in {
            "FROGENT_TRIO_SSH_EXECUTABLE": self.ssh_executable,
            "FROGENT_TRIO_REMOTE_PYTHON": self.remote_python,
            "FROGENT_TRIO_USER_ID": self.user_id,
            "FROGENT_TRIO_USER_EMAIL": self.user_email,
        }.items():
            if not value or any(ord(character) < 32 for character in value):
                raise ValueError(f"{name} is invalid")
        if not self.remote_python.startswith("/work/doomx/TrioWorkspace/"):
            raise ValueError("remote Python must be contained in TrioWorkspace")
        if not 0 < self.max_artifact_bytes <= 45 * 1024 * 1024:
            raise ValueError("artifact limit must be in 1..45 MiB")


def _positive_int(value: str, name: str) -> int:
    if not value.isdigit() or int(value) <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _optional_timeout(value: str) -> float | None:
    if not value.strip() or value.strip() == "0":
        return None
    try:
        timeout = float(value)
    except ValueError as error:
        raise ValueError("FROGENT_TRIO_SSH_TIMEOUT must be a positive finite number") from error
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("FROGENT_TRIO_SSH_TIMEOUT must be a positive finite number")
    return timeout


class TrioRemoteError(RuntimeError):
    """Safe remote or protocol failure."""


class TrioClient:
    def __init__(self, config: TrioConfig, relay_source: str, runner: Runner = subprocess.run):
        if not relay_source.strip():
            raise ValueError("relay source must be non-empty")
        self.config = config
        self.relay_source = relay_source
        self.runner = runner

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes = b"",
        content_type: str = "application/octet-stream",
        max_response_bytes: int = 2 * 1024 * 1024,
    ) -> tuple[dict[str, str | int], bytes]:
        request = {
            "method": method,
            "path": path,
            "body_base64": base64.b64encode(body).decode(),
            "content_type": content_type,
            "user_id": self.config.user_id,
            "user_email": self.config.user_email,
            "max_response_bytes": max_response_bytes,
        }
        completed = self.runner(
            self._command(),
            input=json.dumps(request, separators=(",", ":")).encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.config.timeout,
            check=False,
        )
        if completed.returncode != 0:
            raise TrioRemoteError("TrioWorkspace SSH relay failed safely")
        try:
            response = json.loads(completed.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TrioRemoteError("TrioWorkspace SSH relay returned malformed output") from error
        if not isinstance(response, dict) or "relay_error" in response:
            message = response.get("relay_error") if isinstance(response, dict) else None
            raise TrioRemoteError(str(message or "TrioWorkspace SSH relay failed safely"))
        try:
            payload = base64.b64decode(response["body_base64"], validate=True)
            status = int(response["status"])
        except (KeyError, TypeError, ValueError) as error:
            raise TrioRemoteError("TrioWorkspace SSH relay response is incomplete") from error
        if len(payload) > max_response_bytes:
            raise TrioRemoteError("TrioWorkspace response exceeded the configured limit")
        headers = {
            "status": status,
            "content_type": str(response.get("content_type", "")),
            "content_disposition": str(response.get("content_disposition", "")),
            "etag": str(response.get("etag", "")),
        }
        if not 200 <= status < 300:
            raise TrioRemoteError(_public_error(payload, status))
        return headers, payload

    def json(self, method: str, path: str, *, body: bytes = b"", content_type: str = "application/octet-stream") -> Any:
        _, payload = self.request(method, path, body=body, content_type=content_type)
        try:
            result = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TrioRemoteError("TrioWorkspace returned malformed JSON") from error
        return result

    def download(self, task_id: str, artifact: dict[str, Any]) -> dict[str, Any]:
        artifact_id = _safe_id(artifact.get("id"), "artifact_id")
        task = _safe_id(task_id, "task_id")
        byte_size = artifact.get("byteSize")
        sha256 = artifact.get("sha256")
        if isinstance(byte_size, bool) or not isinstance(byte_size, int) or not 0 <= byte_size <= self.config.max_artifact_bytes:
            raise TrioRemoteError("artifact size is invalid or exceeds the configured limit")
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise TrioRemoteError("artifact checksum is invalid")
        _, payload = self.request(
            "GET", f"/v1/tasks/{task}/artifacts/{artifact_id}",
            max_response_bytes=self.config.max_artifact_bytes,
        )
        if len(payload) != byte_size or hashlib.sha256(payload).hexdigest() != sha256:
            raise TrioRemoteError("downloaded artifact failed size or checksum verification")
        filename = re.sub(r"[^A-Za-z0-9._-]", "_", str(artifact.get("filename", "artifact")))[:160]
        target = self._artifact_path(task, artifact_id, filename)
        _exclusive_or_equal(target, payload)
        return {
            "task_id": task, "artifact_id": artifact_id, "filename": filename,
            "byte_size": byte_size, "sha256": sha256, "local_path": str(target),
            "content_type": artifact.get("contentType"),
        }

    def _command(self) -> list[str]:
        source = base64.b64encode(self.relay_source.encode()).decode()
        loader = f'import base64;exec(compile(base64.b64decode("{source}"),"<frogent-trio-relay>","exec"))'
        remote = " ".join([
            "PYTHONDONTWRITEBYTECODE=1",
            shlex.quote(self.config.remote_python),
            "-c",
            shlex.quote(loader),
        ])
        return [
            self.config.ssh_executable, "-o", "BatchMode=yes", "-o", "ClearAllForwardings=yes",
            "-o", "RequestTTY=no", self.config.ssh_host, remote,
        ]

    def _artifact_path(self, task_id: str, artifact_id: str, filename: str) -> Path:
        root = self.config.runtime_root / "runtime" / "trio-workspace" / "artifacts"
        for parent in (self.config.runtime_root / "runtime", root.parent):
            if parent.exists() and parent.is_symlink():
                raise TrioRemoteError("artifact root contains a symbolic link")
        directory = root / task_id / artifact_id
        directory.mkdir(parents=True, exist_ok=True)
        if any(parent.is_symlink() for parent in (root, root / task_id, directory)):
            raise TrioRemoteError("artifact path contains a symbolic link")
        target = (directory / filename).resolve(strict=False)
        if self.config.runtime_root not in target.parents:
            raise TrioRemoteError("artifact path escaped the runtime root")
        return target


def _safe_id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise TrioRemoteError(f"{name} is invalid")
    return value


def _public_error(payload: bytes, status: int) -> str:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return f"TrioWorkspace request failed with HTTP {status}"
    message = value.get("message") if isinstance(value, dict) else None
    return str(message) if isinstance(message, str) and message else f"TrioWorkspace request failed with HTTP {status}"


def _exclusive_or_equal(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
            raise TrioRemoteError("artifact destination already exists with different content")
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        raise
