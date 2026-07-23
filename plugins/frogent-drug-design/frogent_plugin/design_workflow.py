"""Persistent design judgment, calibration, reranking, and recovery."""

from dataclasses import dataclass
from typing import Mapping, Protocol

from .contracts import ExecutionContext, StreamEvent
from .decision_policy import (
    CalibratedHypothesis, CalibrationFinding, CalibrationOutcome, HypothesisPortfolio,
)
from .design_calibration import calibrate_portfolio, render_portfolio
from .design_memory import DesignMemory, SQLiteDesignStore
from .qualitative_design import CodexDesignStrategist, is_design_constraint_only


class DesignCalibrator(Protocol):
    def calibrate(self, portfolio: HypothesisPortfolio, message: str,
                  context: ExecutionContext) -> tuple[CalibrationFinding, ...]: ...


@dataclass(frozen=True, slots=True)
class DesignChatResult:
    answer: str
    events: tuple[StreamEvent, ...]
    portfolio: HypothesisPortfolio | None = None
    calibrated: tuple[CalibratedHypothesis, ...] = ()
    revision: int = 0


class QualitativeDesignHandler:
    def __init__(self, strategist: CodexDesignStrategist, store: SQLiteDesignStore | None = None,
                 calibrator: DesignCalibrator | None = None) -> None:
        self.strategist, self.store, self.calibrator = strategist, store, calibrator

    def run(self, message: str, context: ExecutionContext) -> DesignChatResult:
        return self.run_with_history(message, context, ())

    def run_with_history(self, message: str, context: ExecutionContext, history=()) -> DesignChatResult:
        saved = self._load(context)
        prior = saved.conversation_context if saved else ()
        conversation = _merge_context(prior, history)
        if is_design_constraint_only(message):
            return self._record_constraints(message, context, saved, conversation)
        if (saved and saved.request == message and saved.portfolio
                and conversation == tuple(prior)):
            return self._resume(context, saved)
        events = [StreamEvent("agent.changed", {"phase": "judgment",
                              "job_id": context.job_id}, "design")]
        try:
            portfolio = self.strategist.propose(message, conversation)
        except Exception as exc:
            return _failed_result(events, "judgment", exc)
        findings, calibration_events = self._calibrate(portfolio, message, context)
        events.extend(calibration_events)
        calibrated = calibrate_portfolio(portfolio, findings)
        answer = render_portfolio(portfolio, calibrated)
        revision = (saved.revision + 1) if saved else 1
        state = DesignMemory(message, portfolio, findings,
            ((saved.answer_versions if saved else ()) + (answer,))[-8:],
            _append_exchange(conversation, message, answer), revision)
        events.append(StreamEvent("tool.completed",
            _portfolio_payload(portfolio, calibrated, findings, revision), "design"))
        events.extend((StreamEvent("message.delta", {"content": answer}, "design"),
                       StreamEvent("done", {"status": "completed", "revision": revision}, "design")))
        return self._save(context, state, DesignChatResult(
            answer, tuple(events), portfolio, calibrated, revision))

    def apply_findings(self, context: ExecutionContext,
                       findings: tuple[CalibrationFinding, ...]) -> DesignChatResult:
        saved = self._load(context)
        if saved is None or saved.portfolio is None:
            raise KeyError("design session does not contain a portfolio")
        calibrated = calibrate_portfolio(saved.portfolio, findings)
        answer = render_portfolio(saved.portfolio, calibrated)
        revision = saved.revision + 1
        state = DesignMemory(saved.request, saved.portfolio, findings,
            (saved.answer_versions + (answer,))[-8:], saved.conversation_context, revision)
        events = (StreamEvent("tool.completed",
                  _portfolio_payload(saved.portfolio, calibrated, findings, revision), "design"),
                  StreamEvent("message.delta", {"content": answer}, "design"),
                  StreamEvent("done", {"status": "completed", "revision": revision}, "design"))
        return self._save(context, state, DesignChatResult(
            answer, events, saved.portfolio, calibrated, revision))

    def _calibrate(self, portfolio, message, context):
        if self.calibrator is None:
            return (), ()
        try:
            findings = tuple(self.calibrator.calibrate(portfolio, message, context))
            calibrate_portfolio(portfolio, findings)
            event = StreamEvent("tool.completed", {"capability_id": "agent.design-calibration",
                "status": "completed", "finding_count": len(findings)}, "design")
            return findings, (event,)
        except Exception as exc:
            findings = tuple(CalibrationFinding(item.hypothesis_id,
                CalibrationOutcome.UNAVAILABLE, f"{type(exc).__name__}: {exc}",
                type(self.calibrator).__name__) for item in portfolio.hypotheses)
            event = StreamEvent("error", {"stage": "calibration",
                "error_type": type(exc).__name__, "message": str(exc), "recoverable": True}, "design")
            return findings, (event,)

    def _record_constraints(self, message, context, saved, conversation):
        answer = "Design constraints recorded. I will apply them to the next ranked design portfolio."
        revision = (saved.revision + 1) if saved else 1
        state = DesignMemory(message, saved.portfolio if saved else None,
            saved.findings if saved else (), ((saved.answer_versions if saved else ()) + (answer,))[-8:],
            _append_exchange(conversation, message, answer), revision)
        events = (StreamEvent("tool.completed", {"capability_id": "agent.design-context",
                  "status": "completed", "revision": revision}, "design"),
                  StreamEvent("message.delta", {"content": answer}, "design"),
                  StreamEvent("done", {"status": "completed", "revision": revision}, "design"))
        return self._save(context, state, DesignChatResult(
            answer, events, state.portfolio, (), revision))

    def _resume(self, context, saved):
        calibrated = calibrate_portfolio(saved.portfolio, saved.findings)
        answer = render_portfolio(saved.portfolio, calibrated)
        events = (StreamEvent("tool.completed",
                  _portfolio_payload(saved.portfolio, calibrated, saved.findings,
                                     saved.revision, resumed=True), "design"),
                  StreamEvent("message.delta", {"content": answer}, "design"),
                  StreamEvent("done", {"status": "completed", "revision": saved.revision,
                                       "resumed": True}, "design"))
        return DesignChatResult(answer, events, saved.portfolio, calibrated, saved.revision)

    def _load(self, context):
        return self.store.load(context.user_id, context.conversation_id) if self.store else None

    def _save(self, context, state, result):
        if self.store is None:
            return result
        try:
            self.store.save(context.user_id, context.conversation_id, state)
            return result
        except Exception as exc:
            event = StreamEvent("error", {"stage": "design_memory",
                "error_type": type(exc).__name__, "message": str(exc), "recoverable": True}, "design")
            events = result.events[:-1] + (event, result.events[-1])
            return DesignChatResult(result.answer, events, result.portfolio,
                                    result.calibrated, result.revision)


