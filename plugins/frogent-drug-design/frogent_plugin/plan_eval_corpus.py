"""Strict evaluator-owned PLAN task, oracle, and corpus validation."""

from datetime import date
from typing import Any, Mapping

from .eval_schema import exact, text, unique
from .plan_eval_schema import (
    CASE_FIELDS, ORACLE_FIELDS, RECORD_FIELDS, WAVES, string_list, validate_groups,
)


def validate_corpus_assets(
    task_value: Any, oracle_value: Any, corpus_value: Any,
) -> tuple[tuple[Mapping[str, Any], ...], dict[str, Mapping[str, Any]], tuple[Mapping[str, Any], ...]]:
    cases = _validate_cases(task_value)
    oracles = _validate_oracles(oracle_value, cases)
    corpus = _validate_corpus(corpus_value)
    _validate_alignment(cases, oracles, corpus)
    return cases, oracles, corpus


def _validate_cases(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list) or len(value) != 2 or {item.get("case_id") for item in value} != {"PLAN-01", "PLAN-02"}:
        raise ValueError("candidate tasks must contain PLAN-01 and PLAN-02 exactly")
    for item in value:
        exact(item, CASE_FIELDS, "candidate task")
        text(item["task"], "task")
        date.fromisoformat(text(item["as_of"], "as_of"))
    return tuple(value)


def _validate_oracles(value: Any, cases: tuple[Mapping[str, Any], ...]) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, list) or len(value) != 2 or {item.get("case_id") for item in value} != {item["case_id"] for item in cases}:
        raise ValueError("evaluator oracle case coverage mismatch")
    result = {}
    for item in value:
        exact(item, ORACLE_FIELDS, "plan oracle")
        validate_groups(item["required_concept_groups"], "concept requirement")
        validate_groups(item["required_stop_groups"], "stop requirement")
        if not isinstance(item["max_query_events"], int) or item["max_query_events"] < 1:
            raise ValueError("max_query_events must be a positive integer")
        for field in ("required_sources", "required_waves", "anchor_record_ids",
                      "counterevidence_record_ids", "relevant_record_ids"):
            string_list(item[field], field)
        if not set(item["required_waves"]) <= set(WAVES):
            raise ValueError("oracle contains unknown wave")
        result[item["case_id"]] = item
    return result


def _validate_corpus(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("frozen corpus must be non-empty")
    ids = []
    by_case: dict[str, list[Mapping[str, Any]]] = {"PLAN-01": [], "PLAN-02": []}
    for item in value:
        exact(item, RECORD_FIELDS, "frozen record")
        if item["case_id"] not in by_case:
            raise ValueError("frozen record case_id is invalid")
        for field in ("record_id", "title", "source", "artifact"):
            text(item[field], field)
        ids.append(item["record_id"])
        _validate_record_metadata(item)
        by_case[item["case_id"]].append(item)
    unique(ids, "frozen record IDs")
    for records in by_case.values():
        classes = {item["relevance_class"] for item in records}
        if not {"anchor", "counterevidence", "irrelevant"} <= classes:
            raise ValueError("each case corpus requires anchor counterevidence and irrelevant")
    return tuple(value)


def _validate_record_metadata(item: Mapping[str, Any]) -> None:
    if item["relevance_class"] not in {"anchor", "counterevidence", "relevant", "irrelevant"}:
        raise ValueError("frozen record relevance_class is invalid")
    _validate_partial_date(item["published_on"], item["date_precision"])
    if item["online_on"] is not None:
        date.fromisoformat(text(item["online_on"], "online_on"))
    if not isinstance(item["event_dates"], dict):
        raise ValueError("event_dates must be a mapping")
    for name, event in item["event_dates"].items():
        text(name, "event date name")
        exact(event, frozenset({"date", "precision"}), "event date")
        _validate_partial_date(event["date"], event["precision"])
    if not isinstance(item["identifiers"], dict) or not item["identifiers"]:
        raise ValueError("record identifiers must be a non-empty mapping")
    for key, value in item["identifiers"].items():
        text(key, "identifier type")
        text(value, "identifier")
    if not isinstance(item["match_groups"], list) or not item["match_groups"]:
        raise ValueError("match_groups must be non-empty")
    for group in item["match_groups"]:
        string_list(group, "match group")
    unique(["\0".join(group) for group in item["match_groups"]], "match groups")


def _validate_partial_date(value: Any, precision: Any) -> None:
    if precision == "day":
        date.fromisoformat(text(value, "date"))
        return
    if precision != "month" or not _fullmonth(value):
        raise ValueError("date differs from precision")


def _validate_alignment(
    cases: tuple[Mapping[str, Any], ...], oracles: Mapping[str, Mapping[str, Any]],
    corpus: tuple[Mapping[str, Any], ...],
) -> None:
    tasks = {item["case_id"]: item["task"].casefold() for item in cases}
    for case_id, oracle in oracles.items():
        records = {item["record_id"]: item for item in corpus if item["case_id"] == case_id}
        expected = {key for key, item in records.items() if item["relevance_class"] != "irrelevant"}
        if set(oracle["relevant_record_ids"]) != expected:
            raise ValueError("oracle relevant IDs differ from case corpus classes")
        for field, label in (("anchor_record_ids", "anchor"),
                             ("counterevidence_record_ids", "counterevidence")):
            class_ids = {key for key, item in records.items() if item["relevance_class"] == label}
            if set(oracle[field]) != class_ids:
                raise ValueError("oracle record class or case lineage mismatch")
        if not set(oracle["required_sources"]) <= {item["source"] for item in records.values()}:
            raise ValueError("oracle source route is absent from case corpus")
        protected = set(records)
        protected.update(value for item in records.values() for value in item["identifiers"].values())
        if any(value.casefold() in tasks[case_id] for value in protected):
            raise ValueError("candidate task leaks evaluator-owned identifier")


def _fullmonth(value: Any) -> bool:
    try:
        year, month = (int(part) for part in str(value).split("-"))
        return 1 <= month <= 12 and year >= 1 and len(str(value)) == 7
    except (TypeError, ValueError):
        return False
