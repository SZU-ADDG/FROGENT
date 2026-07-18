"""Bounded concurrent OA resolution and isolated paper reading."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Mapping

from .contracts import ExecutionContext, StreamEvent
from .evidence import LiteratureRecord
from .research_types import FullTextResolver, Reader, ReaderReport, ReaderTask, RegistryEvidenceResolver


def read_records(records: tuple[LiteratureRecord, ...], resolvers: Mapping[str, FullTextResolver],
                 reader: Reader, context: ExecutionContext, max_workers: int,
                 registry: RegistryEvidenceResolver | None = None
                 ) -> tuple[list[ReaderReport], list[str], list[StreamEvent]]:
    outcomes = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(records) or 1)) as pool:
        futures = {pool.submit(_pipeline, record, resolvers.get(record.source), reader, context,
                               registry): index
                   for index, record in enumerate(records)}
        for future in as_completed(futures):
            outcomes[futures[future]] = future.result()
    reports, gaps, events = [], [], []
    for index in range(len(records)):
        report, item_gaps = outcomes[index]
        gaps.extend(item_gaps)
        if report:
            reports.append(report)
            events.append(StreamEvent("tool.completed", {
                "name": "reader", "record_id": records[index].id}))
    return reports, gaps, events


def _pipeline(record: LiteratureRecord, resolver: FullTextResolver | None, reader: Reader,
              context: ExecutionContext, registry: RegistryEvidenceResolver | None
              ) -> tuple[ReaderReport | None, tuple[str, ...]]:
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
    task = ReaderTask("reader-" + record.id, family_id(record), record, artifact, text)
    try:
        report = reader.read(task)
        _validate_report(report, task)
        return report, tuple(gaps)
    except Exception as exc:
        gaps.append(f"{record.id}: malformed reader output: {type(exc).__name__}: {exc}")
        return None, tuple(gaps)


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
