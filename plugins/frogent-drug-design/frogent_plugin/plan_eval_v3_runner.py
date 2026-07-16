"""Opaque-arm paired comparison and replay for PLAN forward v3."""

import hashlib
import json
from typing import Any, Mapping

from .plan_eval_schema import METRICS, PRIMARY_METRICS
from .plan_eval_v2_replay import QUALITY_METRICS, replay_plan
from .plan_eval_v3_assets import (
    ARMS, CLAIM_LIMITS, HARD_GATES, REPLICATES, PlanEvalV3Bundle, bundle_identity,
)
from .plan_eval_v3_schema import validate_plan_output

BLOCKERS = HARD_GATES


def evaluate_plan_outputs(bundle: PlanEvalV3Bundle, values: list[Any], require_complete: bool = False,
                          input_metadata: list[Mapping[str, str]] | None = None) -> dict[str, Any]:
    runs, invalid, receipts = _prepare_runs(bundle, values, input_metadata)
    expected = {(case["case_id"], arm, rep) for case in bundle.cases for arm in ARMS for rep in REPLICATES}
    coverage = _coverage_findings(expected, set(runs), invalid)
    if require_complete and coverage:
        raise ValueError("complete 12-output coverage is required for evaluation")
    comparisons = [_compare_pair(runs, case["case_id"], rep) for case in bundle.cases for rep in REPLICATES]
    findings = sorted(set(coverage + [finding for item in comparisons for finding in item["findings"]]))
    result = {"eval_id": bundle.manifest["eval_id"], "execution_completion": "completed",
              "effect_outcome": decide_effect(comparisons, findings), "promotion_eligible": False,
              "claim_limits": list(CLAIM_LIMITS), "bundle_identity": bundle_identity(bundle),
              "role_mapping": dict(bundle.manifest["role_mapping"]),
              "output_digests": _output_digests(runs), "runs": [runs[key] for key in sorted(runs)],
              "comparisons": comparisons, "findings": findings,
              "invalid_outputs": {"count": sum(invalid.values()), "taxonomy": invalid},
              "input_receipts": receipts,
              "worker_completion": _worker_completion(runs, len(expected), sum(invalid.values()))}
    result["replay_digest"] = _digest(result)
    return result


def verify_plan_result(bundle: PlanEvalV3Bundle, values: list[Any], expected: Mapping[str, Any],
                       input_metadata: list[Mapping[str, str]] | None = None) -> None:
    replay = evaluate_plan_outputs(bundle, values, require_complete=True, input_metadata=input_metadata)
    if replay["worker_completion"]["state"] != "completed":
        raise ValueError("complete result verification requires 12 completed workers")
    if replay != expected:
        raise ValueError("plan v3 result differs from asset-bound exact replay")


def decide_effect(comparisons: list[Mapping[str, Any]], findings: list[str]) -> str:
    if set(findings) & set(BLOCKERS) or len(comparisons) != 6:
        return "rejected"
    if any(item["state"] != "comparable" for item in comparisons):
        return "rejected"
    improved = any(item["deltas"][metric]["delta"] > 0 for item in comparisons for metric in PRIMARY_METRICS)
    return "improved" if improved else "flat"


def _prepare_runs(bundle: PlanEvalV3Bundle, values: list[Any], metadata: list[Mapping[str, str]] | None
                  ) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    runs: dict[tuple[str, str, str], dict[str, Any]] = {}
    invalid = {"schema_or_worker_identity_invalid": 0, "duplicate_output_identity": 0}
    receipts = []
    supplied = metadata if metadata is not None else [
        {"identity": f"input-{index:03d}", "digest": _digest(value)} for index, value in enumerate(values)
    ]
    if len(supplied) != len(values):
        raise ValueError("input metadata coverage mismatch")
    for value, receipt in zip(values, supplied):
        audit = {"identity": receipt["identity"], "digest": receipt["digest"]}
        try:
            output = validate_plan_output(value, bundle)
        except (KeyError, TypeError, ValueError):
            invalid["schema_or_worker_identity_invalid"] += 1
            receipts.append(dict(audit, status="invalid"))
            continue
        key = (output["case_id"], output["profile"], output["replicate_label"])
        if key in runs:
            invalid["duplicate_output_identity"] += 1
            receipts.append(dict(audit, status="duplicate"))
            continue
        run = replay_plan(output, bundle.v2)
        if output["execution_status"] != "completed":
            run["scorecard"] = {metric: {"state": "not_measured", "reason": "worker execution failed"}
                                for metric in METRICS}
            run["findings"] = sorted(set(run["findings"] + ["worker_execution_failed"]))
        runs[key] = run
        receipts.append(dict(audit, status="accepted", output_identity="|".join(key)))
    return runs, invalid, receipts


