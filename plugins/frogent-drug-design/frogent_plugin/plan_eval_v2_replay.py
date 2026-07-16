"""Deterministic truncation-aware frozen replay and PLAN v2 metrics."""

from datetime import date
from typing import Any, Mapping

from .plan_eval_v2_assets import PlanEvalV2Bundle
from .plan_eval_v2_schema import group_matches, query_group_matches, record_upper_date

QUALITY_METRICS = frozenset({
    "concept_block_coverage", "source_route_coverage", "wave_coverage",
    "anchor_recall", "counterevidence_recall", "retrieval_precision",
    "stop_rule_coverage",
})


def replay_plan(output: Mapping[str, Any], bundle: PlanEvalV2Bundle) -> dict[str, Any]:
    oracle = bundle.oracles[output["case_id"]]
    constraint = bundle.constraints[output["case_id"]]
    findings: list[str] = []
    hits: list[dict[str, Any]] = []
    records: dict[str, Mapping[str, Any]] = {}
    sources = set(output["source_map"])
    query_sources = {query["source"] for query in output["queries"]}
    routes = set(constraint["available_source_routes"])
    if sources != query_sources:
        findings.append("source_route_mismatch")
    if not sources <= routes:
        findings.append("unsupported_source")
    if len(output["queries"]) > constraint["max_query_events"]:
        findings.append("query_budget_exceeded")
    for query in output["queries"]:
        if query["source"] not in sources or query["source"] not in routes:
            findings.append("unsupported_source")
            continue
        for record in _matches(query, output["case_id"], bundle.corpus):
            hits.append(_hit(query, record))
            previous = records.setdefault(record["record_id"], record)
            if previous != record:
                findings.append("conflicting_canonical_record")
    cutoff = date.fromisoformat(output["as_of"])
    if any(record_upper_date(record) > cutoff for record in records.values()):
        findings.append("future_record")
    if any(_future_metadata(record, cutoff) for record in records.values()):
        findings.append("future_metadata")
    findings.extend(replay_provenance_findings(hits, tuple(records.values())))
    return {
        "case_id": output["case_id"], "profile": output["profile"],
        "replicate_label": output["replicate_label"], "plan": output,
        "hits": hits, "records": list(records.values()),
        "scorecard": score_plan(output, oracle, hits, tuple(records.values())),
        "findings": sorted(set(findings)),
    }


def score_plan(output: Mapping[str, Any], oracle: Mapping[str, Any],
               hits: list[Mapping[str, Any]], records: tuple[Mapping[str, Any], ...]) -> dict[str, dict[str, Any]]:
    concepts = [term for block in output["concept_blocks"] for term in block["terms"]]
    record_ids = {record["record_id"] for record in records}
    relevant = set(oracle["relevant_record_ids"])
    by_id = {record["record_id"]: record for record in records}
    cutoff = date.fromisoformat(output["as_of"])
    future_hits = sum(_any_future(by_id[hit["record_id"]], cutoff) for hit in hits)
    relevant_hits = sum(hit["record_id"] in relevant for hit in hits)
    return {
        "concept_block_coverage": _group_ratio(concepts, oracle["required_concept_groups"]),
        "source_route_coverage": _set_ratio({query["source"] for query in output["queries"]}, set(oracle["required_sources"])),
        "wave_coverage": _set_ratio({query["wave"] for query in output["queries"]}, set(oracle["required_waves"])),
        "anchor_recall": _set_ratio(record_ids, set(oracle["anchor_record_ids"])),
        "counterevidence_recall": _set_ratio(record_ids, set(oracle["counterevidence_record_ids"])),
        "retrieval_precision": _ratio(relevant_hits, len(hits), "no query hits"),
        "temporal_violation_rate": _ratio(future_hits, len(hits), "no query hits"),
        "stop_rule_coverage": _group_ratio(output["stop_rules"], oracle["required_stop_groups"]),
    }


def replay_provenance_findings(hits: list[Mapping[str, Any]],
                               records: tuple[Mapping[str, Any], ...]) -> list[str]:
    canonical = {record["record_id"]: record for record in records}
    findings = []
    for hit in hits:
        record = canonical.get(hit["record_id"])
        fields = ("source", "artifact", "published_on", "date_precision")
        if record is None or any(hit[field] != record[field] for field in fields):
            findings.append("hit_record_mismatch")
    hit_ids = {hit["record_id"] for hit in hits}
    if any(record["record_id"] not in hit_ids for record in records):
        findings.append("orphan_canonical_record")
    return sorted(set(findings))


def _matches(query: Mapping[str, Any], case_id: str,
             corpus: tuple[Mapping[str, Any], ...]) -> tuple[Mapping[str, Any], ...]:
    matched = []
    for record in corpus:
        if record["case_id"] != case_id or record["source"] != query["source"]:
            continue
        identifier_hit = any(_exact_locator(query["query"], value) for value in record["identifiers"].values())
        lexical_hit = all(query_group_matches(query["query"], group) for group in record["match_groups"])
        if identifier_hit or lexical_hit:
            matched.append(record)
    return tuple(matched)


def _hit(query: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, Any]:
    return {"query_id": query["query_id"], "source": query["source"], "wave": query["wave"],
            "query": query["query"], "record_id": record["record_id"], "artifact": record["artifact"],
            "published_on": record["published_on"], "date_precision": record["date_precision"]}


def _group_ratio(candidates: list[str], groups: list[Mapping[str, Any]]) -> dict[str, Any]:
    matched = [group["requirement_id"] for group in groups if group_matches(candidates, group["aliases"])]
    result = _ratio(len(matched), len(groups), "oracle requirement groups are empty")
    result["matched_requirement_ids"] = matched
    return result


def _set_ratio(actual: set[str], required: set[str]) -> dict[str, Any]:
    return _ratio(len(actual & required), len(required), "oracle requirement set is empty")


def _ratio(numerator: int, denominator: int, reason: str) -> dict[str, Any]:
    if denominator == 0:
        return {"state": "not_applicable", "reason": reason}
    return {"state": "measured", "numerator": numerator, "denominator": denominator,
            "value": numerator / denominator}


def _exact_locator(query: str, locator: str) -> bool:
    from .plan_eval_schema import normalize_lexical
    query_text, normalized = normalize_lexical(query), normalize_lexical(locator)
    return query_text == normalized or f" {normalized} " in f" {query_text} "


def _future_metadata(record: Mapping[str, Any], cutoff: date) -> bool:
    if record["online_on"] is not None and date.fromisoformat(record["online_on"]) > cutoff:
        return True
    return any(_event_upper(value) > cutoff for value in record["event_dates"].values())


def _event_upper(value: Mapping[str, Any]) -> date:
    return record_upper_date({"published_on": value["date"], "date_precision": value["precision"]})


def _any_future(record: Mapping[str, Any], cutoff: date) -> bool:
    return record_upper_date(record) > cutoff or _future_metadata(record, cutoff)
