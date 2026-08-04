#!/usr/bin/env python3
"""Run a credential-safe tool-call canary against the pinned DeepSeek model."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
MODEL = "deepseek-v4-flash"
BASE_URL = "https://api.deepseek.com"
Transport = Callable[[Mapping[str, object]], Mapping[str, object]]


def _transport(payload: Mapping[str, object]) -> Mapping[str, object]:
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is required")
    request = urllib.request.Request(
        BASE_URL + "/chat/completions",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            value = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"DeepSeek canary failed with HTTP status {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("DeepSeek canary failed before receiving a response") from exc
    if not isinstance(value, dict):
        raise RuntimeError("DeepSeek canary response must be a JSON object")
    return value


def run_canary(transport: Transport = _transport) -> dict[str, object]:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": (
            "Call frogent_canary_echo exactly once with value set to ok.")}],
        "tools": [{"type": "function", "function": {
            "name": "frogent_canary_echo",
            "description": "Return a fixed harmless canary value.",
            "parameters": {"type": "object", "properties": {
                "value": {"type": "string", "enum": ["ok"]}},
                "required": ["value"], "additionalProperties": False},
        }}],
        "thinking": {"type": "disabled"},
        "tool_choice": {"type": "function", "function": {"name": "frogent_canary_echo"}},
        "stream": False,
    }
    response = transport(payload)
    try:
        choice = response["choices"][0]
        calls = choice["message"]["tool_calls"]
        call = calls[0]
        name = call["function"]["name"]
        arguments = json.loads(call["function"]["arguments"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("DeepSeek canary did not return a valid tool call") from exc
    if len(calls) != 1 or name != "frogent_canary_echo" or arguments != {"value": "ok"}:
        raise RuntimeError("DeepSeek canary returned an unexpected tool call")
    usage = response.get("usage", {})
    safe_usage = {key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                  if isinstance(usage, dict) and isinstance(usage.get(key), int)}
    return {
        "status": "pass",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "requested_model": MODEL,
        "returned_model": response.get("model", "not_reported"),
        "finish_reason": choice.get("finish_reason", "not_reported"),
        "tool_call": {"name": name, "arguments": arguments},
        "usage": safe_usage,
        "credential_persisted": False,
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    target = path.resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("output must stay inside the FROGENT project") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("output path must not use symlinks")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                     prefix=".deepseek-canary-", delete=False) as output:
        json.dump(report, output, ensure_ascii=False, sort_keys=True, indent=2)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_canary()
    _write_report(args.output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
