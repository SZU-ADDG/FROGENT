"""Stable contracts and capability metadata for the FROGENT plugin."""

from .catalog import CAPABILITIES, SERVER_NAMES, build_registry
from .config import AppConnector, McpServer, load_app_connectors, load_mcp_servers
from .contracts import ArtifactRef, Capability, ExecutionContext, StreamEvent, ToolResult
from .evidence import (
    EvidenceExcerpt,
    EvidenceLedger,
    EvidenceStrength,
    LiteratureRecord,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
    SearchPlan,
    SynthesisClaim,
)
from .harness import (
    CommandKind,
    HarnessCommand,
    HarnessPhase,
    HarnessPolicy,
    HarnessState,
    admit_evidence,
    advance,
    reconcile_evidence,
)
from .literature import (
    LiteratureBatch,
    LiteratureProvider,
    LiteratureQuery,
    search_literature,
)
from .registry import CapabilityRegistry
from .v4_adapter import V4ChatRequest, v4_messages_to_events

__all__ = [
    "AppConnector",
    "ArtifactRef",
    "CAPABILITIES",
    "Capability",
    "CapabilityRegistry",
    "ExecutionContext",
    "EvidenceExcerpt",
    "EvidenceLedger",
    "EvidenceStrength",
    "CommandKind",
    "HarnessCommand",
    "HarnessPhase",
    "HarnessPolicy",
    "HarnessState",
    "LiteratureRecord",
    "LiteratureBatch",
    "LiteratureProvider",
    "LiteratureQuery",
    "McpServer",
    "SERVER_NAMES",
    "ScreeningDecision",
    "ScreeningOutcome",
    "ScreeningStage",
    "SearchPlan",
    "StreamEvent",
    "SynthesisClaim",
    "ToolResult",
    "V4ChatRequest",
    "admit_evidence",
    "advance",
    "reconcile_evidence",
    "build_registry",
    "load_app_connectors",
    "load_mcp_servers",
    "search_literature",
    "v4_messages_to_events",
]
