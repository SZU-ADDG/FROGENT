"""Bound preregistration assets and corpus integrity for PLAN forward eval."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .eval_schema import exact, text
from .plan_eval_corpus import validate_corpus_assets
from .plan_eval_schema import CLAIM_LIMITS, METRICS, PRIMARY_METRICS, REPLICATES

MANIFEST_FIELDS = frozenset({
    "eval_id", "schema_version", "pack_status", "authority_scope", "provider_mode",
    "network", "seed_control", "output_schema_id", "replicate_labels", "profiles",
    "sole_variable", "registered_metrics", "primary_metrics", "claim_limits", "assets",
    "identity_assets", "evaluator_identity",
})
IDENTITY_NAMES = frozenset({"common_prompt", "baseline_instruction", "skill", "reference"})
EVALUATOR_FILES = frozenset({
    "frogent_plugin/plan_eval_schema.py", "frogent_plugin/plan_eval_corpus.py",
    "frogent_plugin/plan_eval_assets.py", "frogent_plugin/plan_eval_replay.py",
    "frogent_plugin/plan_eval_runner.py", "scripts/run_plan_forward_eval.py",
})


@dataclass(frozen=True, slots=True)
class PlanEvalBundle:
    root: Path
    manifest: Mapping[str, Any]
    cases: tuple[Mapping[str, Any], ...]
    oracles: Mapping[str, Mapping[str, Any]]
    corpus: tuple[Mapping[str, Any], ...]
    asset_digests: Mapping[str, str]
    identity_digests: Mapping[str, str]
    evaluator_digests: Mapping[str, str]


def load_plan_bundle(plugin_root: Path, manifest_path: Path) -> PlanEvalBundle:
    root = plugin_root.resolve(strict=True)
    manifest = _read_object(safe_path(root, manifest_path))
    exact(manifest, MANIFEST_FIELDS, "plan manifest")
    _validate_manifest(manifest)
    _, identities = _load_assets(root, manifest["identity_assets"], IDENTITY_NAMES)
    evaluator_digests = _load_evaluator_identity(root, manifest["evaluator_identity"])
    if manifest["pack_status"] == "awaiting_evaluator_assets":
        return PlanEvalBundle(root, manifest, (), {}, (), {}, identities, evaluator_digests)
    assets, digests = _load_assets(root, manifest["assets"], {"candidate_tasks", "evaluator_oracles", "frozen_corpus"})
    cases, oracles, corpus = validate_corpus_assets(
        assets["candidate_tasks"], assets["evaluator_oracles"], assets["frozen_corpus"]
    )
    return PlanEvalBundle(root, manifest, cases, oracles, corpus, digests, identities, evaluator_digests)


def worker_input_digest(bundle: PlanEvalBundle, case_id: str, profile: str, replicate: str) -> str:
    case = next(item for item in bundle.cases if item["case_id"] == case_id)
    identities = {"common_prompt": bundle.identity_digests["common_prompt"]}
    if profile == "single_skill":
        identities.update(skill=bundle.identity_digests["skill"], reference=bundle.identity_digests["reference"])
    else:
        identities["baseline_instruction"] = bundle.identity_digests["baseline_instruction"]
    payload = {"case": case, "profile": bundle.manifest["profiles"][profile],
               "replicate_label": replicate, "identity_digests": identities}
    return content_digest(payload)


def bundle_identity(bundle: PlanEvalBundle) -> str:
    return content_digest({"manifest": bundle.manifest, "asset_digests": bundle.asset_digests,
                           "identity_digests": bundle.identity_digests,
                           "evaluator_digests": bundle.evaluator_digests})


def content_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def contained_directory(root: Path, relative: Path, create: bool = False) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("directory path must be relative and contained")
    parent = safe_path(root, relative.parent)
    target = parent / relative.name
    if target.is_symlink():
        raise ValueError("contained directory cannot be a symlink")
    if create:
        target.mkdir(exist_ok=True)
    resolved = target.resolve(strict=True)
    resolved.relative_to(root.resolve(strict=True))
    return resolved


def write_contained_exclusive(root: Path, relative: Path, content: str) -> Path:
    directory = contained_directory(root, relative.parent, create=True)
    target = directory / relative.name
    if target.is_symlink():
        raise ValueError("output leaf cannot be a symlink")
    try:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise ValueError("output leaf already exists") from exc
    target.resolve(strict=True).relative_to(root.resolve(strict=True))
    return target


def safe_path(root: Path, path: Path) -> Path:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("plan eval path must be relative and contained")
    resolved = (root / path).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("plan eval path escapes plugin root") from exc
    return resolved


def _validate_manifest(value: Mapping[str, Any]) -> None:
    fixed = (("schema_version", "1.0"), ("authority_scope", "exposed_development_diagnostic"),
             ("provider_mode", "frozen_snapshot"), ("network", "denied"),
             ("seed_control", "unverified"), ("output_schema_id", "plan-forward-output-v1"),
             ("sole_variable", "plan-literature-search_skill_and_declared_reference"))
    if any(value[key] != expected for key, expected in fixed):
        raise ValueError("plan manifest fixed policy mismatch")
    if value["pack_status"] not in {"awaiting_evaluator_assets", "locked"}:
        raise ValueError("plan manifest pack_status is invalid")
    if tuple(value["replicate_labels"]) != REPLICATES:
        raise ValueError("plan replicate labels differ from preregistration")
    if tuple(value["registered_metrics"]) != METRICS or tuple(value["primary_metrics"]) != PRIMARY_METRICS:
        raise ValueError("plan metric policy mismatch")
    if tuple(value["claim_limits"]) != CLAIM_LIMITS:
        raise ValueError("plan claim limits mismatch")
    expected_profiles = {
        "no_skill": {"skill": "none", "declared_reference": "none"},
        "single_skill": {"skill": "plan-literature-search", "declared_reference": "skills/plan-literature-search/references/query-strategy.md"},
    }
    if value["profiles"] != expected_profiles:
        raise ValueError("plan profile identity or sole variable mismatch")
    required = set() if value["pack_status"] != "locked" else {"candidate_tasks", "evaluator_oracles", "frozen_corpus"}
    if set(value["assets"]) != required or set(value["identity_assets"]) != IDENTITY_NAMES:
        raise ValueError("plan manifest asset set does not match policy")
    exact(value["evaluator_identity"], frozenset({"path", "sha256"}), "evaluator identity")


def _load_assets(root: Path, specs: Mapping[str, Any], names: set[str] | frozenset[str]) -> tuple[dict[str, Any], dict[str, str]]:
    if set(specs) != set(names):
        raise ValueError("bound asset names differ from policy")
    assets, digests = {}, {}
    for name, spec in specs.items():
        exact(spec, frozenset({"path", "sha256"}), f"plan asset {name}")
        raw = safe_path(root, Path(text(spec["path"], "asset path"))).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != spec["sha256"]:
            raise ValueError(f"plan asset digest mismatch: {name}")
        assets[name], digests[name] = json.loads(raw) if name not in IDENTITY_NAMES else raw, digest
    return assets, digests


def _load_evaluator_identity(root: Path, spec: Mapping[str, Any]) -> dict[str, str]:
    path = safe_path(root, Path(text(spec["path"], "evaluator identity path")))
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
        raise ValueError("evaluator identity digest mismatch")
    revision = json.loads(raw)
    exact(revision, frozenset({"schema_version", "files"}), "evaluator revision")
    if revision["schema_version"] != "1.0" or set(revision["files"]) != EVALUATOR_FILES:
        raise ValueError("evaluator revision file set mismatch")
    digests = {}
    for name, file_spec in revision["files"].items():
        exact(file_spec, frozenset({"path", "sha256"}), "evaluator file")
        file_raw = safe_path(root, Path(text(file_spec["path"], "evaluator file path"))).read_bytes()
        digest = hashlib.sha256(file_raw).hexdigest()
        if digest != file_spec["sha256"]:
            raise ValueError(f"evaluator file digest mismatch: {name}")
        digests[name] = digest
    return digests


def _read_object(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("plan manifest must be an object")
    return value
