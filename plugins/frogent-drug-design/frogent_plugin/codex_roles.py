"""Strict Codex implementations of planner, reader, screener, and synthesizer."""

from datetime import date
from typing import Mapping

from .codex_client import CodexClient
from .codex_schemas import planner_schema, reader_schema, screener_schema, synthesizer_schema
from .contracts import ExecutionContext
from .evidence import EvidenceExcerpt, EvidenceStrength, LiteratureRecord, SearchPlan
from .reader_text import pack_reader_text
from .research_types import (
    KnowledgeCandidate, ReaderClaim, ReaderReport, ReaderTask, ResearchQuery, ResearchRequest,
    ScreeningAssessment,
)


def _shape(value: Mapping[str, object], required: set[str], optional: set[str] = set()) -> None:
    missing, unknown = required - value.keys(), value.keys() - required - optional
    if missing:
        raise ValueError("missing fields: " + ", ".join(sorted(missing)))
    if unknown:
        raise ValueError("unknown fields: " + ", ".join(sorted(unknown)))


def _strings(value: object, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"{name} must be a list of strings")
    result = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    if len(result) != len(value) or len(set(result)) != len(result):
        raise ValueError(f"{name} must contain unique non-empty strings")
    return result


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


class CodexPlanner:
    def __init__(self, client: CodexClient, routes: tuple[str, ...], max_queries: int = 12,
                 max_results_per_query: int = 10) -> None:
        if not routes or max_queries <= 0 or max_results_per_query <= 0:
            raise ValueError("planner needs routes and a positive query cap")
        self.client, self.routes = client, routes
        self.max_queries, self.max_results_per_query = max_queries, max_results_per_query

    def plan(self, question: str, as_of: date, context: ExecutionContext, history=()) -> ResearchRequest:
        capability_map = {"europe_pmc": "europe-pmc.search", "pubmed": "pubmed.search"}
        contract = ("fields plan_id,question,as_of,queries,inclusion_criteria,exclusion_criteria,"
                    "stop_rules,knowledge_candidates. queries: capability_id/source/wave/query/limit. "
                    f"Allowed route-to-capability map={capability_map}; routes={list(self.routes)}; "
                    f"max queries={self.max_queries}; max results per query={self.max_results_per_query}. "
                    "Knowledge candidates remain unverified and need verification_query.")
        value = self.client.generate("biomedical research planner", contract,
                                     {"question": question, "as_of": as_of.isoformat(),
                                      "available_routes": list(self.routes),
                                      "recent_history": _history(history)},
                                     schema=planner_schema(self.routes, self.max_queries,
                                                           self.max_results_per_query))
        required = {"plan_id", "question", "as_of", "queries", "inclusion_criteria",
                    "exclusion_criteria", "stop_rules", "knowledge_candidates"}
        _shape(value, required)
        if _text(value["question"], "question") != question or value["as_of"] != as_of.isoformat():
            raise ValueError("planner changed question or as_of")
        queries = self._queries(value["queries"])
        candidates = tuple(_candidate(item) for item in _objects(value["knowledge_candidates"], "candidates"))
        sources = tuple(dict.fromkeys(item.source for item in queries))
        plan = SearchPlan(_text(value["plan_id"], "plan id"), question, as_of,
                          tuple(item.query for item in queries), sources,
                          _strings(value["inclusion_criteria"], "inclusion criteria"),
                          _strings(value["exclusion_criteria"], "exclusion criteria"),
                          _strings(value["stop_rules"], "stop rules"))
        return ResearchRequest(plan, queries, candidates)

    def _queries(self, value: object) -> tuple[ResearchQuery, ...]:
        items = _objects(value, "queries")
        if not items or len(items) > self.max_queries:
            raise ValueError("planner query count violates cap")
        result = []
        for item in items:
            _shape(item, {"capability_id", "source", "wave", "query", "limit"})
            source = _text(item["source"], "query source")
            limit = item["limit"]
            capability = _text(item["capability_id"], "capability id")
            wave = _text(item["wave"], "query wave")
            expected = {"europe_pmc": "europe-pmc.search", "pubmed": "pubmed.search"}.get(source)
            waves = {"sentinel", "discovery", "confirmation", "expansion", "challenge", "update"}
            valid_limit = type(limit) is int and 1 <= limit <= self.max_results_per_query
            if source not in self.routes or capability != expected or wave not in waves or not valid_limit:
                raise ValueError("planner query route or limit is invalid")
            result.append(ResearchQuery(capability, source, _text(item["query"], "query"), limit, wave))
        if len({(item.source, item.query) for item in result}) != len(result):
            raise ValueError("planner queries must be unique")
        return tuple(result)


