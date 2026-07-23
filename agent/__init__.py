"""Stable contracts and capability metadata for the FROGENT Agent."""

from agent.core.catalog import CAPABILITIES, SERVER_NAMES, build_registry
from agent.core.chat_adapter import ChatRequest, chat_messages_to_events
from agent.core.config import AppConnector, McpServer, load_app_connectors, load_mcp_servers
from agent.core.contracts import ArtifactRef, Capability, ExecutionContext, StreamEvent, ToolResult
from agent.core.evidence import (
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
from agent.evaluation.eval_manifest import EvalBundle, content_digest, load_bundle
from agent.evaluation.eval_runner import evaluate_bundle, verify_result
from agent.core.harness import (
    CommandKind,
    HarnessCommand,
    HarnessPhase,
    HarnessPolicy,
    HarnessState,
    admit_evidence,
    advance,
    reconcile_evidence,
)
from agent.core.literature import (
    LiteratureBatch,
    LiteratureProvider,
    LiteratureQuery,
    search_literature,
)
from agent.core.registry import CapabilityRegistry
from agent.core.retrieval import RetrievalCall, RetrievalHit, RetrievalRunResult, run_retrieval

__all__ = [
    "AppConnector",
    "ArtifactRef",
    "CAPABILITIES",
    "Capability",
    "CapabilityRegistry",
    "ChatRequest",
    "ExecutionContext",
    "EvidenceExcerpt",
    "EvidenceLedger",
    "EvidenceStrength",
    "EvalBundle",
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
    "RetrievalCall",
    "RetrievalHit",
    "RetrievalRunResult",
    "SERVER_NAMES",
    "ScreeningDecision",
    "ScreeningOutcome",
    "ScreeningStage",
    "SearchPlan",
    "StreamEvent",
    "SynthesisClaim",
    "ToolResult",
    "admit_evidence",
    "advance",
    "content_digest",
    "evaluate_bundle",
    "reconcile_evidence",
    "run_retrieval",
    "build_registry",
    "chat_messages_to_events",
    "load_app_connectors",
    "load_mcp_servers",
    "load_bundle",
    "search_literature",
    "verify_result",
]
