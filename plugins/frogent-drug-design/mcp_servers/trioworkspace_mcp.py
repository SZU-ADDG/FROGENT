#!/usr/bin/env python3
"""Project-contained stdio MCP server for the private TrioWorkspace runtime."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from trioworkspace_client import TrioClient, TrioConfig, TrioRemoteError
from trioworkspace_schemas import TOOLS, TOOL_NAMES
from trioworkspace_tools import TrioTools, text_result


SERVER_VERSION = "0.1.0"


class McpServer:
    def __init__(self, tools: TrioTools):
        self.tools = tools

    def handle(self, request: Any) -> dict[str, Any] | None:
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            return _error(request.get("id") if isinstance(request, dict) else None, -32600, "Invalid Request")
        request_id = request.get("id")
        method = request.get("method")
        if not isinstance(method, str):
            return _error(request_id, -32600, "Invalid Request")
        if method.startswith("notifications/"):
            return None
        try:
            result = self._dispatch(method, request.get("params", {}))
        except (ValueError, TrioRemoteError) as error:
            if method == "tools/call":
                result = {
                    "content": [{"type": "text", "text": str(error)}],
                    "isError": True,
                }
            else:
                return _error(request_id, -32602, str(error))
        except Exception:
            if method == "tools/call":
                result = {
                    "content": [{"type": "text", "text": "TrioWorkspace tool failed safely"}],
                    "isError": True,
                }
            else:
                return _error(request_id, -32603, "Internal error")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _dispatch(self, method: str, params: Any) -> Any:
        if method == "initialize":
            if not isinstance(params, dict):
                raise ValueError("initialize params must be an object")
            requested = params.get("protocolVersion", "2025-06-18")
            if not isinstance(requested, str) or not requested:
                raise ValueError("protocolVersion must be a non-empty string")
            return {
                "protocolVersion": requested,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "frogent-trioworkspace", "version": SERVER_VERSION},
                "instructions": (
                    "Five private scientific engines are exposed as asynchronous tasks. "
                    "Submit a typed engine task, poll its owned task ID, then download verified artifacts."
                ),
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            if params not in ({}, None):
                if not isinstance(params, dict) or params:
                    raise ValueError("tools/list accepts no parameters")
            return {"tools": list(TOOLS)}
        if method == "tools/call":
            if not isinstance(params, dict) or set(params) - {"name", "arguments"}:
                raise ValueError("tools/call params are invalid")
            name = params.get("name")
            arguments = params.get("arguments", {})
            if not isinstance(name, str) or name not in TOOL_NAMES:
                raise ValueError("unknown TrioWorkspace tool")
            return text_result(self.tools.call(name, arguments))
        raise ValueError(f"unsupported MCP method: {method}")


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def build_server(plugin_root: Path | None = None) -> McpServer:
    root = (plugin_root or Path.cwd()).resolve(strict=True)
    config = TrioConfig.from_env(root)
    relay_path = Path(__file__).with_name("trioworkspace_remote_relay.py")
    relay_source = relay_path.read_text(encoding="utf-8")
    return McpServer(TrioTools(TrioClient(config, relay_source), config.project_root))


def main() -> int:
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    server = build_server()
    for line in sys.stdin.buffer:
        try:
            request = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            response = _error(None, -32700, "Parse error")
        else:
            response = server.handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":"), ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
