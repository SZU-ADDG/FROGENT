"""Plugin-contained versioned JSON session memory backed by SQLite."""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Mapping

from .contracts import ArtifactRef
from .evidence import LiteratureRecord, SearchPlan
from .research_types import (
    DocumentReadTelemetry, KnowledgeCandidate, ReaderClaim, ReaderReport, ResearchHit,
    ResearchQuery, ResearchRequest, WorkflowCheckpoint,
)

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ResearchMemory:
    request: ResearchRequest
    checkpoint: WorkflowCheckpoint
    admitted_evidence: tuple[Mapping[str, object], ...] = ()
    answer_versions: tuple[str, ...] = ()
    revocations: tuple[str, ...] = ()
    conversation_context: tuple[Mapping[str, object], ...] = ()


class SQLiteResearchStore:
    """Isolate one JSON state per user and conversation in atomic transactions."""

    def __init__(self, path: Path, plugin_root: Path) -> None:
        self.root = plugin_root.resolve()
        self.path = path.resolve(strict=False)
        try:
            self.path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("memory database must stay inside plugin root") from exc
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != self.root.parent):
            raise ValueError("memory database path cannot traverse symlinks")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS research_memory ("
                               "user_id TEXT NOT NULL, conversation_id TEXT NOT NULL, payload TEXT NOT NULL, "
                               "updated_at TEXT NOT NULL, PRIMARY KEY(user_id, conversation_id))")

    def load(self, user_id: str, conversation_id: str) -> ResearchMemory | None:
        _identity(user_id, conversation_id)
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT payload FROM research_memory WHERE user_id=? AND conversation_id=?",
                                     (user_id, conversation_id)).fetchone()
        return _decode(json.loads(row[0])) if row else None

    def save(self, user_id: str, conversation_id: str, state: ResearchMemory) -> None:
        _identity(user_id, conversation_id)
        payload = json.dumps(_encode(state), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO research_memory VALUES(?,?,?,?) "
                               "ON CONFLICT(user_id,conversation_id) DO UPDATE SET "
                               "payload=excluded.payload,updated_at=excluded.updated_at",
                               (user_id, conversation_id, payload, now))

    def delete(self, user_id: str, conversation_id: str) -> None:
        _identity(user_id, conversation_id)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM research_memory WHERE user_id=? AND conversation_id=?",
                               (user_id, conversation_id))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)


def _identity(user_id: str, conversation_id: str) -> None:
    if not user_id.strip() or not conversation_id.strip():
        raise ValueError("memory identity fields must be non-empty")


def _encode(state: ResearchMemory) -> dict[str, object]:
    return {"schema_version": SCHEMA_VERSION, "request": _request_dict(state.request),
            "checkpoint": _checkpoint_dict(state.checkpoint),
            "admitted_evidence": [dict(item) for item in state.admitted_evidence],
            "answer_versions": list(state.answer_versions), "revocations": list(state.revocations),
            "conversation_context": [dict(item) for item in state.conversation_context]}


def _decode(value: Mapping[str, object]) -> ResearchMemory:
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported memory schema version")
    return ResearchMemory(_request(value["request"]), _checkpoint(value["checkpoint"]),
                          tuple(value.get("admitted_evidence", ())),
                          tuple(value.get("answer_versions", ())), tuple(value.get("revocations", ())),
                          tuple(value.get("conversation_context", ())))


def _request_dict(request: ResearchRequest) -> dict[str, object]:
    plan = request.plan
    return {"plan": {"id": plan.id, "question": plan.question, "as_of": plan.as_of.isoformat(),
            "queries": list(plan.queries), "sources": list(plan.sources),
            "inclusion_criteria": list(plan.inclusion_criteria),
            "exclusion_criteria": list(plan.exclusion_criteria), "stop_rules": list(plan.stop_rules)},
            "queries": [{"capability_id": item.capability_id, "source": item.source,
                         "query": item.query, "limit": item.limit, "wave": item.wave,
                         "provenance": item.provenance} for item in request.queries],
            "knowledge_candidates": [{"id": item.id, "kind": item.kind, "value": item.value,
                "claim": item.claim, "verification_query": item.verification_query, "pmid": item.pmid,
                "doi": item.doi, "status": item.status, "verified_record_id": item.verified_record_id}
                for item in request.knowledge_candidates]}


def _request(value: object) -> ResearchRequest:
    data, plan = _mapping(value), _mapping(_mapping(value)["plan"])
    search_plan = SearchPlan(str(plan["id"]), str(plan["question"]), date.fromisoformat(str(plan["as_of"])),
                             tuple(plan["queries"]), tuple(plan["sources"]),
                             tuple(plan["inclusion_criteria"]), tuple(plan["exclusion_criteria"]),
                             tuple(plan["stop_rules"]))
    queries = tuple(ResearchQuery(str(item["capability_id"]), str(item["source"]), str(item["query"]),
                                  int(item["limit"]), str(item["wave"]), str(item["provenance"]))
                    for item in data["queries"])
    candidates = tuple(KnowledgeCandidate(str(item["id"]), str(item["kind"]), str(item["value"]),
                       str(item["claim"]), str(item["verification_query"]), str(item["pmid"]),
                       str(item["doi"]), str(item["status"]), str(item["verified_record_id"]))
                       for item in data["knowledge_candidates"])
    return ResearchRequest(search_plan, queries, candidates)


