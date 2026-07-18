"""Executable literature intelligence controller with bounded reader isolation."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Mapping

from .contracts import ExecutionContext, StreamEvent
from .evidence import (
    EvidenceExcerpt, EvidenceLedger, EvidenceStrength, LiteratureRecord, ScreeningDecision,
    ScreeningOutcome, ScreeningStage,
)
from .harness import HarnessPhase, HarnessPolicy, HarnessState
from .literature import LiteratureProvider
from .research_execution import query_key, retrieve_queries
from .research_reading import family_id, read_records
from .research_screening import conservative_assessment
from .synthesis_recovery import synthesize_or_partial
from .research_types import (
    AuthorLead, FullTextResolver, HarnessTelemetry, KnowledgeCandidate, Reader, ReaderClaim,
    ReaderReport, ResearchRequest, ResearchResult, Screener, ScreeningAssessment,
    Synthesizer, WorkflowCheckpoint,
)


class ResearchController:
    """Compose retrieval, OA, readers, evidence admission, synthesis, and resume."""

    def __init__(self, providers: Mapping[str, LiteratureProvider],
                 full_text_resolvers: Mapping[str, FullTextResolver], reader: Reader,
                 synthesizer: Synthesizer, policy: HarnessPolicy, max_readers: int = 4,
                 screener: Screener | None = None, expander=None,
                 configuration_gaps: tuple[str, ...] = (), clock=monotonic,
                 max_reader_documents: int = 6) -> None:
        if max_readers <= 0 or max_reader_documents <= 0:
            raise ValueError("reader limits must be positive")
        self.providers = providers
        self.resolvers = full_text_resolvers
        self.reader = reader
        self.synthesizer = synthesizer
        self.policy = policy
        self.max_readers = max_readers
        self.max_reader_documents = max_reader_documents
        self.screener = screener
        self.expander = expander
        self.configuration_gaps = configuration_gaps
        self.clock = clock

    def run(self, request: ResearchRequest, context: ExecutionContext,
            checkpoint: WorkflowCheckpoint | None = None, *, stop_after_retrieval: bool = False,
            revoked_record_ids: tuple[str, ...] = ()) -> ResearchResult:
        started = self.clock()
        saved = checkpoint or WorkflowCheckpoint((), ())
        completed = set(saved.completed_queries)
        pending = tuple(item for item in request.queries if query_key(item) not in completed)
        records, events, new_completed = list(saved.records), [], []
        hits, counters = list(saved.hits), {"provider_calls": saved.provider_calls}
        gaps = list(dict.fromkeys(saved.coverage_gaps + self.configuration_gaps))
        state = HarnessState(context.job_id, request.plan.as_of, HarnessPhase.RETRIEVAL)
        state = retrieve_queries(request.plan, pending, self.providers, context, state, self.policy,
                                 records, events, new_completed, gaps, hits, counters)
        canonical = _canonicalize(records, hits)
        leads = _author_leads(canonical, self.providers)
        if self.expander:
            expansion = self.expander.expand(canonical, leads) if not saved.expansion_queries else None
            expansion_queries = expansion.queries if expansion else saved.expansion_queries
            gaps.extend(expansion.gaps if expansion else ())
            known = completed | set(new_completed)
            extra = tuple(item for item in expansion_queries if query_key(item) not in known)
            expanded_plan = replace(request.plan, queries=request.plan.queries + tuple(item.query for item in extra),
                                    sources=tuple(dict.fromkeys(request.plan.sources +
                                                  tuple(item.source for item in extra))))
            state = retrieve_queries(expanded_plan, extra, self.providers, context, state, self.policy,
                                     records, events, new_completed, gaps, hits, counters)
            canonical = _canonicalize(records, hits)
        candidates = _verify_candidates(request.knowledge_candidates, canonical, gaps)
        completed_keys = tuple(sorted(completed | set(new_completed)))
        if stop_after_retrieval:
            telemetry = _telemetry(counters, saved.reader_tasks, saved.elapsed_seconds, started, self.clock)
            saved = WorkflowCheckpoint(completed_keys, canonical, (), tuple(sorted(set(gaps))),
                                       saved.revoked_record_ids, expansion_queries if self.expander else (),
                                       tuple(hits), telemetry.provider_calls, telemetry.reader_tasks,
                                       telemetry.elapsed_seconds)
            return _result(canonical, (), EvidenceLedger(), candidates, gaps, "", saved, events,
                           hits=hits, telemetry=telemetry)
        reports = list(saved.reports)
        reader_tasks = saved.reader_tasks
        if not reports:
            selected = canonical[:self.max_reader_documents]
            reports, reader_gaps, reader_events = self._read(selected, context)
            reader_tasks += len(selected)
            if len(canonical) > len(selected):
                gaps.append(f"reader document cap omitted {len(canonical) - len(selected)} records")
            gaps.extend(reader_gaps)
            events.extend(reader_events)
        revoked = tuple(sorted(set(saved.revoked_record_ids) | set(revoked_record_ids)))
        ledger = _build_ledger(canonical, tuple(reports), revoked, self.screener, gaps)
        evidence = ledger.admitted()
        memory_ids = tuple(item.id for item in evidence)
        if not evidence:
            gaps.append("no evidence passed screening and memory admission")
        answer = synthesize_or_partial(self.synthesizer, request.plan.question, evidence,
                                       tuple(reports), gaps, events)
        telemetry = _telemetry(counters, reader_tasks, saved.elapsed_seconds, started, self.clock)
        saved = WorkflowCheckpoint(completed_keys, canonical, tuple(reports), tuple(sorted(set(gaps))), revoked,
                                   expansion_queries if self.expander else (), tuple(hits),
                                   telemetry.provider_calls, telemetry.reader_tasks, telemetry.elapsed_seconds)
        events.append(StreamEvent("done", {"records": len(canonical), "admitted": len(evidence),
                                            "coverage_gaps": len(set(gaps)),
                                            "provider_calls": telemetry.provider_calls,
                                            "reader_tasks": telemetry.reader_tasks,
                                            "elapsed_seconds": telemetry.elapsed_seconds}))
        leads = _author_leads(canonical, self.providers)
        return _result(canonical, tuple(reports), ledger, candidates, gaps, answer, saved, events, leads,
                       hits, telemetry)

    def _read(self, records: tuple[LiteratureRecord, ...], context: ExecutionContext
              ) -> tuple[list[ReaderReport], list[str], list[StreamEvent]]:
        return read_records(records, self.resolvers, self.reader, context, self.max_readers)
def _build_ledger(records: tuple[LiteratureRecord, ...], reports: tuple[ReaderReport, ...],
                  revoked: tuple[str, ...], screener: Screener | None,
                  gaps: list[str] | None = None) -> EvidenceLedger:
    ledger, now = EvidenceLedger(), datetime.now(timezone.utc)
    for record in records:
        ledger.add_record(record)
    for report in reports:
        record = next(item for item in records if item.id == report.record_id)
        try:
            assessment = screener.assess(report, record) if screener else conservative_assessment(report)
        except Exception as exc:
            if gaps is not None:
                gaps.append(f"{record.id}: screener failed: {type(exc).__name__}: {exc}")
            assessment = ScreeningAssessment("uncertain", ("screener failed",), EvidenceStrength.UNASSESSED)
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
def _canonicalize(records: list[LiteratureRecord], hits) -> tuple[LiteratureRecord, ...]:
    by_id = {record.id: record for record in records}
    ordered = [by_id[hit.record_id] for hit in hits if hit.record_id in by_id]
    observed = {item.id for item in ordered}
    ordered.extend(record for record in records if record.id not in observed)
    families: dict[str, LiteratureRecord] = {}
    for record in ordered:
        families.setdefault(family_id(record), record)
    return tuple(families.values())
def _telemetry(counters, readers, previous_elapsed, started, clock) -> HarnessTelemetry:
    elapsed = previous_elapsed + max(0.0, clock() - started)
    return HarnessTelemetry(counters["provider_calls"], readers, elapsed)
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


def _result(records, reports, ledger, candidates, gaps, answer, checkpoint, events, leads=(), hits=(),
            telemetry=HarnessTelemetry()) -> ResearchResult:
    memory = tuple(item.id for item in ledger.admitted())
    return ResearchResult(tuple(records), tuple(reports), ledger, memory, candidates,
                          tuple(sorted(set(gaps))), answer, checkpoint, tuple(events), tuple(leads),
                          tuple(hits), telemetry)