class CodexReader:
    def __init__(self, client: CodexClient, max_chars: int = 60000) -> None:
        if max_chars <= 0:
            raise ValueError("reader text bound must be positive")
        self.client, self.max_chars = client, max_chars

    def read(self, task: ReaderTask) -> ReaderReport:
        contract = ("fields task_id,family_id,record_id,claims,counterevidence,integrity_status,"
                    "limitations,unresolved_questions. Each claim has statement,locator,population_or_model,"
                    "intervention,comparator,outcome,direction,magnitude,limitations.")
        packed = task.text if task.text_truncated else pack_reader_text(task.text, self.max_chars)
        instruction = ("Extract claim-level evidence only; never return full text. Compare publication "
                       "enrollment, design, and outcomes against [REGISTRY] evidence; report endpoint "
                       "drift and result-posting gaps. Registry protocol fields describe planned design "
                       "and are not observed efficacy or safety results.")
        value = self.client.generate("bounded biomedical paper reader", contract + " " + instruction,
            {"task_id": task.task_id, "family_id": task.family_id, "record_id": task.record.id,
             "title": task.record.title, "identifiers": dict(task.record.identifiers),
             "artifact": task.full_text_artifact.uri if task.full_text_artifact else task.record.raw_artifact.uri,
             "text": packed, "text_truncated": task.text_truncated or len(task.text) > len(packed)},
            schema=reader_schema())
        required = {"task_id", "family_id", "record_id", "claims", "counterevidence",
                    "integrity_status", "limitations", "unresolved_questions"}
        _shape(value, required)
        claims = tuple(_claim(item) for item in _objects(value["claims"], "claims"))
        if not isinstance(value["counterevidence"], bool):
            raise ValueError("counterevidence must be boolean")
        return ReaderReport(_text(value["task_id"], "task id"), _text(value["family_id"], "family id"),
                            _text(value["record_id"], "record id"), claims, value["counterevidence"],
                            _text(value["integrity_status"], "integrity status"),
                            _strings(value["limitations"], "limitations", allow_empty=True),
                            _strings(value["unresolved_questions"], "unresolved questions", allow_empty=True))


class CodexScreener:
    def __init__(self, client: CodexClient) -> None: self.client = client

    def assess(self, report: ReaderReport, record: LiteratureRecord) -> ScreeningAssessment:
        value = self.client.generate("conservative evidence screener",
            "fields outcome,reasons,strength; outcome include/exclude/uncertain; strength high/moderate/low/unassessed",
            {"record_id": record.id, "title": record.title, "integrity_status": report.integrity_status,
             "claims": [_claim_payload(item) for item in report.claims],
             "limitations": list(report.limitations)}, schema=screener_schema())
        _shape(value, {"outcome", "reasons", "strength"})
        strength = EvidenceStrength(_text(value["strength"], "strength"))
        return ScreeningAssessment(_text(value["outcome"], "outcome"),
                                   _strings(value["reasons"], "reasons"), strength)


