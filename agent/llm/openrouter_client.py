"""Pinned OpenRouter boundary for FROGENT structured roles."""

from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Mapping

Transport = Callable[
    [str, Mapping[str, str], Mapping[str, object], float | None],
    Mapping[str, object],
]


def _urlopen_transport(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, object],
    timeout: float | None,
) -> Mapping[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        headers=dict(headers),
        method="POST",
    )
    try:
        opener = (
            urllib.request.urlopen(request)
            if timeout is None
            else urllib.request.urlopen(request, timeout=timeout)
        )
        with opener as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[-1200:]
        raise RuntimeError(f"OpenRouter request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("OpenRouter request failed before a response was received") from exc
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("OpenRouter response was not valid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("OpenRouter response must be a JSON object")
    return value


class OpenRouterClient:
    """Generate one typed role object with an exact OpenRouter model."""

    def __init__(
        self,
        project_root: Path,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float | None = None,
        reasoning: Mapping[str, object] | None = None,
        max_tokens: int = 12000,
        provider_order: tuple[str, ...] = (),
        allow_provider_fallbacks: bool = False,
        max_attempts: int = 1,
        retry_base_seconds: float = 2.0,
        transport: Transport = _urlopen_transport,
    ) -> None:
        self.root = project_root.resolve()
        if not self.root.is_dir():
            raise ValueError("project root must be an existing directory")
        if not model.strip():
            raise ValueError("OpenRouter model must be configured")
        if not base_url.strip().startswith("https://"):
            raise ValueError("OpenRouter base URL must use HTTPS")
        valid_timeout = isinstance(timeout, (int, float)) and not isinstance(timeout, bool)
        if timeout is not None and (
            not valid_timeout or not math.isfinite(timeout) or timeout < 0
        ):
            raise ValueError("OpenRouter timeout must be zero, None, or a positive finite number")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("OpenRouter max_tokens must be a positive integer")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("OpenRouter max_attempts must be a positive integer")
        if (
            isinstance(retry_base_seconds, bool)
            or not isinstance(retry_base_seconds, (int, float))
            or not math.isfinite(retry_base_seconds)
            or retry_base_seconds < 0
        ):
            raise ValueError("OpenRouter retry_base_seconds must be finite and non-negative")
        self.model = model.strip()
        self.api_key = api_key
        self.base_url = base_url.strip().rstrip("/")
        self.timeout = None if timeout == 0 else timeout
        self.reasoning = dict(reasoning or {"effort": "low"})
        self.max_tokens = max_tokens
        self.provider_order = tuple(provider_order)
        self.allow_provider_fallbacks = bool(allow_provider_fallbacks)
        self.max_attempts = max_attempts
        self.retry_base_seconds = float(retry_base_seconds)
        self.transport = transport
        self.last_metadata: Mapping[str, object] = {}

    def generate(
        self,
        role: str,
        contract: str,
        payload: Mapping[str, object],
        *,
        schema: Mapping[str, object] | None = None,
        cwd: Path | None = None,
    ) -> Mapping[str, object]:
        workdir = (cwd or self.root).resolve()
        try:
            workdir.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("OpenRouter cwd must stay inside project root") from exc
        if not workdir.is_dir() or (cwd and cwd.is_symlink()):
            raise ValueError("OpenRouter cwd must be a contained real directory")
        key = (self.api_key if self.api_key is not None else os.getenv(
            "OPENROUTER_API_KEY", ""
        )).strip()
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY must be configured for OpenRouter Agent runs")
        response_schema = dict(schema or {
            "type": "object",
            "additionalProperties": True,
        })
        provider: dict[str, object] = {
            "allow_fallbacks": self.allow_provider_fallbacks,
            "require_parameters": True,
            "data_collection": "deny",
        }
        if self.provider_order:
            provider["order"] = list(self.provider_order)
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"Role: {role}\nReturn exactly one JSON object with no markdown.\n"
                        f"Contract: {contract}"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ],
            "temperature": 0,
            "seed": 20260805,
            "max_tokens": self.max_tokens,
            "reasoning": self.reasoning,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "frogent_structured_role",
                    "strict": True,
                    "schema": response_schema,
                },
            },
            "provider": provider,
        }
        request_headers = {
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/FROGENT",
            "X-Title": "FROGENT structured Agent role",
        }
        response = None
        value = None
        attempts = 0
        for attempt in range(1, self.max_attempts + 1):
            attempts = attempt
            try:
                response = self.transport(
                    self.base_url + "/chat/completions",
                    request_headers,
                    body,
                    self.timeout,
                )
                message = response["choices"][0]["message"]
                content = message["content"]
                value = json.loads(content)
                if not isinstance(value, dict):
                    raise ValueError("OpenRouter role JSON must be an object")
                break
            except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
                if attempt == self.max_attempts:
                    raise ValueError(
                        "OpenRouter role must return valid JSON object content"
                    ) from exc
                time.sleep(self.retry_base_seconds * (2 ** (attempt - 1)))
            except (RuntimeError, OSError) as exc:
                retryable = (
                    "HTTP 429" in str(exc)
                    or "HTTP 502" in str(exc)
                    or "HTTP 503" in str(exc)
                    or "HTTP 504" in str(exc)
                    or "before a response was received" in str(exc)
                    or isinstance(exc, OSError)
                )
                if not retryable or attempt == self.max_attempts:
                    raise
                time.sleep(self.retry_base_seconds * (2 ** (attempt - 1)))
        if response is None or value is None:
            raise RuntimeError("OpenRouter request produced no response")
        self.last_metadata = {
            "response_id": response.get("id"),
            "returned_model": response.get("model"),
            "provider": response.get("provider"),
            "usage": response.get("usage"),
            "finish_reason": response["choices"][0].get("finish_reason"),
            "request_attempts": attempts,
        }
        return value