def _checkpoint_dict(checkpoint: WorkflowCheckpoint) -> dict[str, object]:
    return {"completed_queries": list(checkpoint.completed_queries),
            "records": [_record_dict(item) for item in checkpoint.records],
            "reports": [_report_dict(item) for item in checkpoint.reports],
            "coverage_gaps": list(checkpoint.coverage_gaps),
            "revoked_record_ids": list(checkpoint.revoked_record_ids),
            "expansion_queries": [{"capability_id": item.capability_id, "source": item.source,
                "query": item.query, "limit": item.limit, "wave": item.wave,
                "provenance": item.provenance} for item in checkpoint.expansion_queries],
            "hits": [{"source": item.source, "query": item.query, "wave": item.wave,
                      "rank": item.rank, "occurrence": item.occurrence, "record_id": item.record_id}
                     for item in checkpoint.hits], "provider_calls": checkpoint.provider_calls,
            "reader_tasks": checkpoint.reader_tasks, "elapsed_seconds": checkpoint.elapsed_seconds,
            "read_telemetry": [_read_telemetry_dict(item) for item in checkpoint.read_telemetry],
            "peak_reader_concurrency": checkpoint.peak_reader_concurrency}


def _checkpoint(value: object) -> WorkflowCheckpoint:
    data = _mapping(value)
    expansion = tuple(ResearchQuery(str(item["capability_id"]), str(item["source"]), str(item["query"]),
                      int(item["limit"]), str(item["wave"]), str(item["provenance"]))
                      for item in data.get("expansion_queries", ()))
    hits = tuple(ResearchHit(str(item["source"]), str(item["query"]), str(item["wave"]),
                 int(item["rank"]), int(item["occurrence"]), str(item["record_id"]))
                 for item in data.get("hits", ()))
    read_telemetry = tuple(_read_telemetry(item) for item in data.get("read_telemetry", ()))
    return WorkflowCheckpoint(tuple(data["completed_queries"]), tuple(_record(item) for item in data["records"]),
                              tuple(_report(item) for item in data["reports"]), tuple(data["coverage_gaps"]),
                              tuple(data["revoked_record_ids"]), expansion, hits,
                              int(data.get("provider_calls", 0)), int(data.get("reader_tasks", 0)),
                              float(data.get("elapsed_seconds", 0.0)), read_telemetry,
                              int(data.get("peak_reader_concurrency", 0)))


def _read_telemetry_dict(item: DocumentReadTelemetry) -> dict[str, object]:
    return {name: getattr(item, name) for name in ("record_id", "source_path",
            "preparation_seconds", "reader_seconds", "total_seconds", "status", "fallback",
            "packed_chars")}


def _read_telemetry(value: object) -> DocumentReadTelemetry:
    item = _mapping(value)
    return DocumentReadTelemetry(str(item["record_id"]), str(item["source_path"]),
        float(item["preparation_seconds"]), float(item["reader_seconds"]),
        float(item["total_seconds"]), str(item["status"]), bool(item["fallback"]),
        int(item["packed_chars"]))


def _record_dict(item: LiteratureRecord) -> dict[str, object]:
    artifact = item.raw_artifact
    return {"id": item.id, "plan_id": item.plan_id, "source": item.source, "title": item.title,
            "retrieved_at": item.retrieved_at.isoformat(), "identifiers": dict(item.identifiers),
            "artifact": {"id": artifact.id, "name": artifact.name, "media_type": artifact.media_type,
                         "uri": artifact.uri},
            "published_on": item.published_on.isoformat() if item.published_on else None,
            "abstract": item.abstract}


def _record(value: object) -> LiteratureRecord:
    item, artifact = _mapping(value), _mapping(_mapping(value)["artifact"])
    ref = ArtifactRef(str(artifact["id"]), str(artifact["name"]), str(artifact["media_type"]), str(artifact["uri"]))
    published = date.fromisoformat(str(item["published_on"])) if item.get("published_on") else None
    return LiteratureRecord(str(item["id"]), str(item["plan_id"]), str(item["source"]), str(item["title"]),
                            datetime.fromisoformat(str(item["retrieved_at"])), dict(item["identifiers"]),
                            ref, published, str(item["abstract"]))


def _report_dict(item: ReaderReport) -> dict[str, object]:
    return {"task_id": item.task_id, "family_id": item.family_id, "record_id": item.record_id,
            "claims": [{name: getattr(claim, name) for name in ("statement", "locator", "population_or_model",
                       "intervention", "comparator", "outcome", "direction", "magnitude", "limitations")}
                       for claim in item.claims], "counterevidence": item.counterevidence,
            "integrity_status": item.integrity_status, "limitations": list(item.limitations),
            "unresolved_questions": list(item.unresolved_questions)}


def _report(value: object) -> ReaderReport:
    item = _mapping(value)
    claims = tuple(ReaderClaim(str(row["statement"]), str(row["locator"]), str(row["population_or_model"]),
                   str(row["intervention"]), str(row["comparator"]), str(row["outcome"]),
                   str(row["direction"]), str(row["magnitude"]), tuple(row["limitations"]))
                   for row in item["claims"])
    return ReaderReport(str(item["task_id"]), str(item["family_id"]), str(item["record_id"]), claims,
                        bool(item["counterevidence"]), str(item["integrity_status"]),
                        tuple(item["limitations"]), tuple(item["unresolved_questions"]))


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError("memory JSON object is malformed")
    return value
