"""OpenAI-compatible DeepSeek boundary for FROGENT structured roles."""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Mapping

Transport = Callable[[str, Mapping[str, str], Mapping[str, object], float | None],
                     Mapping[str, object]]


def _urlopen_transport(url: str, headers: Mapping[str, str], payload: Mapping[str, object],
                       timeout: float | None) -> Mapping[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        headers=dict(headers),
        method="POST",
    )
    try:
        response = (urllib.request.urlopen(request) if timeout is None else
                    urllib.request.urlopen(request, timeout=timeout))
        with response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"DeepSeek request failed with HTTP status {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("DeepSeek request failed before a response was received") from exc
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("DeepSeek response was not valid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("DeepSeek response must be a JSON object")
    return value


class DeepSeekClient:
    """Generate one typed JSON object with the pinned FROGENT Agent model."""

    def __init__(self, project_root: Path, *, model: str = "deepseek-v4-flash",
                 base_url: str = "https://api.deepseek.com", api_key: str | None = None,
                 timeout: float | None = None, transport: Transport = _urlopen_transport) -> None:
        self.root = project_root.resolve()
        if not self.root.is_dir():
            raise ValueError("project root must be an existing directory")
        if not model.strip():
            raise ValueError("DeepSeek model must be configured")
        if not base_url.strip().startswith("https://"):
            raise ValueError("DeepSeek base URL must use HTTPS")
        valid_type = isinstance(timeout, (int, float)) and not isinstance(timeout, bool)
        if timeout is not None and (not valid_type or not math.isfinite(timeout) or timeout < 0):
            raise ValueError("DeepSeek timeout must be zero, None, or a positive finite number")
        self.model = model.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.api_key = api_key
        self.timeout = None if timeout == 0 else timeout
        self.transport = transport

    def generate(self, role: str, contract: str, payload: Mapping[str, object],
                 *, schema: Mapping[str, object] | None = None,
                 cwd: Path | None = None) -> Mapping[str, object]:
        workdir = (cwd or self.root).resolve()
        try:
            workdir.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("DeepSeek cwd must stay inside project root") from exc
        if not workdir.is_dir() or (cwd and cwd.is_symlink()):
            raise ValueError("DeepSeek cwd must be a contained real directory")
        key = (self.api_key if self.api_key is not None else
               os.getenv("DEEPSEEK_API_KEY", "")).strip()
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY must be configured for DeepSeek Agent runs")
        schema_text = (json.dumps(schema, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")) if schema is not None else
                       '{"type":"object"}')
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": (
                    f"Role: {role}\nReturn exactly one JSON object with no markdown.\n"
                    f"Contract: {contract}\nJSON Schema: {schema_text}")},
                {"role": "user", "content": json.dumps(
                    payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        response = self.transport(
            self.base_url + "/chat/completions",
            {"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            body,
            self.timeout,
        )
        try:
            content = response["choices"][0]["message"]["content"]
            value = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("DeepSeek role must return valid JSON object content") from exc
        if not isinstance(value, dict):
            raise ValueError("DeepSeek role JSON must be an object")
        return value
