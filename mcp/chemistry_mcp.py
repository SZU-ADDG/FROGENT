#!/usr/bin/env python3
"""Project-contained stdio MCP server for chemistry and target evidence."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.chemistry_schemas import TOOLS, TOOL_NAMES
from mcp.chemistry_tools import ChemistryTools


SERVER_VERSION = "0.3.0"


class McpServer:
    def __init__(self, tools: ChemistryTools | None = None):
        self.tools = tools or ChemistryTools()

    def handle(self, request: Any) -> dict[str, Any] | None:
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            return _error(
                request.get("id") if isinstance(request, dict) else None,
                -32600,
                "Invalid Request",
            )
        request_id = request.get("id")
        method = request.get("method")
        if not isinstance(method, str):
            return _error(request_id, -32600, "Invalid Request")
        if method.startswith("notifications/"):
            return None
        try:
            result = self._dispatch(method, request.get("params", {}))
        except ValueError as error:
            if method == "tools/call":
                result = {
                    "content": [{"type": "text", "text": str(error)}],
                    "isError": True,
                }
            else:
                return _error(request_id, -32602, str(error))
        except Exception as error:
            if method == "tools/call":
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"chemistry tool failed safely: {type(error).__name__}: {error}",
                        }
                    ],
                    "isError": True,
                }
            else:
                return _error(request_id, -32603, "Internal error")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _dispatch(self, method: str, params: Any) -> Any:
        if method == "initialize":
            return {
                "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "frogent-chemistry",
                    "version": SERVER_VERSION,
                },
                "instructions": (
                    "Deterministic local descriptors plus curated ChEMBL and RCSB PDB "
                    "ligand-similarity evidence. Similarity is a retrieval signal, not affinity."
                ),
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            if params not in ({}, None):
                raise ValueError("tools/list accepts no parameters")
            return {"tools": list(TOOLS)}
        if method == "tools/call":
            if not isinstance(params, dict) or set(params) - {"name", "arguments"}:
                raise ValueError("tools/call params are invalid")
            name = params.get("name")
            if not isinstance(name, str) or name not in TOOL_NAMES:
                raise ValueError("unknown chemistry tool")
            data = self.tools.call(name, params.get("arguments", {}))
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            data, ensure_ascii=False, separators=(",", ":")
                        ),
                    }
                ],
                "structuredContent": data,
                "isError": False,
            }
        raise ValueError(f"unsupported MCP method: {method}")


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def main() -> int:
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    server = McpServer()
    for line in sys.stdin.buffer:
        try:
            request = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            response = _error(None, -32700, "Parse error")
        else:
            response = server.handle(request)
        if response is not None:
            sys.stdout.write(
                json.dumps(response, separators=(",", ":"), ensure_ascii=False) + "\n"
            )
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
