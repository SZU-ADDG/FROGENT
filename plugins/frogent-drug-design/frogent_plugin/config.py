"""Load connector manifests without importing scientific runtimes."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _load_section(path: Path, section_name: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")

    section = payload.get(section_name)
    if not isinstance(section, dict):
        raise ValueError(f"{path} field {section_name!r} must be an object")
    return section


@dataclass(frozen=True, slots=True)
class McpServer:
    name: str
    url: str
    title: str

    @classmethod
    def from_mapping(cls, name: str, entry: Mapping[str, Any]) -> "McpServer":
        transport = entry.get("type", "http")
        if transport != "http":
            raise ValueError(f"MCP server {name!r} must use HTTP transport")

        url = _require_text(entry.get("url"), f"MCP server {name!r} url")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"MCP server {name!r} has an invalid URL")

        title = _require_text(
            entry.get("title", name.replace("-", " ").title()),
            f"MCP server {name!r} title",
        )
        return cls(name=_require_text(name, "MCP server name"), url=url, title=title)


@dataclass(frozen=True, slots=True)
class AppConnector:
    alias: str
    id: str

    @classmethod
    def from_mapping(cls, alias: str, entry: Mapping[str, Any]) -> "AppConnector":
        return cls(
            alias=_require_text(alias, "app alias"),
            id=_require_text(entry.get("id"), f"app {alias!r} id"),
        )


def load_mcp_servers(path: Path) -> tuple[McpServer, ...]:
    section = _load_section(path, "mcpServers")
    servers = []
    for name, entry in section.items():
        if not isinstance(entry, dict):
            raise ValueError(f"MCP server {name!r} must be an object")
        servers.append(McpServer.from_mapping(name, entry))
    return tuple(sorted(servers, key=lambda server: server.name))


def load_app_connectors(path: Path) -> tuple[AppConnector, ...]:
    section = _load_section(path, "apps")
    connectors = []
    for alias, entry in section.items():
        if not isinstance(entry, dict):
            raise ValueError(f"app {alias!r} must be an object")
        connectors.append(AppConnector.from_mapping(alias, entry))
    return tuple(sorted(connectors, key=lambda connector: connector.alias))
