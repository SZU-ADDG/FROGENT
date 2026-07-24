"""Traceable literature evidence kept outside the conversational memory."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from agent.core.contracts import ArtifactRef


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_items(values: tuple[str, ...], field_name: str) -> None:
    if not values or any(not value.strip() for value in values):
        raise ValueError(f"{field_name} must contain non-empty strings")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class ScreeningStage(StrEnum):
    METADATA = "metadata"
    ABSTRACT = "abstract"
    FULL_TEXT = "full_text"


class ScreeningOutcome(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    UNCERTAIN = "uncertain"


class EvidenceStrength(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNASSESSED = "unassessed"


STAGE_PRIORITY = {
    ScreeningStage.METADATA: 1,
    ScreeningStage.ABSTRACT: 2,
    ScreeningStage.FULL_TEXT: 3,
}


@dataclass(frozen=True, slots=True)
class SearchPlan:
    id: str
    question: str
    as_of: date
    queries: tuple[str, ...]
    sources: tuple[str, ...]
    inclusion_criteria: tuple[str, ...]
    exclusion_criteria: tuple[str, ...]
    stop_rules: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.id, "search plan id")
        _require_text(self.question, "search question")
        for values, name in (
            (self.queries, "queries"),
            (self.sources, "sources"),
            (self.inclusion_criteria, "inclusion criteria"),
            (self.exclusion_criteria, "exclusion criteria"),
            (self.stop_rules, "stop rules"),
        ):
            _require_items(values, name)


@dataclass(frozen=True, slots=True)
class LiteratureRecord:
    id: str
    plan_id: str
    source: str
    title: str
    retrieved_at: datetime
    identifiers: Mapping[str, str]
    raw_artifact: ArtifactRef
    published_on: date | None = None
    abstract: str = ""

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "record id"),
            (self.plan_id, "plan id"),
            (self.source, "source"),
            (self.title, "title"),
        ):
            _require_text(value, name)
        _require_aware(self.retrieved_at, "retrieved_at")
        identifiers = dict(self.identifiers)
        if not identifiers or any(not key.strip() or not value.strip() for key, value in identifiers.items()):
            raise ValueError("identifiers must contain non-empty keys and values")
        object.__setattr__(self, "identifiers", MappingProxyType(identifiers))


@dataclass(frozen=True, slots=True)
class ScreeningDecision:
    id: str
    record_id: str
    stage: ScreeningStage
    outcome: ScreeningOutcome
    reasons: tuple[str, ...]
    decided_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.id, "decision id")
        _require_text(self.record_id, "record id")
        _require_items(self.reasons, "screening reasons")
        _require_aware(self.decided_at, "decided_at")


@dataclass(frozen=True, slots=True)
class EvidenceExcerpt:
    id: str
    record_id: str
    claim: str
    locator: str
    strength: EvidenceStrength
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "evidence id"),
            (self.record_id, "record id"),
            (self.claim, "claim"),
            (self.locator, "locator"),
        ):
            _require_text(value, name)
        if any(not value.strip() for value in self.limitations):
            raise ValueError("limitations must contain non-empty strings")


@dataclass(frozen=True, slots=True)
class SynthesisClaim:
    id: str
    statement: str
    evidence_ids: tuple[str, ...]
    counterevidence_ids: tuple[str, ...]
    confidence: EvidenceStrength
    as_of: date
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.id, "claim id")
        _require_text(self.statement, "statement")
        _require_items(self.evidence_ids, "evidence ids")
        if any(not value.strip() for value in self.counterevidence_ids + self.limitations):
            raise ValueError("claim references and limitations cannot contain blank strings")


class EvidenceLedger:
    """Preserve raw records and admit only screened excerpts to memory."""

    def __init__(self) -> None:
        self._records: dict[str, LiteratureRecord] = {}
        self._decisions: dict[str, ScreeningDecision] = {}
        self._admitted: dict[str, EvidenceExcerpt] = {}

    def add_record(self, record: LiteratureRecord) -> None:
        if record.id in self._records:
            raise ValueError(f"duplicate literature record: {record.id}")
        self._records[record.id] = record

    def add_decision(self, decision: ScreeningDecision) -> None:
        if decision.record_id not in self._records:
            raise KeyError(f"unknown literature record: {decision.record_id}")
        if decision.id in self._decisions:
            raise ValueError(f"duplicate screening decision: {decision.id}")
        self._decisions[decision.id] = decision

    def latest_decision(self, record_id: str) -> ScreeningDecision:
        candidates = [item for item in self._decisions.values() if item.record_id == record_id]
        if not candidates:
            raise KeyError(f"record has no screening decision: {record_id}")
        return max(candidates, key=lambda item: (STAGE_PRIORITY[item.stage], item.decided_at, item.id))

    def admit(self, evidence: EvidenceExcerpt) -> None:
        decision = self.latest_decision(evidence.record_id)
        if decision.outcome is not ScreeningOutcome.INCLUDE:
            raise ValueError(f"record is not eligible for memory: {evidence.record_id}")
        if evidence.id in self._admitted:
            raise ValueError(f"duplicate evidence excerpt: {evidence.id}")
        self._admitted[evidence.id] = evidence

    def has_admitted(self, evidence_id: str) -> bool:
        evidence = self._admitted.get(evidence_id)
        if evidence is None:
            return False
        return self.latest_decision(evidence.record_id).outcome is ScreeningOutcome.INCLUDE

    def records(self) -> tuple[LiteratureRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def decisions(self) -> tuple[ScreeningDecision, ...]:
        return tuple(self._decisions[key] for key in sorted(self._decisions))

    def admitted(self) -> tuple[EvidenceExcerpt, ...]:
        return tuple(
            self._admitted[key]
            for key in sorted(self._admitted)
            if self.has_admitted(key)
        )
