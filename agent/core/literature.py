"""Typed boundary for structured literature providers."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from agent.core.contracts import ExecutionContext
from agent.core.evidence import LiteratureRecord, SearchPlan


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class LiteratureQuery:
    """One reproducible query sent to one provider."""

    plan_id: str
    source: str
    query: str
    as_of: date
    limit: int = 20

    def __post_init__(self) -> None:
        for value, name in (
            (self.plan_id, "plan id"),
            (self.source, "source"),
            (self.query, "query"),
        ):
            _require_text(value, name)
        if self.limit <= 0:
            raise ValueError("query limit must be positive")


@dataclass(frozen=True, slots=True)
class LiteratureBatch:
    """Structured provider output with an auditable query boundary."""

    query: LiteratureQuery
    records: tuple[LiteratureRecord, ...]
    provider_version: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.provider_version, "provider version")
        if any(not warning.strip() for warning in self.warnings):
            raise ValueError("provider warnings cannot contain blank strings")
        for record in self.records:
            if record.plan_id != self.query.plan_id:
                raise ValueError("provider record plan does not match query")
            if record.source != self.query.source:
                raise ValueError("provider record source does not match query")
            if record.published_on and record.published_on > self.query.as_of:
                raise ValueError("provider record is newer than the query as_of date")


class LiteratureProvider(Protocol):
    """Port implemented by isolated literature service adapters."""

    def search(
        self,
        query: LiteratureQuery,
        context: ExecutionContext,
    ) -> LiteratureBatch: ...


def search_literature(
    provider: LiteratureProvider,
    plan: SearchPlan,
    source: str,
    query: str,
    context: ExecutionContext,
    *,
    limit: int = 20,
) -> LiteratureBatch:
    """Validate a planned query before and after crossing the provider port."""

    if source not in plan.sources:
        raise ValueError(f"source is not present in search plan: {source}")
    if query not in plan.queries:
        raise ValueError("query is not present in search plan")
    request = LiteratureQuery(plan.id, source, query, plan.as_of, limit)
    batch = provider.search(request, context)
    if batch.query != request:
        raise ValueError("provider returned a batch for a different query")
    return batch