def _failed_result(events, stage, exc):
    answer = f"Design analysis could not complete: {type(exc).__name__}: {exc}"
    events.extend((StreamEvent("error", {"stage": stage, "error_type": type(exc).__name__,
        "message": str(exc), "recoverable": True}, "design"),
        StreamEvent("message.delta", {"content": answer}, "design"),
        StreamEvent("done", {"status": "failed"}, "design")))
    return DesignChatResult(answer, tuple(events))


def _merge_context(saved, history):
    values = list(saved)
    for item in tuple(history)[-8:]:
        if not isinstance(item, Mapping):
            continue
        content, role = item.get("content"), item.get("role")
        role = role if role in {"user", "assistant"} else (
            "user" if item.get("isUser") else "assistant")
        if isinstance(content, str) and content.strip():
            values.append({"role": role, "content": content.strip()[:2000]})
    deduped = []
    for item in values:
        identity = (item.get("role"), item.get("content"))
        if identity not in {(row.get("role"), row.get("content")) for row in deduped}:
            deduped.append(item)
    return tuple(deduped[-8:])


def _append_exchange(history, message, answer):
    return tuple((list(history) + [{"role": "user", "content": message[:2000]},
                  {"role": "assistant", "content": answer[:2000]}])[-8:])


def _portfolio_payload(portfolio, calibrated, findings, revision, resumed=False):
    states = {item.hypothesis.hypothesis_id: item for item in calibrated}
    return {"capability_id": "agent.qualitative-judgment", "status": "completed",
        "regime": portfolio.context.regime.value, "objective": portfolio.context.objective,
        "revision": revision, "resumed": resumed,
        "constraints": [{"text": item.text, "source_turn_id": item.source_turn_id,
                         "immutable": item.immutable} for item in portfolio.context.constraints],
        "hypotheses": [{"id": item.hypothesis_id, "initial_rank": item.rank,
            "adjusted_rank": states[item.hypothesis_id].adjusted_rank,
            "state": states[item.hypothesis_id].state.value,
            "recommendation": item.recommendation, "rationale": item.rationale,
            "expected_benefits": list(item.expected_benefits), "tradeoffs": list(item.tradeoffs),
            "failure_modes": list(item.failure_modes), "knowledge_bases": list(item.knowledge_bases),
            "confidence": item.confidence, "decisive_experiment": item.decisive_experiment,
            "calibration_requests": [{"request_id": row.request_id,
                "capability_id": row.capability_id, "purpose": row.purpose,
                "decision_rule": row.decision_rule} for row in item.calibration_requests]}
            for item in portfolio.hypotheses],
        "findings": [{"hypothesis_id": item.hypothesis_id, "outcome": item.outcome.value,
                      "reason": item.reason, "source": item.source} for item in findings]}