def _coverage_findings(expected: set[tuple[str, str, str]], actual: set[tuple[str, str, str]],
                       invalid: Mapping[str, int]) -> list[str]:
    findings = []
    if expected - actual:
        findings.append("missing_arm_or_replicate")
    if actual - expected or sum(invalid.values()):
        findings.append("extra_or_invalid_output")
    if findings:
        findings.append("pair_coverage_not_comparable")
    return findings


def _compare_pair(runs: Mapping[tuple[str, str, str], Mapping[str, Any]], case_id: str, rep: str) -> dict[str, Any]:
    baseline, candidate = runs.get((case_id, "skill_a", rep)), runs.get((case_id, "skill_b", rep))
    if baseline is None or candidate is None:
        return {"case_id": case_id, "replicate_label": rep, "state": "not_comparable",
                "arms": {"baseline": "skill_a", "candidate": "skill_b"},
                "deltas": {}, "findings": ["missing_paired_arm"]}
    deltas = {metric: _delta(baseline["scorecard"][metric], candidate["scorecard"][metric]) for metric in METRICS}
    findings = _delta_findings(deltas) + baseline["findings"] + candidate["findings"]
    state = "comparable" if all(value["state"] == "measured" for value in deltas.values()) else "not_comparable"
    return {"case_id": case_id, "replicate_label": rep, "state": state,
            "arms": {"baseline": "skill_a", "candidate": "skill_b"},
            "deltas": deltas, "findings": sorted(set(findings))}


def _delta(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    if baseline["state"] != "measured" or candidate["state"] != "measured":
        return {"state": "not_comparable", "reason": "metric measured coverage differs or is absent"}
    return {"state": "measured", "baseline": baseline["value"], "candidate": candidate["value"],
            "delta": candidate["value"] - baseline["value"]}


def _delta_findings(deltas: Mapping[str, Mapping[str, Any]]) -> list[str]:
    findings = []
    if any(value["state"] != "measured" for value in deltas.values()):
        findings.append("metric_coverage_not_comparable")
    for metric, value in deltas.items():
        if value["state"] != "measured":
            continue
        direction = value["delta"] * (-1 if metric == "temporal_violation_rate" else 1)
        if direction < 0 and metric in QUALITY_METRICS:
            findings.append("quality_metric_regression")
        if metric == "temporal_violation_rate" and value["candidate"] > 0:
            findings.append("temporal_violation")
    return findings


def _worker_completion(runs: Mapping[tuple[str, str, str], Mapping[str, Any]], expected: int,
                       invalid: int) -> dict[str, Any]:
    completed = sum(run["plan"]["execution_status"] == "completed" for run in runs.values())
    failed = sum(run["plan"]["execution_status"] == "failed" for run in runs.values())
    missing, state = expected - len(runs), "completed"
    if failed:
        state = "failed"
    elif missing or invalid:
        state = "incomplete"
    return {"state": state, "expected": expected, "accepted": len(runs), "completed": completed,
            "failed": failed, "missing": missing, "invalid": invalid}


def _output_digests(runs: Mapping[tuple[str, str, str], Mapping[str, Any]]) -> dict[str, str]:
    return {"|".join(key): _digest(value["plan"]) for key, value in sorted(runs.items())}


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()
