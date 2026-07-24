"""Auditable research effect metrics with explicit missing-value states."""

from datetime import date
from typing import Any, Mapping

from agent.evaluation.eval_integrity import traceable_evidence
from agent.evaluation.eval_manifest import SUPPORTED_METRICS

METRICS = tuple(sorted(SUPPORTED_METRICS))
LOWER_IS_BETTER = frozenset(
    {
        "temporal_violation_rate", "raw_memory_contamination_rate",
        "cross_case_leakage_rate", "unsupported_claim_rate",
    }
)


def measured(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "status": "measured", "value": round(numerator / denominator, 12),
        "numerator": numerator, "denominator": denominator,
    }


def unavailable(status: str, reason: str) -> dict[str, str]:
    if status not in {"not_applicable", "not_measured", "not_comparable"}:
        raise ValueError("invalid metric status")
    return {"status": status, "reason": reason}


def score_case(
    case: Mapping[str, Any], output: Mapping[str, Any], foreign_evidence_ids: set[str]
) -> dict[str, Mapping[str, Any]]:
    retrieved = {item["record_id"] for item in output["retrieved_hits"]}
    anchors = set(case["anchor_record_ids"])
    counters = set(case["counterevidence_record_ids"])
    relevant = set(case["relevant_record_ids"])
    admissible = set(case["admissible_evidence_ids"])
    admitted = set(output["admitted_evidence_ids"])
    qualified = set(output["qualified_evidence_ids"])
    memory = set(output["memory_evidence_ids"])
    traceable = traceable_evidence(case, output)
    valid_memory = memory & admitted & qualified & traceable
    revoked_oracle = set(case["revoked_evidence_ids"])
    revoked_output = set(output["revoked_evidence_ids"])
    return {
        "anchor_recall": _recall(retrieved, anchors, "no_anchor_oracle"),
        "counterevidence_recall": _recall(retrieved, counters, "no_counterevidence_oracle"),
        "retrieval_precision": _precision(retrieved, relevant, "no_retrieved_records"),
        "provenance_completeness": _provenance(output),
        "temporal_violation_rate": _temporal(output, case["as_of"]),
        "admission_precision": _precision(admitted, admissible, "no_admitted_evidence"),
        "useful_evidence_recall": _recall(valid_memory, admissible, "no_admissible_evidence_oracle"),
        "raw_memory_contamination_rate": _ratio(
            len(memory - valid_memory), len(memory), "no_working_memory"
        ),
        "revocation_accuracy": _ratio(
            len({item for item in revoked_oracle if item in revoked_output and item not in memory})
            + len(admissible - revoked_output),
            len(revoked_oracle | admissible), "empty_evidence_classification_oracle",
        ),
        "cross_case_leakage_rate": _ratio(
            len(memory & foreign_evidence_ids), len(memory), "no_working_memory"
        ),
        "citation_precision": _citation_precision(case, output, valid_memory),
        "unsupported_claim_rate": _unsupported(case, output, valid_memory),
        "counterevidence_retention": _counter_retention(case, output, valid_memory),
        "evidence_gap_visibility": _recall(
            set(output["surfaced_gaps"]), set(case["required_evidence_gaps"]),
            "no_required_gap_oracle",
        ),
        "stop_correctness": measured(
            int(output["stop_reason"] in case["acceptable_stop_reasons"]), 1
        ),
    }


def macro_score(
    scorecards: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> dict[str, Mapping[str, Any]]:
    result = {}
    total = len(scorecards)
    for metric in METRICS:
        measured_ids = sorted(case_id for case_id, card in scorecards.items() if card[metric]["status"] == "measured")
        items = [scorecards[case_id][metric] for case_id in measured_ids]
        if items:
            result[metric] = {
                "status": "measured",
                "value": round(sum(item["value"] for item in items) / len(items), 12),
                "measured_case_count": len(items), "total_case_count": total,
                "measured_case_ids": measured_ids,
            }
        else:
            result[metric] = unavailable("not_measured", "no_measured_cases")
    return result


def _precision(found: set[str], relevant: set[str], reason: str) -> Mapping[str, Any]:
    return _ratio(len(found & relevant), len(found), reason)


def _recall(found: set[str], relevant: set[str], reason: str) -> Mapping[str, Any]:
    return _ratio(len(found & relevant), len(relevant), reason)


def _ratio(numerator: int, denominator: int, reason: str) -> Mapping[str, Any]:
    return measured(numerator, denominator) if denominator else unavailable("not_applicable", reason)


def _provenance(output: Mapping[str, Any]) -> Mapping[str, Any]:
    records = {item["record_id"]: item for item in output["records"]}
    complete = 0
    for hit in output["retrieved_hits"]:
        record = records.get(hit["record_id"])
        complete += int(
            record is not None
            and all(hit[field] == record[field] for field in ("source", "artifact", "published_on"))
        )
    return _ratio(complete, len(output["retrieved_hits"]), "no_retrieved_hits")


def _temporal(output: Mapping[str, Any], as_of: str) -> Mapping[str, Any]:
    entries = output["retrieved_hits"] + output["records"]
    cutoff = date.fromisoformat(as_of)
    future = sum(date.fromisoformat(item["published_on"]) > cutoff for item in entries)
    return _ratio(future, len(entries), "no_retrieval_provenance")


def _links(case: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {item["claim_id"]: item for item in case["claim_links"]}


def _citation_precision(
    case: Mapping[str, Any], output: Mapping[str, Any], valid: set[str]
) -> Mapping[str, Any]:
    expected = _links(case)
    if not expected:
        return unavailable("not_measured", "no_claim_link_oracle")
    correct = total = 0
    for claim in output["claims"]:
        cited = set(claim["evidence_ids"] + claim["counterevidence_ids"])
        target = expected.get(claim["claim_id"])
        allowed = set(target["evidence_ids"] + target["counterevidence_ids"]) & valid if target else set()
        correct += len(cited & allowed)
        total += len(cited)
    return _ratio(correct, total, "no_candidate_citations")


def _unsupported(
    case: Mapping[str, Any], output: Mapping[str, Any], valid: set[str]
) -> Mapping[str, Any]:
    expected = _links(case)
    if not expected:
        return unavailable("not_measured", "no_claim_link_oracle")
    claims = {item["claim_id"]: item for item in output["claims"]}
    claim_ids = set(expected) | set(claims)
    bad = 0
    for claim_id in claim_ids:
        claim, target = claims.get(claim_id), expected.get(claim_id)
        cited = set(claim["evidence_ids"] + claim["counterevidence_ids"]) if claim else set()
        allowed = set(target["evidence_ids"] + target["counterevidence_ids"]) & valid if target else set()
        bad += int(not cited or not cited <= allowed)
    return measured(bad, len(claim_ids))


def _counter_retention(
    case: Mapping[str, Any], output: Mapping[str, Any], valid: set[str]
) -> Mapping[str, Any]:
    expected = _links(case)
    required = {(key, item) for key, link in expected.items() for item in link["counterevidence_ids"]}
    found = {(claim["claim_id"], item) for claim in output["claims"] for item in claim["counterevidence_ids"] if item in valid}
    return _ratio(len(required & found), len(required), "no_counterevidence_claim_oracle")
