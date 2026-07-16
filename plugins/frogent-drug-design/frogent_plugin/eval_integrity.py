"""Lineage and consistency checks for research eval candidate outputs."""

from datetime import date
from typing import Any, Mapping


def analyze_case(case: Mapping[str, Any], output: Mapping[str, Any]) -> tuple[str, ...]:
    failures: set[str] = set()
    records = {item["record_id"]: item for item in output["records"]}
    hit_ids = {item["record_id"] for item in output["retrieved_hits"]}
    if (
        any(not _hit_matches(hit, records.get(hit["record_id"])) for hit in output["retrieved_hits"])
        or not set(records) <= hit_ids
    ):
        failures.add("retrieval_record_mismatch")
    traceable = traceable_evidence(case, output)
    qualified = set(output["qualified_evidence_ids"])
    admitted = set(output["admitted_evidence_ids"])
    memory = set(output["memory_evidence_ids"])
    if not memory <= admitted <= qualified <= traceable:
        failures.add("evidence_lineage_break")
    cited = {
        item for claim in output["claims"]
        for item in claim["evidence_ids"] + claim["counterevidence_ids"]
    }
    if not cited <= (memory & admitted & qualified & traceable):
        failures.add("claim_lineage_break")
    required_claims = {item["claim_id"] for item in case["claim_links"]}
    if not required_claims <= {item["claim_id"] for item in output["claims"]}:
        failures.add("missing_required_claim")
    oracle_revoked = set(case["revoked_evidence_ids"])
    declared_revoked = set(output["revoked_evidence_ids"])
    if not oracle_revoked <= declared_revoked or oracle_revoked & memory:
        failures.add("revocation_failure")
    if _has_future(case["as_of"], output["retrieved_hits"] + output["records"]):
        failures.add("future_record")
    return tuple(sorted(failures))


def traceable_evidence(case: Mapping[str, Any], output: Mapping[str, Any]) -> set[str]:
    records = {item["record_id"]: item for item in output["records"]}
    retrieved = {item["record_id"] for item in output["retrieved_hits"]}
    oracle = {item["evidence_id"]: item for item in case["evidence_provenance"]}
    return {
        item["evidence_id"] for item in output["evidence_lineage"]
        if item["evidence_id"] in oracle
        and item["record_id"] == oracle[item["evidence_id"]]["record_id"]
        and item["artifact"] == oracle[item["evidence_id"]]["artifact"]
        if item["record_id"] in retrieved
        and item["record_id"] in records
        and item["artifact"] == records[item["record_id"]]["artifact"]
    }


def _hit_matches(hit: Mapping[str, Any], record: Mapping[str, Any] | None) -> bool:
    if record is None:
        return False
    return all(hit[field] == record[field] for field in ("source", "artifact", "published_on"))


def _has_future(as_of: str, entries: list[Mapping[str, Any]]) -> bool:
    cutoff = date.fromisoformat(as_of)
    return any(date.fromisoformat(item["published_on"]) > cutoff for item in entries)
