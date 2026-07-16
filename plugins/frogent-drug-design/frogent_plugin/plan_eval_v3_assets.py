"""Locked assets, typed receipts, and sealed envelopes for PLAN v3."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .eval_schema import exact, text
from .plan_eval_v2_assets import EVALUATOR_FILES as V2_FILES
from .plan_eval_v2_assets import PlanEvalV2Bundle, load_plan_v2_bundle
from .plan_eval_schema import METRICS, PRIMARY_METRICS

ARMS = ("skill_a", "skill_b")
REPLICATES = ("17", "29", "43")
CLAIM_LIMITS = ("exposed_development_panel", "seed_control_unverified",
                "candidate_reference_filesystem_isolation_not_established",
                "independent_score_owner_not_established",
                "model_runtime_provider_memory_identity_closure_incomplete",
                "actual_prompt_delivery_not_independently_attested")
ASSET_PATHS = {
    "candidate_tasks": "evals/plan-forward-v1.candidate-tasks.json",
    "frozen_corpus": "evals/plan-forward-v1.frozen-corpus.json",
    "candidate_constraints": "evals/plan-forward-v2.candidate-constraints.json",
    "evaluator_oracles": "evals/plan-forward-v2.evaluator-oracles.json",
    "common_prompt": "evals/plan-forward-v2.worker-common.txt",
    "current_skill": "evals/plan-forward-v3.current-skill.md",
    "candidate_skill": "evals/plan-forward-v3.candidate-skill.md",
    "shared_reference": "evals/plan-forward-v3.query-strategy.md",
    "arm_instruction": "evals/plan-forward-v3.arm-instruction.txt",
}
V3_FILES = frozenset({"frogent_plugin/plan_eval_v3_assets.py",
                      "frogent_plugin/plan_eval_v3_schema.py",
                      "frogent_plugin/plan_eval_v3_runner.py",
                      "frogent_plugin/plan_eval_assets.py",
                      "scripts/run_plan_forward_v3_eval.py"})
EVALUATOR_FILES = V2_FILES | V3_FILES
HARD_GATES = ("pair_coverage_not_comparable", "metric_coverage_not_comparable",
              "quality_metric_regression", "temporal_violation", "future_record",
              "future_metadata", "unsupported_source", "query_budget_exceeded",
              "source_route_mismatch", "hit_record_mismatch", "orphan_canonical_record",
              "conflicting_canonical_record", "worker_execution_failed")
FROZEN_COMMITS = {"current_clean": "a0d662925a5c14d5df908409e045b1069d9c327a",
                  "v2_official_result": "fad8bc1aeb842a3995996ad0c819bf822c3042e0",
                  "v2_pre_worker_lock": "e1304fc6033f098f00bb202cb20aca7539796c81"}


@dataclass(frozen=True, slots=True)
class PlanEvalV3Bundle:
    root: Path
    manifest: Mapping[str, Any]
    v2: PlanEvalV2Bundle
    raw_assets: Mapping[str, bytes]
    asset_digests: Mapping[str, str]
    evaluator_digests: Mapping[str, str]

    @property
    def cases(self): return self.v2.cases
    @property
    def oracles(self): return self.v2.oracles
    @property
    def corpus(self): return self.v2.corpus
    @property
    def constraints(self): return self.v2.constraints


def load_plan_v3_bundle(root_path: Path, manifest_path: Path) -> PlanEvalV3Bundle:
    root = root_path.resolve(strict=True)
    manifest = _object(_safe(root, manifest_path))
    fields = frozenset({"eval_id", "schema_version", "pack_status", "authority_scope",
                        "provider_mode", "network", "seed_control", "replicate_labels",
                        "arms", "role_mapping", "sole_variable", "claim_limits", "assets",
                        "evaluator_identity", "envelopes", "hypothesis", "frozen_commits",
                        "registered_metrics", "primary_metrics", "hard_gates",
                        "fresh_workers", "effect_outcome", "promotion_eligible"})
    exact(manifest, fields, "plan v3 manifest")
    _manifest_policy(manifest)
    raw, digests = _load_assets(root, manifest["assets"])
    evaluator = _load_revision(root, manifest["evaluator_identity"])
    v2 = load_plan_v2_bundle(root, Path("evals/plan-forward-v2.manifest.json"))
    bundle = PlanEvalV3Bundle(root, manifest, v2, raw, digests, evaluator)
    _validate_shared_assets(bundle)
    _validate_envelopes(bundle)
    return bundle


def worker_receipt(bundle: PlanEvalV3Bundle, case_id: str, arm: str, replicate: str) -> dict[str, Any]:
    if arm not in ARMS or replicate not in REPLICATES:
        raise ValueError("worker arm or replicate is invalid")
    case = next(item for item in bundle.cases if item["case_id"] == case_id)
    role = bundle.manifest["role_mapping"][arm]
    skill_name = "current_skill" if arm == "skill_a" else "candidate_skill"
    payload = {"case": case, "constraint": bundle.constraints[case_id], "profile": arm,
               "role": role, "replicate_label": replicate,
               "identity_digests": {name: bundle.asset_digests[name] for name in
                                    ("common_prompt", "arm_instruction", skill_name, "shared_reference")}}
    return {"case_id": case_id, "profile": arm, "replicate_label": replicate,
            "worker_input_digest": _digest(payload), "as_of": case["as_of"],
            "constraint": bundle.constraints[case_id]}


def worker_envelope(bundle: PlanEvalV3Bundle, case_id: str, arm: str, replicate: str) -> bytes:
    receipt = worker_receipt(bundle, case_id, arm, replicate)
    case = next(item for item in bundle.cases if item["case_id"] == case_id)
    skill = bundle.raw_assets["current_skill" if arm == "skill_a" else "candidate_skill"]
    parts = (bundle.raw_assets["common_prompt"], b"\n\nCANDIDATE TASK\n" + case["task"].encode(),
             b"\n\nWORKER RECEIPT\n" + _canonical(receipt).encode(),
             b"\n\nARM INSTRUCTION\n" + bundle.raw_assets["arm_instruction"],
             b"\n\nSKILL SNAPSHOT\n" + skill,
             b"\n\nSHARED REFERENCE\n" + bundle.raw_assets["shared_reference"])
    return b"".join(parts).rstrip(b"\n") + b"\n"


def bundle_identity(bundle: PlanEvalV3Bundle) -> str:
    return _digest({"manifest": bundle.manifest, "assets": bundle.asset_digests,
                    "evaluator": bundle.evaluator_digests})


def _manifest_policy(value: Mapping[str, Any]) -> None:
    fixed = {"eval_id": "plan-forward-v3", "schema_version": "3.0", "pack_status": "locked",
             "authority_scope": "exposed_development_diagnostic", "provider_mode": "frozen_snapshot",
             "network": "denied", "seed_control": "unverified",
             "sole_variable": "budgeted_minimum_evidence_path_bullet"}
    if any(value[key] != expected for key, expected in fixed.items()):
        raise ValueError("plan v3 fixed policy mismatch")
    if tuple(value["replicate_labels"]) != REPLICATES or tuple(value["arms"]) != ARMS:
        raise ValueError("plan v3 matrix mismatch")
    if value["role_mapping"] != {"skill_a": "baseline_current", "skill_b": "candidate"}:
        raise ValueError("plan v3 role mapping mismatch")
    if tuple(value["claim_limits"]) != CLAIM_LIMITS or set(value["assets"]) != set(ASSET_PATHS):
        raise ValueError("plan v3 claim or asset policy mismatch")
    if value["frozen_commits"] != FROZEN_COMMITS or value["fresh_workers"] != 0:
        raise ValueError("plan v3 frozen identity or worker state mismatch")
    if value["effect_outcome"] != "not_evaluated" or value["promotion_eligible"] is not False:
        raise ValueError("plan v3 pre-worker effect state mismatch")
    if tuple(value["registered_metrics"]) != tuple(METRICS):
        raise ValueError("plan v3 metric policy mismatch")
    if tuple(value["primary_metrics"]) != tuple(PRIMARY_METRICS) or tuple(value["hard_gates"]) != HARD_GATES:
        raise ValueError("plan v3 gate policy mismatch")
    if value["hypothesis"] != "budgeted minimum evidence paths improve primary recall or precision without regressions":
        raise ValueError("plan v3 hypothesis mismatch")
    if any(value["assets"][name].get("path") != path for name, path in ASSET_PATHS.items()):
        raise ValueError("plan v3 asset path identity mismatch")
    if value["evaluator_identity"].get("path") != "evals/plan-forward-v3.evaluator-revision.json":
        raise ValueError("plan v3 revision path identity mismatch")


def _load_assets(root: Path, specs: Mapping[str, Any]) -> tuple[dict[str, bytes], dict[str, str]]:
    raw, digests = {}, {}
    for name, spec in specs.items():
        exact(spec, frozenset({"path", "sha256"}), "plan v3 asset")
        data = _safe(root, Path(text(spec["path"], "asset path"))).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != spec["sha256"]: raise ValueError(f"plan v3 asset digest mismatch: {name}")
        raw[name], digests[name] = data, digest
    return raw, digests


def _load_revision(root: Path, spec: Mapping[str, Any]) -> dict[str, str]:
    exact(spec, frozenset({"path", "sha256"}), "plan v3 evaluator identity")
    raw = _safe(root, Path(spec["path"])).read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec["sha256"]: raise ValueError("plan v3 revision digest mismatch")
    revision = json.loads(raw); exact(revision, frozenset({"schema_version", "files"}), "plan v3 revision")
    if revision["schema_version"] != "3.0" or set(revision["files"]) != EVALUATOR_FILES:
        raise ValueError("plan v3 revision file set mismatch")
    result = {}
    for name, item in revision["files"].items():
        exact(item, frozenset({"path", "sha256"}), "plan v3 evaluator file")
        if item["path"] != name: raise ValueError("plan v3 evaluator key path mismatch")
        digest = hashlib.sha256(_safe(root, Path(name)).read_bytes()).hexdigest()
        if digest != item["sha256"]: raise ValueError(f"plan v3 evaluator digest mismatch: {name}")
        result[name] = digest
    return result


def _validate_shared_assets(bundle: PlanEvalV3Bundle) -> None:
    mapping = {"candidate_tasks": "candidate_tasks", "frozen_corpus": "frozen_corpus",
               "candidate_constraints": "candidate_constraints", "evaluator_oracles": "evaluator_oracles",
               "common_prompt": "common_prompt"}
    if any(bundle.asset_digests[name] != bundle.v2.asset_digests.get(target, bundle.v2.identity_digests.get(target))
           for name, target in mapping.items()):
        raise ValueError("plan v3 shared v2 asset identity mismatch")


def _validate_envelopes(bundle: PlanEvalV3Bundle) -> None:
    expected = {f"{case['case_id']}|{arm}|{rep}" for case in bundle.cases for arm in ARMS for rep in REPLICATES}
    if set(bundle.manifest["envelopes"]) != expected: raise ValueError("plan v3 envelope coverage mismatch")
    for key, spec in bundle.manifest["envelopes"].items():
        exact(spec, frozenset({"path", "sha256"}), "plan v3 envelope")
        case, arm, rep = key.split("|")
        expected_path = f"evals/plan-forward-v3.envelopes/{case}-{arm}-{rep}.txt"
        if spec["path"] != expected_path: raise ValueError("plan v3 envelope path identity mismatch")
        raw = _safe(bundle.root, Path(expected_path)).read_bytes()
        if hashlib.sha256(raw).hexdigest() != spec["sha256"] or raw != worker_envelope(bundle, case, arm, rep):
            raise ValueError("plan v3 envelope identity mismatch")


def _safe(root: Path, path: Path) -> Path:
    if path.is_absolute() or ".." in path.parts: raise ValueError("plan v3 path must be relative")
    resolved = (root / path).resolve(strict=True); resolved.relative_to(root); return resolved
def _object(path: Path):
    value = json.loads(path.read_text());
    if not isinstance(value, dict): raise ValueError("plan v3 manifest must be object")
    return value
def _canonical(value: Any): return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def _digest(value: Any): return hashlib.sha256(_canonical(value).encode()).hexdigest()
