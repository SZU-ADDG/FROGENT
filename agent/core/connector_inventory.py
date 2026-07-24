"""Current MCP inventory loader supporting HTTP and stdio providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class McpConnector:
    name: str
    title: str
    transport: str
    url: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()
    cwd: str | None = None

    @classmethod
    def from_mapping(cls, name: str, entry: Mapping[str, Any]) -> "McpConnector":
        server_name = _text(name, "MCP server name")
        title = _text(entry.get("title", name.replace("-", " ").title()), f"{name} title")
        if "command" in entry:
            if "url" in entry or entry.get("type") not in {None, "stdio"}:
                raise ValueError(f"MCP server {name!r} mixes transports")
            command = _text(entry.get("command"), f"{name} command")
            raw_args = entry.get("args", [])
            if not isinstance(raw_args, list) or any(
                not isinstance(argument, str) for argument in raw_args
            ):
                raise ValueError(f"MCP server {name!r} args must be a string array")
            cwd = _text(entry.get("cwd", "."), f"{name} cwd")
            return cls(server_name, title, "stdio", command=command, args=tuple(raw_args), cwd=cwd)
        if entry.get("type", "http") != "http":
            raise ValueError(f"MCP server {name!r} has an unsupported transport")
        url = _text(entry.get("url"), f"{name} url")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"MCP server {name!r} has an invalid URL")
        return cls(server_name, title, "http", url=url)


def load_connector_inventory(path: Path) -> tuple[McpConnector, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load MCP inventory: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("mcpServers"), dict):
        raise ValueError("MCP inventory must contain an mcpServers object")
    connectors = []
    for name, entry in payload["mcpServers"].items():
        if not isinstance(entry, dict):
            raise ValueError(f"MCP server {name!r} must be an object")
        connectors.append(McpConnector.from_mapping(name, entry))
    return tuple(sorted(connectors, key=lambda connector: connector.name))
