"""Fail-closed loading for replayable research eval assets."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from .eval_schema import exact, has_leakage, text, validate_case, validate_output

ASSET_NAMES = ("cases", "baseline", "candidate")
SPLITS = frozenset({"development", "frozen_core", "challenge"})
MANIFEST_FIELDS = frozenset(
    {
        "eval_id", "schema_version", "authority_scope", "assets", "provider_mode",
        "network", "as_of", "temporal_policy", "baseline_profile",
        "candidate_profile", "sole_variable", "registered_metrics",
        "primary_metrics", "hard_gates", "eval_hooks",
    }
)
CASE_FIELDS = frozenset(
    {
        "case_id", "split", "family_id", "lineage_id", "as_of",
        "relevant_record_ids", "anchor_record_ids", "counterevidence_record_ids",
        "admissible_evidence_ids", "revoked_evidence_ids", "claim_links",
        "evidence_provenance", "required_evidence_gaps", "acceptable_stop_reasons",
    }
)
OUTPUT_FIELDS = frozenset(
    {
        "case_id", "execution_status", "retrieved_hits", "records",
        "evidence_lineage",
        "qualified_evidence_ids", "admitted_evidence_ids", "memory_evidence_ids",
        "revoked_evidence_ids", "claims", "surfaced_gaps", "stop_reason",
    }
)
SUPPORTED_METRICS = frozenset(
    {
        "anchor_recall", "counterevidence_recall", "retrieval_precision",
        "provenance_completeness", "temporal_violation_rate", "admission_precision",
        "useful_evidence_recall", "raw_memory_contamination_rate",
        "revocation_accuracy", "cross_case_leakage_rate", "citation_precision",
        "unsupported_claim_rate", "counterevidence_retention",
        "evidence_gap_visibility", "stop_correctness",
    }
)
SUPPORTED_GATES = frozenset(
    {
        "case_coverage_match", "primary_improvement_without_regression",
        "zero_temporal_violation", "zero_raw_memory_contamination",
        "zero_cross_case_leakage", "zero_unsupported_citation",
        "no_revoked_evidence_retention", "evidence_lineage_integrity",
        "retrieval_record_consistency", "fixture_authority_no_promotion",
    }
)


@dataclass(frozen=True, slots=True)
class EvalBundle:
    root: Path
    manifest: Mapping[str, Any]
    cases: tuple[Mapping[str, Any], ...]
    baseline: tuple[Mapping[str, Any], ...]
    candidate: tuple[Mapping[str, Any], ...]
    asset_digests: Mapping[str, str]


def canonical_bytes(value: Any) -> bytes:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def content_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_bundle(plugin_root: Path, manifest_path: Path) -> EvalBundle:
    root = plugin_root.resolve(strict=True)
    path = _safe_path(root, manifest_path)
    manifest = _read_json(path)
    exact(manifest, MANIFEST_FIELDS, "manifest")
    _validate_manifest(manifest)
    assets: dict[str, Any] = {}
    digests: dict[str, str] = {}
    for name in ASSET_NAMES:
        spec = manifest["assets"][name]
        exact(spec, frozenset({"path", "sha256"}), f"asset {name}")
        asset_path = _safe_path(root, Path(spec["path"]))
        raw = asset_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != spec["sha256"]:
            raise ValueError(f"asset digest mismatch: {name}")
        assets[name] = json.loads(raw)
        digests[name] = digest
    cases = _validate_cases(assets["cases"], manifest["as_of"])
    baseline = _validate_outputs(assets["baseline"], "baseline")
    candidate = _validate_outputs(assets["candidate"], "candidate")
    return EvalBundle(root, manifest, cases, baseline, candidate, digests)


def _validate_manifest(value: Mapping[str, Any]) -> None:
    if value["schema_version"] != "1.0":
        raise ValueError("unsupported eval schema_version")
    if value["authority_scope"] != "evaluator_fixture":
        raise ValueError("unsupported authority_scope")
    if value["provider_mode"] != "frozen_snapshot" or value["network"] != "denied":
        raise ValueError("research eval must be frozen and offline")
    date.fromisoformat(value["as_of"])
    if value["temporal_policy"] != "published_on_lte_as_of":
        raise ValueError("unsupported temporal policy")
    if set(value["assets"]) != set(ASSET_NAMES):
        raise ValueError("manifest assets must be exact")
    registered = set(value["registered_metrics"])
    if registered != SUPPORTED_METRICS or not set(value["primary_metrics"]) <= registered:
        raise ValueError("primary metrics must be registered")
    if set(value["hard_gates"]) != SUPPORTED_GATES:
        raise ValueError("manifest hard gates differ from evaluator policy")
    hooks = value["eval_hooks"]
    if set(hooks) != {
        "plan-literature-search", "research-biomedical-literature",
        "screen-literature-evidence", "synthesize-biomedical-evidence",
    }:
        raise ValueError("all research Skill eval hooks are required")
    if any(not set(metrics) or not set(metrics) <= registered for metrics in hooks.values()):
        raise ValueError("eval hook references unknown metrics")
    for field in ("eval_id", "baseline_profile", "candidate_profile", "sole_variable"):
        text(value[field], field)
    if value["baseline_profile"] != "fixture-baseline-v1" or value["candidate_profile"] != "fixture-candidate-v1":
        raise ValueError("fixture profile identity mismatch")
    if value["sole_variable"] != "evaluator_self_test_fixture_pack":
        raise ValueError("fixture sole variable mismatch")


def _validate_cases(payload: Any, manifest_as_of: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(payload, list) or not payload:
        raise ValueError("cases must be a non-empty list")
    seen: set[str] = set()
    evidence_seen: set[str] = set()
    lineage_splits: dict[str, str] = {}
    cases = []
    for item in payload:
        exact(item, CASE_FIELDS, "case")
        case_id = text(item["case_id"], "case_id")
        if case_id in seen or item["split"] not in SPLITS:
            raise ValueError("case identity or split is invalid")
        if item["as_of"] != manifest_as_of:
            raise ValueError("case as_of differs from manifest")
        date.fromisoformat(item["as_of"])
        seen.add(case_id)
        cases.append(item)
        validate_case(item)
        case_evidence = {entry["evidence_id"] for entry in item["evidence_provenance"]}
        if evidence_seen & case_evidence:
            raise ValueError("evaluator evidence IDs must be globally unique")
        evidence_seen.update(case_evidence)
        for key in (item["family_id"], item["lineage_id"]):
            previous = lineage_splits.setdefault(key, item["split"])
            if previous != item["split"]:
                raise ValueError("family or lineage crosses exposed splits")
    if {item["split"] for item in cases} != SPLITS:
        raise ValueError("all exposed splits are required")
    return tuple(cases)


def _validate_outputs(payload: Any, label: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(payload, list):
        raise ValueError(f"{label} output must be a list")
    if has_leakage(payload):
        raise ValueError(f"{label} output contains outcome leakage")
    seen: set[str] = set()
    outputs = []
    for item in payload:
        exact(item, OUTPUT_FIELDS, f"{label} output")
        case_id = text(item["case_id"], "case_id")
        if case_id in seen:
            raise ValueError(f"duplicate {label} case output")
        for hit in item["retrieved_hits"]:
            exact(hit, frozenset({"record_id", "source", "query", "artifact", "published_on"}), "retrieved hit")
        for record in item["records"]:
            exact(record, frozenset({"record_id", "source", "query", "artifact", "published_on"}), "record")
        for lineage in item["evidence_lineage"]:
            exact(lineage, frozenset({"evidence_id", "record_id", "artifact"}), "evidence lineage")
        for claim in item["claims"]:
            exact(claim, frozenset({"claim_id", "evidence_ids", "counterevidence_ids"}), "claim")
        validate_output(item)
        seen.add(case_id)
        outputs.append(item)
    return tuple(outputs)


def _safe_path(root: Path, path: Path) -> Path:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("eval asset path must be relative and contained")
    resolved = (root / path).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("eval asset path escapes plugin root") from exc
    return resolved


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("manifest must be a JSON object")
    return value