class CodexSynthesizer:
    def __init__(self, client: CodexClient) -> None: self.client = client

    def synthesize(self, question: str, evidence: tuple[EvidenceExcerpt, ...],
                   reports: tuple[ReaderReport, ...], gaps: tuple[str, ...]) -> str:
        allowed = tuple(item.id for item in evidence)
        schema = synthesizer_schema(allowed)
        value = self.client.generate("evidence-bounded biomedical synthesizer",
            "fields source_study_answer,current_evidence_update,citations,counterevidence,gaps,limitations. "
            "Use only supplied admitted evidence IDs; calibrate verdict to the source study before later updates.",
            {"question": question, "admitted_evidence": [_evidence_payload(item) for item in evidence],
             "coverage_gaps": list(gaps)}, schema=schema)
        try:
            return _validated_synthesis(value, allowed)
        except EvidenceBindingError as exc:
            repaired = self.client.generate("evidence-bounded biomedical synthesis repair",
                "Repair the previous structured output. Use only allowed evidence IDs in citations and "
                "counterevidence; preserve calibrated claims and return every required field.",
                {"validation_error": str(exc), "previous_output": dict(value),
                 "allowed_evidence_ids": list(allowed),
                 "admitted_evidence": [_evidence_payload(item) for item in evidence]}, schema=schema)
            return _validated_synthesis(repaired, allowed)


class EvidenceBindingError(ValueError):
    pass


def _validated_synthesis(value: Mapping[str, object], allowed_ids: tuple[str, ...]) -> str:
    required = {"source_study_answer", "current_evidence_update", "citations",
                "counterevidence", "gaps", "limitations"}
    _shape(value, required)
    citations = _strings(value["citations"], "citations", allow_empty=True)
    counterevidence = _strings(value["counterevidence"], "counterevidence", allow_empty=True)
    if not set(citations + counterevidence).issubset(allowed_ids):
        raise EvidenceBindingError("synthesis cited evidence outside admitted memory")
    parts = (("Source-study answer", _text(value["source_study_answer"], "source study answer")),
             ("Current-evidence update", _text(value["current_evidence_update"], "current update")),
             ("Citations", ", ".join(citations) or "none"),
             ("Counterevidence", "; ".join(counterevidence) or "none"),
             ("Coverage gaps", "; ".join(_strings(value["gaps"], "gaps", allow_empty=True)) or "none"),
             ("Limitations", "; ".join(_strings(value["limitations"], "limitations", allow_empty=True)) or "none"))
    return "\n\n".join(f"{name}: {text}" for name, text in parts)


def _objects(value: object, name: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{name} must be a list of objects")
    return tuple(value)


def _candidate(item: Mapping[str, object]) -> KnowledgeCandidate:
    required = {"id", "kind", "value", "claim", "verification_query"}
    _shape(item, required, {"pmid", "doi"})
    return KnowledgeCandidate(*(_text(item[key], key) for key in ("id", "kind", "value", "claim", "verification_query")),
                              pmid=str(item.get("pmid") or ""), doi=str(item.get("doi") or ""))


def _claim(item: Mapping[str, object]) -> ReaderClaim:
    keys = ("statement", "locator", "population_or_model", "intervention", "comparator",
            "outcome", "direction", "magnitude")
    _shape(item, set(keys) | {"limitations"})
    return ReaderClaim(*(_text(item[key], key) for key in keys),
                       _strings(item["limitations"], "claim limitations", allow_empty=True))


def _claim_payload(item: ReaderClaim) -> dict[str, object]:
    return {name: getattr(item, name) for name in ("statement", "locator", "population_or_model",
            "intervention", "comparator", "outcome", "direction", "magnitude")}


def _evidence_payload(item: EvidenceExcerpt) -> dict[str, object]:
    return {"id": item.id, "record_id": item.record_id, "claim": item.claim,
            "locator": item.locator, "strength": item.strength.value, "limitations": list(item.limitations)}


def _history(values) -> list[dict[str, object]]:
    result = []
    for item in tuple(values)[-8:]:
        if isinstance(item, Mapping):
            content = item.get("content", "")
            text = content if isinstance(content, str) else ""
            role = item.get("role")
            is_user = role == "user" if role in {"user", "assistant"} else bool(item.get("isUser"))
            result.append({"content": text[:1000], "is_user": is_user})
    return result
