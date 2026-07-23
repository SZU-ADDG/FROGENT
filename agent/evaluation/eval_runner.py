"""Replay, compare, diagnose, and gate research effect fixtures."""

from typing import Any, Mapping

from agent.evaluation.eval_integrity import analyze_case
from agent.evaluation.eval_manifest import EvalBundle, content_digest
from agent.evaluation.eval_metrics import LOWER_IS_BETTER, METRICS, macro_score, score_case, unavailable

ZERO_TOLERANCE = frozenset(
    {
        "temporal_violation_rate", "raw_memory_contamination_rate",
        "cross_case_leakage_rate", "unsupported_claim_rate",
    }
)


def evaluate_bundle(bundle: EvalBundle) -> dict[str, Any]:
    cases = {item["case_id"]: item for item in bundle.cases}
    baseline = {item["case_id"]: item for item in bundle.baseline}
    candidate = {item["case_id"]: item for item in bundle.candidate}
    coverage_equal = set(cases) == set(baseline) == set(candidate)
    baseline_cards = _scorecards(cases, baseline) if set(cases) == set(baseline) else {}
    candidate_cards = _scorecards(cases, candidate) if set(cases) == set(candidate) else {}
    baseline_macro = macro_score(baseline_cards) if baseline_cards else _unmeasured()
    candidate_macro = macro_score(candidate_cards) if candidate_cards else _unmeasured()
    deltas = _deltas(baseline_macro, candidate_macro, coverage_equal)
    findings = _findings(bundle, cases, candidate, candidate_cards, candidate_macro, deltas, coverage_equal)
    failed_cases = _failed_cases(cases, candidate, candidate_cards)
    result = {
        "eval_id": bundle.manifest["eval_id"],
        "schema_version": bundle.manifest["schema_version"],
        "authority_scope": "evaluator_fixture",
        "execution_completion": "completed",
        "effect_outcome": "not_evaluated",
        "promotion_eligible": False,
        "baseline_scorecard": {"per_case": baseline_cards, "macro": baseline_macro},
        "candidate_scorecard": {"per_case": candidate_cards, "macro": candidate_macro},
        "metric_deltas": deltas,
        "failed_cases": failed_cases,
        "hard_gate_findings": findings,
        "claim_limits": {
            "preregistration_authority": "no_independent_score_owner_root",
            "filesystem_isolation": "candidate_reference_isolation_not_established",
            "dependency_identity": "candidate_model_runtime_provider_memory_closure_not_fully_bound",
            "digest_authority": "self_contained_package_consistency_only",
            "leakage_control": "sensitive_key_rejection_is_negative_control_only",
        },
        "replay_identity": {
            "manifest_digest": content_digest(bundle.manifest),
            "asset_digests": dict(bundle.asset_digests),
            "evaluator_version": "research-eval-kernel-1",
        },
    }
    result["canonical_result_digest"] = content_digest(result)
    return result


def verify_result(result: Mapping[str, Any], require_promotion: bool = False) -> None:
    payload = dict(result)
    digest = payload.pop("canonical_result_digest", None)
    if digest != content_digest(payload):
        raise ValueError("canonical result digest mismatch")
    if result.get("execution_completion") != "completed":
        raise ValueError("eval execution did not complete")
    if require_promotion and not result.get("promotion_eligible"):
        raise ValueError("candidate is not promotion eligible")


def _scorecards(
    cases: Mapping[str, Mapping[str, Any]],
    outputs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Mapping[str, Mapping[str, Any]]]:
    evidence_by_case = {
        case_id: set(case["admissible_evidence_ids"] + case["revoked_evidence_ids"])
        for case_id, case in cases.items()
    }
    cards = {}
    for case_id, case in sorted(cases.items()):
        foreign = set().union(*(ids for key, ids in evidence_by_case.items() if key != case_id))
        cards[case_id] = score_case(case, outputs[case_id], foreign)
    return cards


def _deltas(
    baseline: Mapping[str, Mapping[str, Any]],
    candidate: Mapping[str, Mapping[str, Any]],
    comparable: bool,
) -> dict[str, Mapping[str, Any]]:
    return {
        metric: _delta(metric, baseline[metric], candidate[metric], comparable)
        for metric in METRICS
    }


def _delta(
    metric: str, left: Mapping[str, Any], right: Mapping[str, Any], comparable: bool
) -> Mapping[str, Any]:
    if not comparable:
        return unavailable("not_comparable", "case_coverage_mismatch")
    if left.get("measured_case_ids") != right.get("measured_case_ids"):
        return unavailable("not_comparable", "metric_measured_case_coverage_mismatch")
    if left["status"] == right["status"] == "measured":
        raw = right["value"] - left["value"]
        improvement = -raw if metric in LOWER_IS_BETTER else raw
        return {
            "status": "measured", "delta": round(raw, 12),
            "improvement": round(improvement, 12),
        }
    status = "not_applicable" if left["status"] == right["status"] == "not_applicable" else "not_measured"
    return unavailable(status, "baseline_candidate_metric_state_mismatch")


