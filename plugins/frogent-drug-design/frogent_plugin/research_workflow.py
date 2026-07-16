"""Executable literature intelligence controller with bounded reader isolation."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Mapping

from .contracts import ExecutionContext, StreamEvent
from .evidence import (
    EvidenceExcerpt, EvidenceLedger, EvidenceStrength, LiteratureRecord, ScreeningDecision,
    ScreeningOutcome, ScreeningStage,
)
from .harness import HarnessPhase, HarnessPolicy, HarnessState
from .literature import LiteratureProvider
from .research_types import (
    AuthorLead, FullTextResolver, KnowledgeCandidate, Reader, ReaderClaim, ReaderReport, ReaderTask,
    ResearchRequest, ResearchResult, Screener, ScreeningAssessment, Synthesizer, WorkflowCheckpoint,
)
from .retrieval import RetrievalCall, run_retrieval


class ResearchController:
    """Compose retrieval, OA, readers, evidence admission, synthesis, and resume."""

    def __init__(self, providers: Mapping[str, LiteratureProvider],
                 full_text_resolvers: Mapping[str, FullTextResolver], reader: Reader,
                 synthesizer: Synthesizer, policy: HarnessPolicy, max_readers: int = 4,
                 screener: Screener | None = None) -> None:
        if max_readers <= 0:
            raise ValueError("max_readers must be positive")
        self.providers = providers
        self.resolvers = full_text_resolvers
        self.reader = reader
        self.synthesizer = synthesizer
        self.policy = policy
        self.max_readers = max_readers
        self.screener = screener

    def run(self, request: ResearchRequest, context: ExecutionContext,
            checkpoint: WorkflowCheckpoint | None = None, *, stop_after_retrieval: bool = False,
            revoked_record_ids: tuple[str, ...] = ()) -> ResearchResult:
        saved = checkpoint or WorkflowCheckpoint((), ())
        completed = set(saved.completed_queries)
        pending = tuple(item for item in request.queries if _query_key(item) not in completed)
        records, events, new_completed = list(saved.records), [], []
        gaps = list(saved.coverage_gaps)
        state = HarnessState(context.job_id, request.plan.as_of, HarnessPhase.RETRIEVAL)
        for item in pending:
            call = RetrievalCall(item.capability_id, item.source, item.query, item.limit)
            retrieval = run_retrieval(request.plan, (call,), self.providers, context, state, self.policy)
            records.extend(retrieval.ledger.records())
            events.extend(event for event in retrieval.events if event.kind != "done")
            if retrieval.completed_calls:
                new_completed.append(_query_key(item))
            else:
                gaps.append(f"retrieval failed: {item.source} {item.query}: {retrieval.state.error}")
            state = HarnessState(context.job_id, request.plan.as_of, HarnessPhase.RETRIEVAL,
                                 retrieval.state.step_count, retrieval.state.tool_call_count)
        canonical = _canonicalize(records)
        candidates = _verify_candidates(request.knowledge_candidates, canonical, gaps)
        completed_keys = tuple(sorted(completed | set(new_completed)))
        if stop_after_retrieval:
            saved = WorkflowCheckpoint(completed_keys, canonical, (), tuple(sorted(set(gaps))),
                                       saved.revoked_record_ids)
            return _result(canonical, (), EvidenceLedger(), candidates, gaps, "", saved, events)
        reports = list(saved.reports)
        if not reports:
            reports, reader_gaps, reader_events = self._read(canonical, context)
            gaps.extend(reader_gaps)
            events.extend(reader_events)
        revoked = tuple(sorted(set(saved.revoked_record_ids) | set(revoked_record_ids)))
        ledger = _build_ledger(canonical, tuple(reports), revoked, self.screener)
        evidence = ledger.admitted()
        memory_ids = tuple(item.id for item in evidence)
        if not evidence:
            gaps.append("no evidence passed screening and memory admission")
        answer = self.synthesizer.synthesize(request.plan.question, evidence, tuple(reports),
                                             tuple(sorted(set(gaps))))
        saved = WorkflowCheckpoint(completed_keys, canonical, tuple(reports), tuple(sorted(set(gaps))), revoked)
        events.append(StreamEvent("done", {"records": len(canonical), "admitted": len(evidence),
                                            "coverage_gaps": len(set(gaps))}))
        leads = _author_leads(canonical, self.providers)
        return _result(canonical, tuple(reports), ledger, candidates, gaps, answer, saved, events, leads)

    def _read(self, records: tuple[LiteratureRecord, ...], context: ExecutionContext
              ) -> tuple[list[ReaderReport], list[str], list[StreamEvent]]:
        tasks, gaps, events = [], [], []
        for record in records:
            document = None
            resolver = self.resolvers.get(record.source)
            if resolver:
                try:
                    document = resolver.resolve(record, context)
                except Exception as exc:
                    gaps.append(f"{record.id}: {type(exc).__name__}: {exc}")
            if document is None:
                gaps.append(f"{record.id}: abstract-only evidence")
            text = document.text if document else (record.abstract or record.title)
            artifact = document.artifact if document else None
            tasks.append(ReaderTask("reader-" + record.id, _family_id(record), record, artifact, text))
        reports: list[ReaderReport] = []
        with ThreadPoolExecutor(max_workers=min(self.max_readers, len(tasks) or 1)) as pool:
            futures = {pool.submit(self.reader.read, task): task for task in tasks}
            for future in as_completed(futures):
                task = futures[future]
                report, gap = _reader_result(future, task)
                if report:
                    reports.append(report)
                    events.append(StreamEvent("tool.completed", {"name": "reader", "record_id": task.record.id}))
                if gap:
                    gaps.append(gap)
        return sorted(reports, key=lambda item: item.task_id), gaps, events


def _build_ledger(records: tuple[LiteratureRecord, ...], reports: tuple[ReaderReport, ...],
                  revoked: tuple[str, ...], screener: Screener | None) -> EvidenceLedger:
    ledger, now = EvidenceLedger(), datetime.now(timezone.utc)
    for record in records:
        ledger.add_record(record)
    for report in reports:
        record = next(item for item in records if item.id == report.record_id)
        assessment = screener.assess(report, record) if screener else _default_assessment(report)
        outcome = ScreeningOutcome(assessment.outcome)
        ledger.add_decision(ScreeningDecision("screen-" + report.record_id, report.record_id,
                            ScreeningStage.ABSTRACT, outcome, assessment.reasons, now))
        if outcome is ScreeningOutcome.INCLUDE:
            claim = report.claims[0]
            ledger.admit(_excerpt(report.record_id, claim, report.limitations, assessment.strength))
    for index, record_id in enumerate(revoked):
        if record_id in {item.id for item in records}:
            ledger.add_decision(ScreeningDecision("revoke-" + record_id, record_id,
                                ScreeningStage.FULL_TEXT, ScreeningOutcome.EXCLUDE,
                                ("correction or retraction",), now + timedelta(seconds=index + 1)))
    return ledger


def _excerpt(record_id: str, claim: ReaderClaim, report_limits: tuple[str, ...],
             strength: EvidenceStrength) -> EvidenceExcerpt:
    limitations = tuple(dict.fromkeys(claim.limitations + report_limits))
    return EvidenceExcerpt("ev-" + record_id, record_id, claim.statement, claim.locator, strength, limitations)


def _default_assessment(report: ReaderReport) -> ScreeningAssessment:
    if report.integrity_status == "retracted":
        return ScreeningAssessment("exclude", ("retracted record",), EvidenceStrength.UNASSESSED)
    if report.integrity_status not in {"clear", "corrected"}:
        return ScreeningAssessment("uncertain", ("integrity unresolved",), EvidenceStrength.UNASSESSED)
    if any(not claim.statement.strip() or not claim.locator.strip() for claim in report.claims):
        return ScreeningAssessment("uncertain", ("claim or locator missing",), EvidenceStrength.UNASSESSED)
    return ScreeningAssessment("include", ("structured reader report passed conservative gate",),
                               EvidenceStrength.LOW)


def _verify_candidates(candidates: tuple[KnowledgeCandidate, ...], records: tuple[LiteratureRecord, ...],
                       gaps: list[str]) -> tuple[KnowledgeCandidate, ...]:
    verified = []
    for candidate in candidates:
        match = next((item for item in records if _candidate_matches(candidate, item)), None)
        status = "verified" if match else "rejected"
        if match is None:
            gaps.append(f"knowledge candidate rejected: {candidate.id}")
        verified.append(replace(candidate, status=status, verified_record_id=match.id if match else ""))
    return tuple(verified)


def _candidate_matches(candidate: KnowledgeCandidate, record: LiteratureRecord) -> bool:
    identifiers = {key.lower(): value.casefold() for key, value in record.identifiers.items()}
    if candidate.pmid:
        return identifiers.get("pmid") == candidate.pmid.casefold()
    if candidate.doi:
        return identifiers.get("doi") == candidate.doi.casefold()
    if candidate.kind in {"author", "author_lab"}:
        return False
    return candidate.value.casefold() in record.title.casefold()


def _canonicalize(records: list[LiteratureRecord]) -> tuple[LiteratureRecord, ...]:
    families: dict[str, LiteratureRecord] = {}
    for record in records:
        families.setdefault(_family_id(record), record)
    return tuple(sorted(families.values(), key=lambda item: item.id))


def _family_id(record: LiteratureRecord) -> str:
    values = {key.lower(): value.casefold() for key, value in record.identifiers.items()}
    for key in ("doi", "nct", "pmid"):
        if values.get(key):
            return key + ":" + values[key]
    return "title:" + " ".join(record.title.casefold().split())


def _query_key(item) -> str:
    return "|".join((item.capability_id, item.source, item.query))


def _reader_result(future, task: ReaderTask) -> tuple[ReaderReport | None, str]:
    try:
        report = future.result()
        if not isinstance(report, ReaderReport):
            raise TypeError("malformed reader output")
        if (report.task_id, report.family_id, report.record_id) != (
                task.task_id, task.family_id, task.record.id):
            raise ValueError("reader output identity mismatch")
        return report, ""
    except Exception as exc:
        return None, f"{task.record.id}: malformed reader output: {type(exc).__name__}: {exc}"


def _author_leads(records, providers) -> tuple[AuthorLead, ...]:
    leads = {}
    for record in records:
        for provider in providers.values():
            for lead in _provider_leads(record, provider):
                leads[(record.id, lead.name, lead.orcid)] = lead
    return tuple(leads[key] for key in sorted(leads))


def _provider_leads(record, provider) -> tuple[AuthorLead, ...]:
    metadata = provider.metadata(record.id) if callable(getattr(provider, "metadata", None)) else {}
    authors = metadata.get("authors", ()) if isinstance(metadata, Mapping) else ()
    result = []
    for item in authors:
        name = str(item.get("fullName") or item.get("name") or item.get("collectiveName") or "").strip()
        if name:
            result.append(AuthorLead(record.id, name, str(item.get("orcid") or ""),
                                     _affiliations(item)))
    return tuple(result)


def _affiliations(item: Mapping[str, object]) -> tuple[str, ...]:
    values = list(item.get("affiliations") or ())
    details = item.get("authorAffiliationDetailsList") or {}
    if isinstance(details, Mapping):
        values.extend(row.get("affiliation", "") for row in details.get("authorAffiliation", ()))
    return tuple(text for value in values if (text := str(value).strip()))


def _result(records, reports, ledger, candidates, gaps, answer, checkpoint, events, leads=()) -> ResearchResult:
    memory = tuple(item.id for item in ledger.admitted())
    return ResearchResult(tuple(records), tuple(reports), ledger, memory, candidates,
                          tuple(sorted(set(gaps))), answer, checkpoint, tuple(events), tuple(leads))
