"""Strict opaque-arm output adapter for PLAN forward v3."""

import re
from datetime import date
from typing import Any, Mapping

from .eval_schema import exact, text
from .plan_eval_schema import REPLICATES, string_list
from .plan_eval_v2_schema import (
    OUTPUT_FIELDS,
    _has_leakage,
    _validate_concepts,
    _validate_queries,
)
from .plan_eval_v3_assets import ARMS, PlanEvalV3Bundle, worker_receipt


def validate_plan_output(value: Any, bundle: PlanEvalV3Bundle) -> Mapping[str, Any]:
    if bundle.manifest["pack_status"] != "locked":
        raise ValueError("plan v3 preregistration is pending")
    if _has_leakage(value):
        raise ValueError("plan output contains sensitive evaluator key")
    exact(value, OUTPUT_FIELDS, "plan v3 output")
    for field in ("case_id", "question_frame"):
        text(value[field], field)
    if value["profile"] not in ARMS or value["replicate_label"] not in REPLICATES:
        raise ValueError("plan output arm or replicate is invalid")
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
    receipt = worker_receipt(bundle, value["case_id"], value["profile"], value["replicate_label"])
    if value["worker_input_digest"] != receipt["worker_input_digest"]:
        raise ValueError("worker input identity mismatch")
    return value
