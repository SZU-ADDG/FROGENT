"""Bound preregistration loader and receipts for PLAN forward v2."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .eval_schema import exact, text, unique
from .plan_eval_corpus import validate_corpus_assets
from .plan_eval_v2_schema import (
    CLAIM_LIMITS, CONSTRAINT_FIELDS, METRICS, PRIMARY_METRICS, REPLICATES, string_list,
)

MANIFEST_FIELDS = frozenset({
    "eval_id", "schema_version", "pack_status", "authority_scope", "provider_mode",
    "network", "seed_control", "output_schema_id", "replicate_labels", "profiles",
    "sole_variable", "registered_metrics", "primary_metrics", "claim_limits", "assets",
    "identity_assets", "evaluator_identity",
})
ASSET_NAMES = frozenset({"candidate_tasks", "evaluator_oracles", "frozen_corpus", "candidate_constraints"})
IDENTITY_NAMES = frozenset({"common_prompt", "baseline_instruction", "skill", "reference"})
EXPECTED_PATHS = {
    "candidate_tasks": "evals/plan-forward-v1.candidate-tasks.json",
    "evaluator_oracles": "evals/plan-forward-v2.evaluator-oracles.json",
    "frozen_corpus": "evals/plan-forward-v1.frozen-corpus.json",
    "candidate_constraints": "evals/plan-forward-v2.candidate-constraints.json",
    "common_prompt": "evals/plan-forward-v2.worker-common.txt",
    "baseline_instruction": "evals/plan-forward-v2.baseline-instruction.txt",
    "skill": "skills/plan-literature-search/SKILL.md",
    "reference": "skills/plan-literature-search/references/query-strategy.md",
}
EVALUATOR_FILES = frozenset({
    "frogent_plugin/__init__.py", "frogent_plugin/catalog.py", "frogent_plugin/config.py",
    "frogent_plugin/contracts.py", "frogent_plugin/eval_integrity.py",
    "frogent_plugin/eval_manifest.py", "frogent_plugin/eval_metrics.py",
    "frogent_plugin/eval_runner.py", "frogent_plugin/eval_schema.py",
    "frogent_plugin/evidence.py", "frogent_plugin/harness.py",
    "frogent_plugin/literature.py", "frogent_plugin/registry.py",
    "frogent_plugin/retrieval.py", "frogent_plugin/v4_adapter.py",
    "frogent_plugin/plan_eval_schema.py", "frogent_plugin/plan_eval_corpus.py",
    "frogent_plugin/plan_eval_v2_schema.py", "frogent_plugin/plan_eval_v2_assets.py",
    "frogent_plugin/plan_eval_v2_replay.py", "frogent_plugin/plan_eval_v2_runner.py",
    "scripts/run_plan_forward_v2_eval.py",
})


@dataclass(frozen=True, slots=True)
class PlanEvalV2Bundle:
    root: Path
    manifest: Mapping[str, Any]
    cases: tuple[Mapping[str, Any], ...]
    oracles: Mapping[str, Mapping[str, Any]]
    corpus: tuple[Mapping[str, Any], ...]
    constraints: Mapping[str, Mapping[str, Any]]
    asset_digests: Mapping[str, str]
    identity_digests: Mapping[str, str]
    evaluator_digests: Mapping[str, str]


def load_plan_v2_bundle(plugin_root: Path, manifest_path: Path) -> PlanEvalV2Bundle:
    root = plugin_root.resolve(strict=True)
    manifest = _read_object(safe_path(root, manifest_path))
    exact(manifest, MANIFEST_FIELDS, "plan v2 manifest")
    _validate_manifest(manifest)
    _, identities = _load_assets(root, manifest["identity_assets"], IDENTITY_NAMES)
    evaluator = _load_evaluator_identity(root, manifest["evaluator_identity"])
    assets, digests = _load_assets(root, manifest["assets"], ASSET_NAMES)
    cases, oracles, corpus = validate_corpus_assets(
        assets["candidate_tasks"], assets["evaluator_oracles"], assets["frozen_corpus"]
    )
    constraints = _validate_constraints(assets["candidate_constraints"], cases, corpus, oracles)
    return PlanEvalV2Bundle(root, manifest, cases, oracles, corpus, constraints, digests, identities, evaluator)


def worker_input_digest(bundle: PlanEvalV2Bundle, case_id: str, profile: str, replicate: str) -> str:
    case = next(item for item in bundle.cases if item["case_id"] == case_id)
    identities = {"common_prompt": bundle.identity_digests["common_prompt"]}
    if profile == "single_skill":
        identities.update(skill=bundle.identity_digests["skill"], reference=bundle.identity_digests["reference"])
    else:
        identities["baseline_instruction"] = bundle.identity_digests["baseline_instruction"]
    payload = {"case": case, "constraint": bundle.constraints[case_id],
               "profile": bundle.manifest["profiles"][profile],
               "replicate_label": replicate, "identity_digests": identities}
    return content_digest(payload)


def worker_receipt(bundle: PlanEvalV2Bundle, case_id: str, profile: str, replicate: str) -> dict[str, Any]:
    case = next(item for item in bundle.cases if item["case_id"] == case_id)
    return {"case_id": case_id, "profile": profile, "replicate_label": replicate,
            "worker_input_digest": worker_input_digest(bundle, case_id, profile, replicate),
            "as_of": case["as_of"], "constraint": bundle.constraints[case_id]}


def bundle_identity(bundle: PlanEvalV2Bundle) -> str:
    return content_digest({"manifest": bundle.manifest, "asset_digests": bundle.asset_digests,
                           "identity_digests": bundle.identity_digests,
                           "evaluator_digests": bundle.evaluator_digests})


def content_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def safe_path(root: Path, path: Path) -> Path:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("plan v2 path must be relative and contained")
    resolved = (root / path).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("plan v2 path escapes plugin root") from exc
    return resolved


def _validate_manifest(value: Mapping[str, Any]) -> None:
    fixed = (("eval_id", "plan-forward-v2"), ("schema_version", "2.0"),
             ("pack_status", "locked"), ("authority_scope", "exposed_development_diagnostic"),
             ("provider_mode", "frozen_snapshot"), ("network", "denied"),
             ("seed_control", "unverified"), ("output_schema_id", "plan-forward-output-v2"),
             ("sole_variable", "plan-literature-search_skill_and_declared_reference"))
    if any(value[key] != expected for key, expected in fixed):
        raise ValueError("plan v2 manifest fixed policy mismatch")
    if tuple(value["replicate_labels"]) != REPLICATES:
        raise ValueError("plan v2 replicate labels differ")
    if tuple(value["registered_metrics"]) != METRICS or tuple(value["primary_metrics"]) != PRIMARY_METRICS:
        raise ValueError("plan v2 metric policy mismatch")
    if tuple(value["claim_limits"]) != CLAIM_LIMITS:
        raise ValueError("plan v2 claim limits mismatch")
    profiles = {"no_skill": {"skill": "none", "declared_reference": "none"},
                "single_skill": {"skill": "plan-literature-search", "declared_reference":
                                 "skills/plan-literature-search/references/query-strategy.md"}}
    if value["profiles"] != profiles or set(value["assets"]) != ASSET_NAMES:
        raise ValueError("plan v2 profile or asset policy mismatch")
    if set(value["identity_assets"]) != IDENTITY_NAMES:
        raise ValueError("plan v2 identity asset policy mismatch")
    exact(value["evaluator_identity"], frozenset({"path", "sha256"}), "evaluator identity")
    specs = dict(value["assets"], **value["identity_assets"])
    if any(specs[name].get("path") != path for name, path in EXPECTED_PATHS.items()):
        raise ValueError("plan v2 asset path identity mismatch")
    if value["evaluator_identity"]["path"] != "evals/plan-forward-v2.evaluator-revision.json":
        raise ValueError("plan v2 evaluator revision path identity mismatch")


def _validate_constraints(value: Any, cases: tuple[Mapping[str, Any], ...], corpus: tuple[Mapping[str, Any], ...],
                          oracles: Mapping[str, Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    case_ids = {item["case_id"] for item in cases}
    if not isinstance(value, list) or len(value) != len(cases):
        raise ValueError("candidate constraint coverage mismatch")
    validated, ids = [], []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("candidate constraint must be an object")
        exact(item, CONSTRAINT_FIELDS, "candidate constraint")
        case_id = text(item["case_id"], "constraint case_id")
        ids.append(case_id)
        string_list(item["available_source_routes"], "available_source_routes")
        if not isinstance(item["max_query_events"], int) or item["max_query_events"] < 1:
            raise ValueError("constraint max_query_events must be positive")
        validated.append(item)
    unique(ids, "constraint case IDs")
    if set(ids) != case_ids:
        raise ValueError("candidate constraint coverage mismatch")
    result = {}
    for item in validated:
        case_id = item["case_id"]
        corpus_routes = {record["source"] for record in corpus if record["case_id"] == case_id}
        if set(item["available_source_routes"]) != corpus_routes:
            raise ValueError("candidate routes differ from case corpus")
        if item["max_query_events"] != oracles[case_id]["max_query_events"]:
            raise ValueError("candidate budget differs from evaluator policy")
        result[case_id] = item
    return result


def _load_assets(root: Path, specs: Mapping[str, Any], names: frozenset[str]) -> tuple[dict[str, Any], dict[str, str]]:
    if set(specs) != set(names):
        raise ValueError("bound v2 asset names differ from policy")
    assets, digests = {}, {}
    for name, spec in specs.items():
        exact(spec, frozenset({"path", "sha256"}), f"plan v2 asset {name}")
        raw = safe_path(root, Path(text(spec["path"], "asset path"))).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != spec["sha256"]:
            raise ValueError(f"plan v2 asset digest mismatch: {name}")
        assets[name], digests[name] = json.loads(raw) if name not in IDENTITY_NAMES else raw, digest
    return assets, digests


def _load_evaluator_identity(root: Path, spec: Mapping[str, Any]) -> dict[str, str]:
    raw = safe_path(root, Path(text(spec["path"], "evaluator identity path"))).read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
        raise ValueError("plan v2 evaluator identity digest mismatch")
    revision = json.loads(raw)
    exact(revision, frozenset({"schema_version", "files"}), "plan v2 evaluator revision")
    if revision["schema_version"] != "2.0" or set(revision["files"]) != EVALUATOR_FILES:
        raise ValueError("plan v2 evaluator revision file set mismatch")
    digests = {}
    for name, file_spec in revision["files"].items():
        exact(file_spec, frozenset({"path", "sha256"}), "plan v2 evaluator file")
        if file_spec["path"] != name:
            raise ValueError("plan v2 evaluator key and path identity mismatch")
        raw = safe_path(root, Path(text(file_spec["path"], "evaluator file path"))).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != file_spec["sha256"]:
            raise ValueError(f"plan v2 evaluator file digest mismatch: {name}")
        digests[name] = digest
    return digests


def _read_object(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("plan v2 manifest must be an object")
    return value
