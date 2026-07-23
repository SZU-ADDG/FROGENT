"""Typed contracts for literature intelligence orchestration."""

from dataclasses import dataclass
from typing import Protocol

from agent.core.contracts import ArtifactRef, ExecutionContext, StreamEvent
from agent.core.evidence import EvidenceExcerpt, EvidenceLedger, EvidenceStrength, LiteratureRecord, SearchPlan


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


@dataclass(frozen=True, slots=True)
class KnowledgeCandidate:
    id: str
    kind: str
    value: str
    claim: str
    verification_query: str
    pmid: str = ""
    doi: str = ""
    status: str = "unverified"
    verified_record_id: str = ""

    def __post_init__(self) -> None:
        for value, name in ((self.id, "candidate id"), (self.kind, "candidate kind"),
                            (self.value, "candidate value"), (self.claim, "candidate claim"),
                            (self.verification_query, "verification query")):
            _text(value, name)
        if self.status not in {"unverified", "verified", "rejected"}:
            raise ValueError("candidate status is invalid")


@dataclass(frozen=True, slots=True)
class ResearchQuery:
    capability_id: str
    source: str
    query: str
    limit: int = 20
    wave: str = "planned"
    provenance: str = "planner"

    def __post_init__(self) -> None:
        for value, name in ((self.capability_id, "capability id"), (self.source, "source"),
                            (self.query, "query"), (self.wave, "wave"),
                            (self.provenance, "provenance")):
            _text(value, name)
        if self.limit <= 0:
            raise ValueError("query limit must be positive")


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    plan: SearchPlan
    queries: tuple[ResearchQuery, ...]
    knowledge_candidates: tuple[KnowledgeCandidate, ...] = ()

    def __post_init__(self) -> None:
        if not self.queries:
            raise ValueError("research request needs explicit source-query pairs")


@dataclass(frozen=True, slots=True)
class FullTextDocument:
    record_id: str
    artifact: ArtifactRef
    text: str
    source_path: str = ""

    def __post_init__(self) -> None:
        _text(self.record_id, "full-text record id")
        _text(self.text, "full text")
        if self.source_path and self.source_path not in {
                "jats", "bioc", "repository_pdf", "oa_fallback", "other_full_text"}:
            raise ValueError("full-text source path is invalid")


@dataclass(frozen=True, slots=True)
class ReaderClaim:
    statement: str
    locator: str
    population_or_model: str
    intervention: str
    comparator: str
    outcome: str
    direction: str
    magnitude: str
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, name in ((self.statement, "statement"), (self.locator, "locator"),
                            (self.population_or_model, "population or model"),
                            (self.outcome, "outcome"), (self.direction, "direction")):
            _text(value, name)


@dataclass(frozen=True, slots=True)
class ReaderTask:
    task_id: str
    family_id: str
    record: LiteratureRecord
    full_text_artifact: ArtifactRef | None
    text: str
    text_truncated: bool = False


@dataclass(frozen=True, slots=True)
class ReaderReport:
    task_id: str
    family_id: str
    record_id: str
    claims: tuple[ReaderClaim, ...]
    counterevidence: bool
    integrity_status: str
    limitations: tuple[str, ...]
    unresolved_questions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.claims:
            raise ValueError("reader report needs claim-level evidence")
        if self.integrity_status not in {"clear", "corrected", "retracted", "uncertain"}:
            raise ValueError("reader integrity status is invalid")


class Reader(Protocol):
    def read(self, task: ReaderTask) -> ReaderReport: ...


class Synthesizer(Protocol):
    def synthesize(self, question: str, evidence: tuple[EvidenceExcerpt, ...],
                   reports: tuple[ReaderReport, ...], gaps: tuple[str, ...]) -> str: ...


class FullTextResolver(Protocol):
    def resolve(self, record: LiteratureRecord, context: ExecutionContext) -> FullTextDocument | None: ...


class RegistryEvidenceResolver(Protocol):
    def resolve(self, record: LiteratureRecord, context: ExecutionContext) -> str: ...

    def coverage_gap(self, record_id: str) -> str: ...


@dataclass(frozen=True, slots=True)
class ScreeningAssessment:
    outcome: str
    reasons: tuple[str, ...]
    strength: EvidenceStrength = EvidenceStrength.LOW

    def __post_init__(self) -> None:
        if self.outcome not in {"include", "exclude", "uncertain"} or not self.reasons:
            raise ValueError("screening assessment is invalid")


class Screener(Protocol):
    def assess(self, report: ReaderReport, record: LiteratureRecord) -> ScreeningAssessment: ...


@dataclass(frozen=True, slots=True)
class AuthorLead:
    record_id: str
    name: str
    orcid: str = ""
    affiliations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResearchHit:
    source: str
    query: str
    wave: str
    rank: int
    occurrence: int
    record_id: str


@dataclass(frozen=True, slots=True)
class DocumentReadTelemetry:
    record_id: str
    source_path: str
    preparation_seconds: float
    reader_seconds: float
    total_seconds: float
    status: str
    fallback: bool
    packed_chars: int

    def __post_init__(self) -> None:
        if not self.record_id.strip() or self.source_path not in {
                "jats", "bioc", "repository_pdf", "abstract", "oa_fallback", "other_full_text"}:
            raise ValueError("document read telemetry identity is invalid")
        values = (self.preparation_seconds, self.reader_seconds, self.total_seconds)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
               for value in values):
            raise ValueError("document read durations must be non-negative numbers")
        if self.status not in {"completed", "reader_failed"}:
            raise ValueError("document read status is invalid")
        if not isinstance(self.fallback, bool) or isinstance(self.packed_chars, bool) \
                or not isinstance(self.packed_chars, int) or self.packed_chars < 0:
            raise ValueError("document read fallback or packed character count is invalid")


@dataclass(frozen=True, slots=True)
class HarnessTelemetry:
    provider_calls: int = 0
    reader_tasks: int = 0
    elapsed_seconds: float = 0.0
    peak_reader_concurrency: int = 0
    documents: tuple[DocumentReadTelemetry, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowCheckpoint:
    completed_queries: tuple[str, ...]
    records: tuple[LiteratureRecord, ...]
    reports: tuple[ReaderReport, ...] = ()
    coverage_gaps: tuple[str, ...] = ()
    revoked_record_ids: tuple[str, ...] = ()
    expansion_queries: tuple[ResearchQuery, ...] = ()
    hits: tuple[ResearchHit, ...] = ()
    provider_calls: int = 0
    reader_tasks: int = 0
    elapsed_seconds: float = 0.0
    read_telemetry: tuple[DocumentReadTelemetry, ...] = ()
    peak_reader_concurrency: int = 0


@dataclass(frozen=True, slots=True)
class ResearchResult:
    raw_records: tuple[LiteratureRecord, ...]
    reader_reports: tuple[ReaderReport, ...]
    ledger: EvidenceLedger
    working_memory_ids: tuple[str, ...]
    knowledge_candidates: tuple[KnowledgeCandidate, ...]
    coverage_gaps: tuple[str, ...]
    answer: str
    checkpoint: WorkflowCheckpoint
    events: tuple[StreamEvent, ...]
    author_leads: tuple[AuthorLead, ...] = ()
    hits: tuple[ResearchHit, ...] = ()
    telemetry: HarnessTelemetry = HarnessTelemetry()
