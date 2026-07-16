"""Strict candidate schema and query-only truncation semantics for PLAN v2."""

import re
from datetime import date
from typing import Any, Mapping

from .eval_schema import exact, text, unique
from .plan_eval_schema import (
    CLAIM_LIMITS, METRICS, PRIMARY_METRICS, PROFILES, REPLICATES, SENSITIVE_KEYS,
    WAVES, group_matches, normalize_lexical, record_upper_date, string_list,
)

OUTPUT_FIELDS = frozenset({
    "case_id", "profile", "replicate_label", "worker_input_digest",
    "execution_status", "question_frame", "as_of", "source_map",
    "concept_blocks", "queries", "inclusion_criteria", "exclusion_criteria",
    "stop_rules", "coverage_gaps",
})
CONSTRAINT_FIELDS = frozenset({"case_id", "available_source_routes", "max_query_events"})


def validate_plan_output(value: Any, bundle: Any) -> Mapping[str, Any]:
    if bundle.manifest["pack_status"] != "locked":
        raise ValueError("plan v2 preregistration is pending")
    if _has_leakage(value):
        raise ValueError("plan output contains sensitive evaluator key")
    exact(value, OUTPUT_FIELDS, "plan v2 output")
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
    constraint = bundle.constraints.get(value["case_id"])
    if case is None or constraint is None or case["as_of"] != value["as_of"]:
        raise ValueError("plan output case or as_of does not match preregistration")
    from .plan_eval_v2_assets import worker_input_digest
    expected = worker_input_digest(bundle, value["case_id"], value["profile"], value["replicate_label"])
    if value["worker_input_digest"] != expected:
        raise ValueError("worker input identity mismatch")
    return value


def query_group_matches(query: str, aliases: list[str]) -> bool:
    tokens = _query_tokens(query)
    return any(_query_alias_match(tokens, normalize_lexical(alias).split()) for alias in aliases)


def _query_tokens(value: str) -> list[str]:
    normalized = normalize_lexical(value)
    positive, negated = [], False
    for token in normalized.split():
        if token == "not":
            negated = True
            continue
        if token == "and":
            negated = False
            continue
        if token == "or":
            continue
        if not negated:
            positive.append(token)
    return positive


def _query_alias_match(tokens: list[str], alias: list[str]) -> bool:
    if not alias or len(alias) > len(tokens):
        return False
    for index in range(len(tokens) - len(alias) + 1):
        if all(_token_match(candidate, expected) for candidate, expected in zip(tokens[index:], alias)):
            return True
    return False


def _token_match(candidate: str, expected: str) -> bool:
    if "*" not in candidate:
        return candidate == expected
    if candidate.count("*") != 1 or not candidate.endswith("*"):
        return False
    stem = candidate[:-1]
    return bool(stem) and expected.startswith(stem)


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
