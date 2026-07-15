"""Finite state and policy boundary for the FROGENT agent harness."""

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from .evidence import EvidenceLedger


class HarnessPhase(StrEnum):
    INTAKE = "intake"
    PLANNING = "planning"
    RETRIEVAL = "retrieval"
    SCREENING = "screening"
    EXECUTION = "execution"
    EVALUATION = "evaluation"
    SYNTHESIS = "synthesis"
    WAITING = "waiting"
    COMPLETE = "complete"
    FAILED = "failed"


class CommandKind(StrEnum):
    ACTIVATE_SKILL = "activate_skill"
    DELEGATE_AGENT = "delegate_agent"
    CALL_CAPABILITY = "call_capability"
    REQUEST_INPUT = "request_input"
    COMPLETE = "complete"
    FAIL = "fail"


TERMINAL_PHASES = frozenset({HarnessPhase.COMPLETE, HarnessPhase.FAILED})
TARGETED_COMMANDS = frozenset(
    {
        CommandKind.ACTIVATE_SKILL,
        CommandKind.DELEGATE_AGENT,
        CommandKind.CALL_CAPABILITY,
    }
)
FIXED_PHASES = {
    CommandKind.REQUEST_INPUT: HarnessPhase.WAITING,
    CommandKind.COMPLETE: HarnessPhase.COMPLETE,
    CommandKind.FAIL: HarnessPhase.FAILED,
}
ALLOWED_TRANSITIONS = {
    HarnessPhase.INTAKE: {HarnessPhase.PLANNING, HarnessPhase.WAITING, HarnessPhase.FAILED},
    HarnessPhase.PLANNING: {
        HarnessPhase.PLANNING,
        HarnessPhase.RETRIEVAL,
        HarnessPhase.EXECUTION,
        HarnessPhase.WAITING,
        HarnessPhase.FAILED,
    },
    HarnessPhase.RETRIEVAL: {
        HarnessPhase.RETRIEVAL,
        HarnessPhase.SCREENING,
        HarnessPhase.EVALUATION,
        HarnessPhase.WAITING,
        HarnessPhase.FAILED,
    },
    HarnessPhase.SCREENING: {
        HarnessPhase.SCREENING,
        HarnessPhase.RETRIEVAL,
        HarnessPhase.EXECUTION,
        HarnessPhase.EVALUATION,
        HarnessPhase.SYNTHESIS,
        HarnessPhase.WAITING,
        HarnessPhase.FAILED,
    },
    HarnessPhase.EXECUTION: {
        HarnessPhase.EXECUTION,
        HarnessPhase.EVALUATION,
        HarnessPhase.WAITING,
        HarnessPhase.FAILED,
    },
    HarnessPhase.EVALUATION: {
        HarnessPhase.PLANNING,
        HarnessPhase.RETRIEVAL,
        HarnessPhase.SCREENING,
        HarnessPhase.SYNTHESIS,
        HarnessPhase.WAITING,
        HarnessPhase.COMPLETE,
        HarnessPhase.FAILED,
    },
    HarnessPhase.SYNTHESIS: {
        HarnessPhase.SYNTHESIS,
        HarnessPhase.RETRIEVAL,
        HarnessPhase.EVALUATION,
        HarnessPhase.WAITING,
        HarnessPhase.COMPLETE,
        HarnessPhase.FAILED,
    },
    HarnessPhase.WAITING: {HarnessPhase.PLANNING, HarnessPhase.FAILED},
    HarnessPhase.COMPLETE: set(),
    HarnessPhase.FAILED: set(),
}


def _require_text(value: str | None, field_name: str) -> None:
    if value is None or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class HarnessPolicy:
    max_steps: int = 40
    max_tool_calls: int = 24
    max_memory_items: int = 32
    allowed_capabilities: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        limits = (self.max_steps, self.max_tool_calls, self.max_memory_items)
        if any(value <= 0 for value in limits):
            raise ValueError("harness limits must be positive")

    def allows(self, capability_id: str) -> bool:
        return not self.allowed_capabilities or capability_id in self.allowed_capabilities


@dataclass(frozen=True, slots=True)
class HarnessCommand:
    kind: CommandKind
    next_phase: HarnessPhase
    reason: str
    target: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.reason, "command reason")
        if self.kind in TARGETED_COMMANDS:
            _require_text(self.target, "command target")
        expected_phase = FIXED_PHASES.get(self.kind)
        if expected_phase is not None and self.next_phase is not expected_phase:
            raise ValueError(f"{self.kind.value} must enter {expected_phase.value}")


@dataclass(frozen=True, slots=True)
class HarnessState:
    run_id: str
    as_of: date
    phase: HarnessPhase = HarnessPhase.INTAKE
    step_count: int = 0
    tool_call_count: int = 0
    memory_evidence_ids: tuple[str, ...] = ()
    last_target: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run id")
        if self.step_count < 0 or self.tool_call_count < 0:
            raise ValueError("harness counters cannot be negative")
        if len(set(self.memory_evidence_ids)) != len(self.memory_evidence_ids):
            raise ValueError("memory evidence ids must be unique")

    @property
    def terminal(self) -> bool:
        return self.phase in TERMINAL_PHASES


def advance(state: HarnessState, command: HarnessCommand, policy: HarnessPolicy) -> HarnessState:
    if state.terminal:
        raise ValueError("terminal harness state cannot advance")
    if command.next_phase not in ALLOWED_TRANSITIONS[state.phase]:
        raise ValueError(f"invalid harness transition: {state.phase.value} -> {command.next_phase.value}")
    if state.step_count >= policy.max_steps:
        raise RuntimeError("harness step limit reached")

    is_tool_call = command.kind is CommandKind.CALL_CAPABILITY
    tool_call_count = state.tool_call_count + int(is_tool_call)
    if is_tool_call and not policy.allows(command.target or ""):
        raise PermissionError(f"capability is not allowed: {command.target}")
    if tool_call_count > policy.max_tool_calls:
        raise RuntimeError("harness tool-call limit reached")

    return replace(
        state,
        phase=command.next_phase,
        step_count=state.step_count + 1,
        tool_call_count=tool_call_count,
        last_target=command.target,
        error=command.reason if command.kind is CommandKind.FAIL else state.error,
    )


def admit_evidence(
    state: HarnessState,
    evidence_id: str,
    ledger: EvidenceLedger,
    policy: HarnessPolicy,
) -> HarnessState:
    _require_text(evidence_id, "evidence id")
    if not ledger.has_admitted(evidence_id):
        raise ValueError(f"evidence has not passed the memory gate: {evidence_id}")
    if evidence_id in state.memory_evidence_ids:
        return state
    if len(state.memory_evidence_ids) >= policy.max_memory_items:
        raise RuntimeError("harness memory-item limit reached")
    return replace(state, memory_evidence_ids=state.memory_evidence_ids + (evidence_id,))


def reconcile_evidence(state: HarnessState, ledger: EvidenceLedger) -> HarnessState:
    eligible_ids = tuple(
        evidence_id
        for evidence_id in state.memory_evidence_ids
        if ledger.has_admitted(evidence_id)
    )
    if eligible_ids == state.memory_evidence_ids:
        return state
    return replace(state, memory_evidence_ids=eligible_ids)
