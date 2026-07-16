"""Strict candidate-output and lexical schemas for PLAN forward evaluation."""

import re
import unicodedata
from calendar import monthrange
from datetime import date
from typing import Any, Mapping

from .eval_schema import exact, text, unique

PROFILES = ("no_skill", "single_skill")
REPLICATES = ("17", "29", "43")
WAVES = ("sentinel", "discovery", "confirmation", "expansion", "challenge", "update")
METRICS = (
    "concept_block_coverage", "source_route_coverage", "wave_coverage",
    "anchor_recall", "counterevidence_recall", "retrieval_precision",
    "temporal_violation_rate", "stop_rule_coverage",
)
PRIMARY_METRICS = ("anchor_recall", "counterevidence_recall", "retrieval_precision")
CLAIM_LIMITS = ("exposed_development_panel", "seed_control_unverified",
                "candidate_reference_filesystem_isolation_not_established",
                "independent_score_owner_not_established",
                "model_runtime_provider_memory_identity_closure_incomplete")
SENSITIVE_KEYS = ("oracle", "gold", "expected", "answer",
                  "relevant_record_ids", "match_rules")
OUTPUT_FIELDS = frozenset({
    "case_id", "profile", "replicate_label", "worker_input_digest",
    "execution_status", "question_frame", "as_of", "source_map",
    "concept_blocks", "queries", "inclusion_criteria", "exclusion_criteria",
    "stop_rules", "coverage_gaps",
})
CASE_FIELDS = frozenset({"case_id", "task", "as_of"})
ORACLE_FIELDS = frozenset({
    "case_id", "required_concept_groups", "required_sources", "required_waves",
    "anchor_record_ids", "counterevidence_record_ids", "relevant_record_ids",
    "required_stop_groups", "max_query_events",
})
RECORD_FIELDS = frozenset({
    "case_id", "record_id", "title", "identifiers", "source", "published_on",
    "date_precision", "online_on", "event_dates", "artifact", "relevance_class",
    "match_groups",
})


def validate_plan_output(value: Any, bundle: Any) -> Mapping[str, Any]:
    if bundle.manifest["pack_status"] != "locked":
        raise ValueError("plan preregistration is pending evaluator assets")
    if _has_leakage(value):
        raise ValueError("plan output contains sensitive evaluator key")
    exact(value, OUTPUT_FIELDS, "plan output")
    for field in ("case_id", "question_frame"):
        text(value[field], field)
    if value["profile"] not in PROFILES or value["replicate_label"] not in REPLICATES:
        raise ValueError("plan output profile or replicate is invalid")
    if value["execution_status"] not in {"completed", "failed"}:
        raise ValueError("plan output execution_status is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", value["worker_input_digest"]):
        raise ValueError("worker_input_digest must be lowercase SHA-256")
    date.fromisoformat(text(value["as_of"], "as_of"))
    for field in ("source_map", "inclusion_criteria", "exclusion_criteria", "stop_rules"):
        string_list(value[field], field)
    string_list(value["coverage_gaps"], "coverage_gaps", allow_empty=True)
    _validate_concepts(value["concept_blocks"])
    _validate_queries(value["queries"])
    case = next((item for item in bundle.cases if item["case_id"] == value["case_id"]), None)
    if case is None or case["as_of"] != value["as_of"]:
        raise ValueError("plan output case or as_of does not match preregistration")
    from .plan_eval_assets import worker_input_digest
    expected = worker_input_digest(bundle, value["case_id"], value["profile"], value["replicate_label"])
    if value["worker_input_digest"] != expected:
        raise ValueError("worker input identity mismatch")
    return value


def normalize_lexical(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.replace("α", "alpha")
    normalized = re.sub(r"[-/,()\[\]{}:'\"]", " ", normalized)
    return " ".join(normalized.split())


def group_matches(candidate_values: list[str], aliases: list[str]) -> bool:
    candidates = [normalize_lexical(item) for item in candidate_values]
    normalized_aliases = [normalize_lexical(alias) for alias in aliases]
    return any(_phrase_in(candidate, alias) for candidate in candidates for alias in normalized_aliases)


def record_upper_date(record: Mapping[str, Any]) -> date:
    if record["date_precision"] == "day":
        return date.fromisoformat(record["published_on"])
    year, month = (int(part) for part in record["published_on"].split("-"))
    return date(year, month, monthrange(year, month)[1])


def validate_groups(value: Any, label: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty list")
    ids = []
    for item in value:
        exact(item, frozenset({"requirement_id", "aliases"}), label)
        ids.append(text(item["requirement_id"], "requirement_id"))
        string_list(item["aliases"], "aliases")
        normalized = [normalize_lexical(alias) for alias in item["aliases"]]
        unique(normalized, "normalized aliases")
    unique(ids, f"{label} IDs")


def string_list(value: Any, label: str, allow_empty: bool = False) -> None:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ValueError(f"{label} must be a list of non-empty strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} must be a list of non-empty strings")
    unique(value, label)


def _validate_concepts(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError("concept_blocks must be a non-empty list")
    for item in value:
        exact(item, frozenset({"block_id", "terms"}), "concept block")
        text(item["block_id"], "block_id")
        string_list(item["terms"], "concept terms")
    unique([item["block_id"] for item in value], "concept block IDs")


def _validate_queries(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError("queries must be a non-empty list")
    for item in value:
        exact(item, frozenset({"query_id", "source", "wave", "query", "purpose"}), "exact query")
        for field in ("query_id", "source", "query", "purpose"):
            text(item[field], field)
        if item["wave"] not in WAVES:
            raise ValueError("query wave is invalid")
    unique([item["query_id"] for item in value], "query IDs")


def _has_leakage(value: Any) -> bool:
    if isinstance(value, dict):
        if any(any(token in str(key).lower() for token in SENSITIVE_KEYS) for key in value):
            return True
        return any(_has_leakage(item) for item in value.values())
    return isinstance(value, list) and any(_has_leakage(item) for item in value)


def _phrase_in(candidate: str, phrase: str) -> bool:
    return candidate == phrase or f" {phrase} " in f" {candidate} "
