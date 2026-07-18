"""Bounded concurrent OA resolution and isolated paper reading."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Mapping

from .contracts import ExecutionContext, StreamEvent
from .evidence import LiteratureRecord
from .reader_text import pack_reader_text
from .research_types import (
    DocumentReadTelemetry, FullTextDocument, FullTextResolver, Reader, ReaderReport, ReaderTask,
    RegistryEvidenceResolver,
)


@dataclass(frozen=True, slots=True)
class ReadBatch:
    reports: list[ReaderReport]
    gaps: list[str]
    events: list[StreamEvent]
    telemetry: tuple[DocumentReadTelemetry, ...]
    peak_reader_concurrency: int

    def __iter__(self):
        yield self.reports
        yield self.gaps
        yield self.events


class _ReaderConcurrency:
    def __init__(self) -> None:
        self._lock, self.active, self.peak = Lock(), 0, 0

    def enter(self) -> None:
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)

    def leave(self) -> None:
        with self._lock:
            self.active -= 1


def read_records(records: tuple[LiteratureRecord, ...], resolvers: Mapping[str, FullTextResolver],
                 reader: Reader, context: ExecutionContext, max_workers: int,
                 registry: RegistryEvidenceResolver | None = None, clock=None) -> ReadBatch:
    outcomes, concurrency, timer = {}, _ReaderConcurrency(), clock or monotonic
    with ThreadPoolExecutor(max_workers=min(max_workers, len(records) or 1)) as pool:
        futures = {pool.submit(_pipeline, record, resolvers.get(record.source), reader, context,
                               registry, timer, concurrency): index
                   for index, record in enumerate(records)}
        for future in as_completed(futures):
            outcomes[futures[future]] = future.result()
    reports, gaps, events, telemetry = [], [], [], []
    for index in range(len(records)):
        report, item_gaps, item_telemetry = outcomes[index]
        telemetry.append(item_telemetry)
        gaps.extend(item_gaps)
        if report:
            reports.append(report)
            events.append(StreamEvent("tool.completed", {
                "name": "reader", "record_id": records[index].id,
                "source_path": item_telemetry.source_path,
                "total_seconds": item_telemetry.total_seconds}))
    return ReadBatch(reports, gaps, events, tuple(telemetry), concurrency.peak)


def _pipeline(record: LiteratureRecord, resolver: FullTextResolver | None, reader: Reader,
              context: ExecutionContext, registry: RegistryEvidenceResolver | None,
              clock, concurrency: _ReaderConcurrency
              ) -> tuple[ReaderReport | None, tuple[str, ...], DocumentReadTelemetry]:
    total_started = clock()
    document, gaps = None, []
    if resolver:
        try:
            document = resolver.resolve(record, context)
        except Exception as exc:
            gaps.append(f"{record.id}: {type(exc).__name__}: {exc}")
        try:
            detail = resolver.coverage_gap(record.id) if callable(
                getattr(resolver, "coverage_gap", None)) else ""
            if detail:
                gaps.append(f"{record.id}: {detail}")
        except Exception as exc:
            gaps.append(f"{record.id}: resolver gap failed: {type(exc).__name__}: {exc}")
    if document is None:
        gaps.append(f"{record.id}: abstract-only evidence")
    text = document.text if document else (record.abstract or record.title)
    registry_text = _registry_text(record, registry, context, gaps)
    if registry_text:
        text = text.rstrip() + "\n\n[REGISTRY SOURCE BOUNDARY]\n" + registry_text
    artifact = document.artifact if document else None
    source_path = _source_path(document)
    bound = getattr(reader, "max_chars", len(text) or 1)
    if isinstance(bound, bool) or not isinstance(bound, int) or bound <= 0:
        bound = len(text) or 1
    packed = pack_reader_text(text, bound)
    task = ReaderTask("reader-" + record.id, family_id(record), record, artifact, packed,
                      len(packed) < len(text))
    prepared = clock()
    concurrency.enter()
    reader_started = clock()
    report, status = None, "completed"
    try:
        report = reader.read(task)
        _validate_report(report, task)
    except Exception as exc:
        gaps.append(f"{record.id}: malformed reader output: {type(exc).__name__}: {exc}")
        report = None
        status = "reader_failed"
    finally:
        reader_finished = clock()
        concurrency.leave()
    telemetry = DocumentReadTelemetry(record.id, source_path,
        max(0.0, prepared - total_started), max(0.0, reader_finished - reader_started),
        max(0.0, reader_finished - total_started), status, source_path != "jats", len(packed))
    return report, tuple(gaps), telemetry


def _source_path(document: FullTextDocument | None) -> str:
    if document is None:
        return "abstract"
    if document.source_path:
        return document.source_path
    if document.artifact.media_type == "application/pdf":
        return "repository_pdf"
    if document.artifact.id.startswith("bioc-"):
        return "bioc"
    return "jats" if document.artifact.media_type.endswith("xml") else "other_full_text"


def _registry_text(record, registry, context, gaps) -> str:
    if registry is None:
        return ""
    try:
        text = registry.resolve(record, context)
    except Exception as exc:
        gaps.append(f"{record.id}: registry failed: {type(exc).__name__}: {exc}")
        text = ""
    try:
        detail = registry.coverage_gap(record.id)
        if detail:
            gaps.append(f"{record.id}: {detail}")
    except Exception as exc:
        gaps.append(f"{record.id}: registry gap failed: {type(exc).__name__}: {exc}")
    return text


def _validate_report(report, task: ReaderTask) -> None:
    if not isinstance(report, ReaderReport):
        raise TypeError("malformed reader output")
    if (report.task_id, report.family_id, report.record_id) != (
            task.task_id, task.family_id, task.record.id):
        raise ValueError("reader output identity mismatch")


def family_id(record: LiteratureRecord) -> str:
    values = {key.lower(): value.casefold() for key, value in record.identifiers.items()}
    for key in ("doi", "nct", "pmid"):
        if values.get(key):
            return key + ":" + values[key]
    return "title:" + " ".join(record.title.casefold().split())
