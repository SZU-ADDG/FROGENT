"""Versioned persistent state for qualitative design decisions."""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from agent.design.decision_policy import (
    CalibrationFinding, CalibrationOutcome, CalibrationRequest, DecisionConstraint,
    DecisionContext, DesignHypothesis, HypothesisPortfolio, OptimizationHandoff,
)

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class DesignMemory:
    request: str
    portfolio: HypothesisPortfolio | None
    findings: tuple[CalibrationFinding, ...] = ()
    answer_versions: tuple[str, ...] = ()
    conversation_context: tuple[Mapping[str, object], ...] = ()
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.request.strip() or type(self.revision) is not int or self.revision < 0:
            raise ValueError("design memory identity is invalid")
        if self.portfolio is None and self.findings:
            raise ValueError("design findings require a portfolio")


class SQLiteDesignStore:
    def __init__(self, path: Path, project_root: Path) -> None:
        self.root = project_root.resolve()
        self.path = path.resolve(strict=False)
        try:
            self.path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("design memory database must stay inside project root") from exc
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents
                                    if parent != self.root.parent):
            raise ValueError("design memory path cannot traverse symlinks")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS design_memory ("
                "user_id TEXT NOT NULL, conversation_id TEXT NOT NULL, payload TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, PRIMARY KEY(user_id,conversation_id))")

    def load(self, user_id: str, conversation_id: str) -> DesignMemory | None:
        _identity(user_id, conversation_id)
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT payload FROM design_memory "
                "WHERE user_id=? AND conversation_id=?", (user_id, conversation_id)).fetchone()
        return _decode(json.loads(row[0])) if row else None

    def save(self, user_id: str, conversation_id: str, state: DesignMemory) -> None:
        _identity(user_id, conversation_id)
        payload = json.dumps(_encode(state), ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"))
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO design_memory VALUES(?,?,?,?) "
                "ON CONFLICT(user_id,conversation_id) DO UPDATE SET "
                "payload=excluded.payload,updated_at=excluded.updated_at",
                (user_id, conversation_id, payload, datetime.now(timezone.utc).isoformat()))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)


def _encode(state: DesignMemory) -> dict[str, object]:
    return {"schema_version": SCHEMA_VERSION, "request": state.request,
            "portfolio": _portfolio_dict(state.portfolio) if state.portfolio else None,
            "findings": [{"hypothesis_id": item.hypothesis_id, "outcome": item.outcome.value,
                          "reason": item.reason, "source": item.source}
                         for item in state.findings],
            "answer_versions": list(state.answer_versions),
            "conversation_context": [dict(item) for item in state.conversation_context],
            "revision": state.revision}


def _decode(value: Mapping[str, object]) -> DesignMemory:
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported design memory schema version")
    portfolio = _portfolio(value["portfolio"]) if value.get("portfolio") else None
    findings = tuple(CalibrationFinding(str(item["hypothesis_id"]),
        CalibrationOutcome(str(item["outcome"])), str(item["reason"]), str(item["source"]))
        for item in value.get("findings", ()))
    return DesignMemory(str(value["request"]), portfolio, findings,
                        tuple(value.get("answer_versions", ())),
                        tuple(value.get("conversation_context", ())),
                        int(value.get("revision", 0)))


def _portfolio_dict(value: HypothesisPortfolio) -> dict[str, object]:
    context = value.context
    handoff = context.optimization_handoff
    return {"context": {"objective": context.objective,
        "reliable_discriminator": context.reliable_discriminator,
        "unresolved_qualitative_choices": context.unresolved_qualitative_choices,
        "discriminator": context.discriminator,
        "constraints": [{"text": item.text, "source_turn_id": item.source_turn_id,
                         "immutable": item.immutable} for item in context.constraints],
        "optimization_handoff": _handoff_dict(handoff) if handoff else None},
        "hypotheses": [_hypothesis_dict(item) for item in value.hypotheses]}


def _portfolio(value: object) -> HypothesisPortfolio:
    data = _mapping(value)
    raw_context = _mapping(data["context"])
    constraints = tuple(DecisionConstraint(str(item["text"]), str(item["source_turn_id"]),
                        _boolean(item["immutable"], "constraint immutable"))
                        for item in raw_context["constraints"])
    handoff = (_handoff(_mapping(raw_context["optimization_handoff"]))
               if raw_context.get("optimization_handoff") else None)
    context = DecisionContext(str(raw_context["objective"]),
        _boolean(raw_context["reliable_discriminator"], "reliable discriminator"),
        _boolean(raw_context["unresolved_qualitative_choices"],
                 "unresolved qualitative choices"),
        str(raw_context["discriminator"]), constraints, handoff)
    return HypothesisPortfolio(context, tuple(_hypothesis(item) for item in data["hypotheses"]))


def _hypothesis_dict(item: DesignHypothesis) -> dict[str, object]:
    return {"hypothesis_id": item.hypothesis_id, "rank": item.rank,
        "recommendation": item.recommendation, "rationale": item.rationale,
        "expected_benefits": list(item.expected_benefits), "tradeoffs": list(item.tradeoffs),
        "failure_modes": list(item.failure_modes), "knowledge_bases": list(item.knowledge_bases),
        "calibration_requests": [{"request_id": row.request_id,
            "capability_id": row.capability_id, "purpose": row.purpose,
            "decision_rule": row.decision_rule} for row in item.calibration_requests],
        "decisive_experiment": item.decisive_experiment, "confidence": item.confidence}


def _hypothesis(value: object) -> DesignHypothesis:
    item = _mapping(value)
    requests = tuple(CalibrationRequest(str(row["request_id"]), str(row["capability_id"]),
                     str(row["purpose"]), str(row["decision_rule"]))
                     for row in item["calibration_requests"])
    return DesignHypothesis(str(item["hypothesis_id"]), int(item["rank"]),
        str(item["recommendation"]), str(item["rationale"]),
        tuple(item["expected_benefits"]), tuple(item["tradeoffs"]), tuple(item["failure_modes"]),
        tuple(item["knowledge_bases"]), requests, str(item["decisive_experiment"]),
        str(item["confidence"]))


def _handoff_dict(value: OptimizationHandoff) -> dict[str, object]:
    return {"objective": value.objective, "constraints": list(value.constraints),
            "search_space": value.search_space, "discriminator": value.discriminator,
            "optimizer": value.optimizer, "stopping_rule": value.stopping_rule,
            "residual_qualitative_choices": list(value.residual_qualitative_choices)}


def _handoff(value: Mapping[str, object]) -> OptimizationHandoff:
    return OptimizationHandoff(str(value["objective"]), tuple(value["constraints"]),
        str(value["search_space"]), str(value["discriminator"]), str(value["optimizer"]),
        str(value["stopping_rule"]), tuple(value["residual_qualitative_choices"]))


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError("design memory JSON object is malformed")
    return value


def _identity(*values: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError("design memory identity fields must be non-empty")


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be boolean")
    return value