def _findings(
    bundle: EvalBundle,
    cases: Mapping[str, Mapping[str, Any]],
    outputs: Mapping[str, Mapping[str, Any]],
    cards: Mapping[str, Mapping[str, Mapping[str, Any]]],
    macro: Mapping[str, Mapping[str, Any]],
    deltas: Mapping[str, Mapping[str, Any]],
    coverage_equal: bool,
) -> list[Mapping[str, Any]]:
    findings: list[Mapping[str, Any]] = []
    if not coverage_equal:
        findings.append({"code": "case_coverage_mismatch"})
    mismatched = sorted(name for name, item in deltas.items() if item["status"] == "not_comparable")
    if mismatched:
        findings.append({"code": "metric_coverage_mismatch", "metrics": mismatched})
    for metric in ZERO_TOLERANCE:
        item = macro[metric]
        if item["status"] == "measured" and item["value"] > 0:
            findings.append({"code": "zero_tolerance_violation", "metric": metric})
    _append_case_findings(findings, cases, outputs, cards)
    primary = [deltas[name] for name in bundle.manifest["primary_metrics"]]
    measured_primary = [item for item in primary if item["status"] == "measured"]
    if len(measured_primary) != len(primary):
        findings.append({"code": "primary_metric_unmeasured_or_not_comparable"})
    if not measured_primary or not any(item["improvement"] > 0 for item in measured_primary):
        findings.append({"code": "no_primary_improvement"})
    if any(item["improvement"] < 0 for item in measured_primary):
        findings.append({"code": "primary_metric_regression"})
    if any(item["status"] == "measured" and item["improvement"] < 0 for item in deltas.values()):
        findings.append({"code": "measured_metric_regression"})
    findings.append({"code": "fixture_authority_blocks_promotion"})
    return findings


def _append_case_findings(
    findings: list[Mapping[str, Any]],
    cases: Mapping[str, Mapping[str, Any]],
    outputs: Mapping[str, Mapping[str, Any]],
    cards: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> None:
    for case_id, output in outputs.items():
        if case_id not in cases:
            findings.append({"code": "unexpected_case_output", "case_id": case_id})
            continue
        if output["execution_status"] != "completed":
            findings.append({"code": "case_execution_incomplete", "case_id": case_id})
        card = cards.get(case_id, {})
        if _nonzero(card.get("temporal_violation_rate")):
            findings.append({"code": "future_record", "case_id": case_id})
        if _nonzero(card.get("raw_memory_contamination_rate")):
            findings.append({"code": "raw_memory_contamination", "case_id": case_id})
        if _nonzero(card.get("cross_case_leakage_rate")):
            findings.append({"code": "cross_case_memory_leakage", "case_id": case_id})
        if _nonzero(card.get("unsupported_claim_rate")):
            findings.append({"code": "unsupported_or_fabricated_citation", "case_id": case_id})
        revoked = set(cases.get(case_id, {}).get("revoked_evidence_ids", ()))
        if revoked & set(output["memory_evidence_ids"]):
            findings.append({"code": "revoked_evidence_retained", "case_id": case_id})
        for code in analyze_case(cases[case_id], output):
            findings.append({"code": code, "case_id": case_id})


def _failed_cases(
    cases: Mapping[str, Mapping[str, Any]],
    outputs: Mapping[str, Mapping[str, Any]],
    cards: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> list[Mapping[str, Any]]:
    failures = []
    for case_id, output in sorted(outputs.items()):
        taxonomy = []
        if output["execution_status"] != "completed":
            taxonomy.append("execution_incomplete")
        for metric in ZERO_TOLERANCE:
            if _nonzero(cards.get(case_id, {}).get(metric)):
                taxonomy.append(metric)
        if case_id in cases:
            taxonomy.extend(analyze_case(cases[case_id], output))
        if taxonomy:
            failures.append({"case_id": case_id, "taxonomy": sorted(set(taxonomy))})
    return failures


def _nonzero(metric: Mapping[str, Any] | None) -> bool:
    return bool(metric and metric["status"] == "measured" and metric["value"] > 0)


def _unmeasured() -> dict[str, Mapping[str, Any]]:
    return {metric: unavailable("not_measured", "case_coverage_mismatch") for metric in METRICS}
