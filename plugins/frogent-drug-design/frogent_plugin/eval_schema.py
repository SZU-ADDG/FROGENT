"""Strict semantic helpers for exposed research eval JSON."""

from datetime import date
from typing import Any, Mapping

LEAK_KEYS = ("oracle", "gold", "expected", "answer")
ID_LIST_FIELDS = (
    "relevant_record_ids", "anchor_record_ids", "counterevidence_record_ids",
    "admissible_evidence_ids", "revoked_evidence_ids",
)
OUTPUT_ID_FIELDS = (
    "qualified_evidence_ids", "admitted_evidence_ids", "memory_evidence_ids",
    "revoked_evidence_ids", "surfaced_gaps",
)


def validate_case(item: Mapping[str, Any]) -> None:
    for field in ID_LIST_FIELDS + ("required_evidence_gaps", "acceptable_stop_reasons"):
        string_list(item[field], field)
    relevant = set(item["relevant_record_ids"])
    admissible = set(item["admissible_evidence_ids"])
    revoked = set(item["revoked_evidence_ids"])
    if admissible & revoked:
        raise ValueError("admissible and revoked evidence must be disjoint")
    if not set(item["anchor_record_ids"] + item["counterevidence_record_ids"]) <= relevant:
        raise ValueError("anchor and counterevidence records must be relevant")
    provenance_ids = []
    for entry in item["evidence_provenance"]:
        exact(entry, frozenset({"evidence_id", "record_id", "artifact"}), "evidence provenance")
        for field in ("evidence_id", "record_id", "artifact"):
            text(entry[field], field)
        provenance_ids.append(entry["evidence_id"])
    unique(provenance_ids, "evidence provenance IDs")
    if any(entry["record_id"] not in relevant for entry in item["evidence_provenance"]):
        raise ValueError("evidence provenance record must be relevant")
    if not set(item["admissible_evidence_ids"] + item["revoked_evidence_ids"]) <= set(provenance_ids):
        raise ValueError("oracle evidence IDs require evaluator provenance")
    claim_ids = []
    cited_ids: set[str] = set()
    for link in item["claim_links"]:
        exact(link, frozenset({"claim_id", "evidence_ids", "counterevidence_ids"}), "claim link")
        claim_ids.append(text(link["claim_id"], "claim_id"))
        string_list(link["evidence_ids"], "claim evidence IDs")
        string_list(link["counterevidence_ids"], "claim counterevidence IDs")
        cited_ids.update(link["evidence_ids"] + link["counterevidence_ids"])
    unique(claim_ids, "claim link IDs")
    if not cited_ids <= admissible:
        raise ValueError("claim link evidence must be admissible")


def validate_output(item: Mapping[str, Any]) -> None:
    if item["execution_status"] not in {"completed", "failed", "partial"}:
        raise ValueError("invalid execution_status")
    for field in OUTPUT_ID_FIELDS:
        string_list(item[field], field)
    text(item["stop_reason"], "stop_reason")
    record_ids: list[str] = []
    for entry in item["retrieved_hits"] + item["records"]:
        for field in ("record_id", "source", "query", "artifact", "published_on"):
            text(entry[field], field)
        date.fromisoformat(entry["published_on"])
    for record in item["records"]:
        record_ids.append(record["record_id"])
    unique(record_ids, "canonical record IDs")
    lineage_ids = []
    for lineage in item["evidence_lineage"]:
        lineage_ids.append(text(lineage["evidence_id"], "evidence_id"))
        text(lineage["record_id"], "record_id")
        text(lineage["artifact"], "artifact")
    unique(lineage_ids, "evidence lineage IDs")
    claim_ids = []
    for claim in item["claims"]:
        claim_ids.append(text(claim["claim_id"], "claim_id"))
        string_list(claim["evidence_ids"], "claim evidence IDs")
        string_list(claim["counterevidence_ids"], "claim counterevidence IDs")
    unique(claim_ids, "output claim IDs")


def exact(value: Any, fields: frozenset[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields must match schema exactly")


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value


def string_list(value: Any, label: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} must be a list of non-empty strings")
    unique(value, label)


def unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def has_leakage(value: Any) -> bool:
    if isinstance(value, dict):
        if any(any(token in str(key).lower() for token in LEAK_KEYS) for key in value):
            return True
        return any(has_leakage(item) for item in value.values())
    if isinstance(value, list):
        return any(has_leakage(item) for item in value)
    return False
