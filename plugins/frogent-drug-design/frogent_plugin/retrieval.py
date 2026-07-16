"""Composition boundary for policy-controlled literature retrieval."""

from dataclasses import dataclass
from typing import Mapping

from .contracts import ExecutionContext, StreamEvent
from .evidence import EvidenceLedger, LiteratureRecord, SearchPlan
from .harness import (
    CommandKind,
    HarnessCommand,
    HarnessPhase,
    HarnessPolicy,
    HarnessState,
    advance,
)
from .literature import LiteratureProvider, search_literature


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class RetrievalCall:
    capability_id: str
    source: str
    query: str
    limit: int = 20

    def __post_init__(self) -> None:
        for value, name in (
            (self.capability_id, "capability id"),
            (self.source, "source"),
            (self.query, "query"),
        ):
            _require_text(value, name)
        if self.limit <= 0:
            raise ValueError("retrieval limit must be positive")


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    call_index: int
    capability_id: str
    source: str
    query: str
    record_id: str


@dataclass(frozen=True, slots=True)
class RetrievalRunResult:
    state: HarnessState
    ledger: EvidenceLedger
    events: tuple[StreamEvent, ...]
    hits: tuple[RetrievalHit, ...]
    completed_calls: int

    @property
    def ok(self) -> bool:
        return self.state.phase is not HarnessPhase.FAILED


def run_retrieval(
    plan: SearchPlan,
    calls: tuple[RetrievalCall, ...],
    providers: Mapping[str, LiteratureProvider],
    context: ExecutionContext,
    state: HarnessState,
    policy: HarnessPolicy,
) -> RetrievalRunResult:
    """Run explicitly paired retrieval calls through the harness policy gate."""

    ledger = EvidenceLedger()
    events: list[StreamEvent] = []
    hits: list[RetrievalHit] = []
    canonical: dict[str, LiteratureRecord] = {}
    current = state
    completed = 0
    if not calls:
        exc = ValueError("retrieval plan must contain at least one call")
        current = _fail(current, policy, exc)
        events.append(
            StreamEvent(
                "error",
                {"error_type": type(exc).__name__, "message": str(exc)},
            )
        )
    for index, call in enumerate(calls):
        try:
            _validate_call(plan, call)
            provider = _provider_for(call, providers)
            current = _authorize(current, call, policy)
            events.append(_event("tool.started", call, index))
            batch = search_literature(
                provider,
                plan,
                call.source,
                call.query,
                context,
                limit=call.limit,
            )
            for record in batch.records:
                hits.append(
                    RetrievalHit(
                        index,
                        call.capability_id,
                        call.source,
                        call.query,
                        record.id,
                    )
                )
                _merge_record(record, canonical, ledger)
            completed += 1
            events.append(
                _event(
                    "tool.completed",
                    call,
                    index,
                    record_count=len(batch.records),
                    provider_version=batch.provider_version,
                )
            )
        except Exception as exc:
            current = _fail(current, policy, exc)
            events.append(
                _event(
                    "error",
                    call,
                    index,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            break
    events.append(
        StreamEvent(
            "done",
            {
                "ok": current.phase is not HarnessPhase.FAILED,
                "completed_calls": completed,
                "raw_hit_count": len(hits),
                "unique_record_count": len(ledger.records()),
                "memory_evidence_count": len(current.memory_evidence_ids),
            },
        )
    )
    return RetrievalRunResult(current, ledger, tuple(events), tuple(hits), completed)


def _merge_record(record: LiteratureRecord, canonical: dict[str, LiteratureRecord], ledger: EvidenceLedger) -> None:
    existing = canonical.get(record.id)
    if existing is None:
        canonical[record.id] = record
        ledger.add_record(record)
    elif existing != record:
        raise ValueError(f"conflicting literature record: {record.id}")


def _validate_call(plan: SearchPlan, call: RetrievalCall) -> None:
    if call.source not in plan.sources:
        raise ValueError(f"source is not present in search plan: {call.source}")
    if call.query not in plan.queries:
        raise ValueError("query is not present in search plan")


def _provider_for(call: RetrievalCall, providers: Mapping[str, LiteratureProvider]) -> LiteratureProvider:
    try:
        return providers[call.capability_id]
    except KeyError as exc:
        raise KeyError(f"unknown retrieval capability: {call.capability_id}") from exc


def _authorize(
    state: HarnessState,
    call: RetrievalCall,
    policy: HarnessPolicy,
) -> HarnessState:
    command = HarnessCommand(
        CommandKind.CALL_CAPABILITY,
        HarnessPhase.RETRIEVAL,
        "Execute a planned literature retrieval pair",
        call.capability_id,
    )
    return advance(state, command, policy)


def _fail(state: HarnessState, policy: HarnessPolicy, exc: Exception) -> HarnessState:
    if state.terminal:
        return state
    try:
        return advance(
            state,
            HarnessCommand(CommandKind.FAIL, HarnessPhase.FAILED, str(exc)),
            policy,
        )
    except (RuntimeError, ValueError):
        return HarnessState(
            state.run_id,
            state.as_of,
            HarnessPhase.FAILED,
            state.step_count,
            state.tool_call_count,
            state.memory_evidence_ids,
            state.last_target,
            str(exc),
        )


def _event(kind: str, call: RetrievalCall, index: int, **details: object) -> StreamEvent:
    payload = {
        "call_index": index,
        "capability_id": call.capability_id,
        "source": call.source,
        "query": call.query,
        **details,
    }
    return StreamEvent(kind, payload)  # type: ignore[arg-type]
