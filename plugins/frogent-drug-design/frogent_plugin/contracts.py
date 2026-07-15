"""Small immutable contracts shared by apps, skills, and MCP adapters."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

EventKind = Literal[
    "message.delta",
    "agent.changed",
    "tool.started",
    "tool.completed",
    "artifact.created",
    "error",
    "done",
]

EVENT_KINDS = frozenset(
    {
        "message.delta",
        "agent.changed",
        "tool.started",
        "tool.completed",
        "artifact.created",
        "error",
        "done",
    }
)


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class Capability:
    """Stable capability name mapped to one MCP tool."""

    id: str
    server: str
    tool: str
    summary: str

    def __post_init__(self) -> None:
        for field_name in ("id", "server", "tool", "summary"):
            _require_text(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Identity and workspace carried through one user job."""

    user_id: str
    conversation_id: str
    job_id: str
    workspace: Path

    def __post_init__(self) -> None:
        for field_name in ("user_id", "conversation_id", "job_id"):
            _require_text(getattr(self, field_name), field_name)
        if not self.workspace.is_absolute():
            raise ValueError("workspace must be an absolute path")


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Logical reference to a file managed by an artifact store."""

    id: str
    name: str
    media_type: str
    uri: str

    def __post_init__(self) -> None:
        for field_name in ("id", "name", "media_type", "uri"):
            _require_text(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Normalized result returned by every capability provider."""

    ok: bool
    data: Mapping[str, Any] = field(default_factory=dict)
    artifacts: tuple[ArtifactRef, ...] = ()
    warnings: tuple[str, ...] = ()
    error: str | None = None

    def __post_init__(self) -> None:
        if self.ok and self.error:
            raise ValueError("successful results cannot contain an error")
        if not self.ok and not self.error:
            raise ValueError("failed results must contain an error")


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """Transport-neutral event converted to SSE only at the web boundary."""

    kind: EventKind
    payload: Mapping[str, Any] = field(default_factory=dict)
    agent: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unsupported event kind: {self.kind}")

    def as_dict(self) -> dict[str, Any]:
        event = {"kind": self.kind, "payload": dict(self.payload)}
        if self.agent:
            event["agent"] = self.agent
        return event
