"""Integrity, mutation, and replay tests for the research eval kernel."""

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin.eval_manifest import EvalBundle, SUPPORTED_METRICS, load_bundle  # noqa: E402
from frogent_plugin.eval_runner import evaluate_bundle, verify_result  # noqa: E402

MANIFEST = Path("evals/research-eval-v1.manifest.json")


def loaded() -> EvalBundle:
    return load_bundle(PLUGIN_ROOT, MANIFEST)


def with_candidate(mutator, *, drop_last: bool = False) -> EvalBundle:
    bundle = loaded()
    candidate = copy.deepcopy(list(bundle.candidate))
    mutator(candidate)
    if drop_last:
        candidate.pop()
    return EvalBundle(
        bundle.root,
        bundle.manifest,
        bundle.cases,
        bundle.baseline,
        tuple(candidate),
        bundle.asset_digests,
    )


def finding_codes(result: dict) -> set[str]:
    return {item["code"] for item in result["hard_gate_findings"]}


class AssetSandbox:
    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=PLUGIN_ROOT / "evals")
        self.root = Path(self.temp.name)
        self.manifest = json.loads((PLUGIN_ROOT / MANIFEST).read_text(encoding="utf-8"))
        for name, spec in self.manifest["assets"].items():
            source = PLUGIN_ROOT / spec["path"]
            target = self.root / source.name
            target.write_bytes(source.read_bytes())
            spec["path"] = target.relative_to(PLUGIN_ROOT).as_posix()
        self.manifest_path = self.root / "manifest.json"

    def write_manifest(self) -> None:
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def asset(self, name: str) -> Path:
        return PLUGIN_ROOT / self.manifest["assets"][name]["path"]

    def rewrite(self, name: str, value) -> None:
        path = self.asset(name)
        path.write_text(json.dumps(value), encoding="utf-8")
        self.manifest["assets"][name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    def close(self) -> None:
        self.temp.cleanup()


class ManifestIntegrityTests(unittest.TestCase):
    def test_all_skill_hooks_resolve_to_exact_registered_metrics(self) -> None:
        manifest = loaded().manifest
        self.assertEqual(SUPPORTED_METRICS, set(manifest["registered_metrics"]))
        self.assertEqual(
            {
                "plan-literature-search",
                "research-biomedical-literature",
                "screen-literature-evidence",
                "synthesize-biomedical-evidence",
            },
            set(manifest["eval_hooks"]),
        )
        self.assertTrue(all(set(metrics) <= SUPPORTED_METRICS for metrics in manifest["eval_hooks"].values()))

    def test_exact_replay_is_canonical_and_stable(self) -> None:
        first = evaluate_bundle(loaded())
        second = evaluate_bundle(loaded())
        self.assertEqual(first, second)
        verify_result(first)

    def test_any_bound_asset_byte_change_is_tamper_rejected(self) -> None:
        for name in ("cases", "baseline", "candidate"):
            with self.subTest(name=name):
                sandbox = AssetSandbox()
                try:
                    sandbox.asset(name).write_bytes(sandbox.asset(name).read_bytes() + b" ")
                    sandbox.write_manifest()
                    with self.assertRaisesRegex(ValueError, "digest mismatch"):
                        load_bundle(PLUGIN_ROOT, sandbox.manifest_path.relative_to(PLUGIN_ROOT))
                finally:
                    sandbox.close()

    def test_recursive_sensitive_key_is_leakage_negative_control(self) -> None:
        sandbox = AssetSandbox()
        try:
            candidate = json.loads(sandbox.asset("candidate").read_text(encoding="utf-8"))
            candidate[0]["claims"][0]["gold_hint"] = "exposed reference copy"
            sandbox.rewrite("candidate", candidate)
            sandbox.write_manifest()
            with self.assertRaisesRegex(ValueError, "outcome leakage"):
                load_bundle(PLUGIN_ROOT, sandbox.manifest_path.relative_to(PLUGIN_ROOT))
        finally:
            sandbox.close()

    def test_absolute_parent_and_symlink_escape_paths_are_rejected(self) -> None:
        for bad_path in ("/etc/hosts", "../outside.json"):
            sandbox = AssetSandbox()
            try:
                sandbox.manifest["assets"]["cases"]["path"] = bad_path
                sandbox.write_manifest()
                with self.assertRaisesRegex(ValueError, "relative and contained"):
                    load_bundle(PLUGIN_ROOT, sandbox.manifest_path.relative_to(PLUGIN_ROOT))
            finally:
                sandbox.close()
        sandbox = AssetSandbox()
        try:
            link = sandbox.root / "escape.json"
            link.symlink_to("/etc/hosts")
            sandbox.manifest["assets"]["cases"] = {
                "path": link.relative_to(PLUGIN_ROOT).as_posix(),
                "sha256": hashlib.sha256(link.read_bytes()).hexdigest(),
            }
            sandbox.write_manifest()
            with self.assertRaisesRegex(ValueError, "escapes plugin root"):
                load_bundle(PLUGIN_ROOT, sandbox.manifest_path.relative_to(PLUGIN_ROOT))
        finally:
            sandbox.close()

    def test_live_network_and_policy_identity_mutations_fail_closed(self) -> None:
        mutations = (
            ("provider_mode", "live"),
            ("network", "enabled"),
            ("sole_variable", "candidate_claimed_improvement"),
            ("registered_metrics", ["anchor_recall"]),
            ("hard_gates", ["fixture_authority_no_promotion"]),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                sandbox = AssetSandbox()
                try:
                    sandbox.manifest[field] = value
                    sandbox.write_manifest()
                    with self.assertRaises(ValueError):
                        load_bundle(PLUGIN_ROOT, sandbox.manifest_path.relative_to(PLUGIN_ROOT))
                finally:
                    sandbox.close()

    def test_family_lineage_cross_split_is_rejected(self) -> None:
        sandbox = AssetSandbox()
        try:
            cases = json.loads(sandbox.asset("cases").read_text(encoding="utf-8"))
            cases[1]["family_id"] = cases[0]["family_id"]
            sandbox.rewrite("cases", cases)
            sandbox.write_manifest()
            with self.assertRaisesRegex(ValueError, "crosses exposed splits"):
                load_bundle(PLUGIN_ROOT, sandbox.manifest_path.relative_to(PLUGIN_ROOT))
        finally:
            sandbox.close()

    def test_malformed_lists_status_and_duplicate_ids_fail_closed(self) -> None:
        for mutation in ("string_list", "status", "duplicate"):
            with self.subTest(mutation=mutation):
                sandbox = AssetSandbox()
                try:
                    candidate = json.loads(sandbox.asset("candidate").read_text(encoding="utf-8"))
                    if mutation == "string_list":
                        candidate[0]["memory_evidence_ids"] = "e-dev-support"
                    elif mutation == "status":
                        candidate[0]["execution_status"] = "maybe"
                    else:
                        candidate[0]["qualified_evidence_ids"] *= 2
                    sandbox.rewrite("candidate", candidate)
                    sandbox.write_manifest()
                    with self.assertRaises(ValueError):
                        load_bundle(PLUGIN_ROOT, sandbox.manifest_path.relative_to(PLUGIN_ROOT))
                finally:
                    sandbox.close()

    def test_oracle_claim_and_record_provenance_fail_closed(self) -> None:
        for mutation in ("unknown_evidence", "irrelevant_record"):
            with self.subTest(mutation=mutation):
                sandbox = AssetSandbox()
                try:
                    cases = json.loads(sandbox.asset("cases").read_text(encoding="utf-8"))
                    if mutation == "unknown_evidence":
                        cases[0]["claim_links"][0]["evidence_ids"] = ["e-unmapped"]
                    else:
                        cases[0]["evidence_provenance"][0]["record_id"] = "r-unrelated"
                    sandbox.rewrite("cases", cases)
                    sandbox.write_manifest()
                    with self.assertRaisesRegex(ValueError, "provenance|admissible"):
                        load_bundle(PLUGIN_ROOT, sandbox.manifest_path.relative_to(PLUGIN_ROOT))
                finally:
                    sandbox.close()

    def test_case_evidence_semantics_and_global_ids_fail_closed(self) -> None:
        for mutation in ("overlap", "claim_revoked", "cross_case_duplicate"):
            with self.subTest(mutation=mutation):
                sandbox = AssetSandbox()
                try:
                    cases = json.loads(sandbox.asset("cases").read_text(encoding="utf-8"))
                    if mutation == "overlap":
                        cases[0]["revoked_evidence_ids"].append("e-dev-support")
                    elif mutation == "claim_revoked":
                        cases[0]["claim_links"][0]["evidence_ids"] = ["e-dev-stale"]
                    else:
                        cases[1]["evidence_provenance"][0]["evidence_id"] = "e-dev-support"
                        cases[1]["admissible_evidence_ids"] = ["e-dev-support"]
                        cases[1]["claim_links"][0]["evidence_ids"] = ["e-dev-support"]
                    sandbox.rewrite("cases", cases)
                    sandbox.write_manifest()
                    with self.assertRaises(ValueError):
                        load_bundle(PLUGIN_ROOT, sandbox.manifest_path.relative_to(PLUGIN_ROOT))
                finally:
                    sandbox.close()


class EvaluatorMutationTests(unittest.TestCase):
    def test_future_record_in_hit_and_record_triggers_gate(self) -> None:
        def mutate(items):
            items[0]["retrieved_hits"][0]["published_on"] = "2026-07-16"
            items[0]["records"][0]["published_on"] = "2026-07-16"

        result = evaluate_bundle(with_candidate(mutate))
        self.assertIn("future_record", finding_codes(result))
        self.assertFalse(result["promotion_eligible"])

    def test_raw_memory_unknown_and_lineage_break_trigger_gates(self) -> None:
        def mutate(items):
            items[0]["qualified_evidence_ids"].append("e-unknown")
            items[0]["admitted_evidence_ids"].append("e-unknown")
            items[0]["memory_evidence_ids"].append("e-unknown")

        result = evaluate_bundle(with_candidate(mutate))
        self.assertIn("raw_memory_contamination", finding_codes(result))
        self.assertIn("evidence_lineage_break", finding_codes(result))

    def test_revoked_evidence_requires_declared_revoke_and_memory_removal(self) -> None:
        def mutate(items):
            items[0]["revoked_evidence_ids"] = []
            items[0]["memory_evidence_ids"].append("e-dev-stale")

        result = evaluate_bundle(with_candidate(mutate))
        self.assertIn("revocation_failure", finding_codes(result))
        taxonomy = result["failed_cases"][0]["taxonomy"]
        self.assertIn("revocation_failure", taxonomy)

    def test_memory_retention_and_false_revocation_reduce_measured_metrics(self) -> None:
        def lose_memory(items):
            items[0]["memory_evidence_ids"].remove("e-dev-support")
            items[0]["claims"][0]["evidence_ids"] = []

        retention = evaluate_bundle(with_candidate(lose_memory))
        useful = retention["candidate_scorecard"]["per_case"]["dev-target-mechanism"]["useful_evidence_recall"]
        self.assertEqual({"status": "measured", "value": 0.5, "numerator": 1, "denominator": 2}, useful)
        self.assertLess(retention["metric_deltas"]["useful_evidence_recall"]["improvement"], 0)
        self.assertIn("measured_metric_regression", finding_codes(retention))

        def false_revoke(items):
            items[0]["revoked_evidence_ids"].append("e-dev-support")

        revocation = evaluate_bundle(with_candidate(false_revoke))
        score = revocation["candidate_scorecard"]["per_case"]["dev-target-mechanism"]["revocation_accuracy"]
        self.assertEqual(2, score["numerator"])
        self.assertEqual(3, score["denominator"])
        self.assertLess(score["value"], 1.0)

    def test_cross_case_memory_leakage_is_zero_tolerance(self) -> None:
        def mutate(items):
            foreign = "e-frozen-support"
            items[0]["qualified_evidence_ids"].append(foreign)
            items[0]["admitted_evidence_ids"].append(foreign)
            items[0]["memory_evidence_ids"].append(foreign)

        result = evaluate_bundle(with_candidate(mutate))
        self.assertIn("cross_case_memory_leakage", finding_codes(result))

    def test_fabricated_citation_and_missing_claim_are_rejected(self) -> None:
        def fabricated(items):
            items[0]["claims"][0]["evidence_ids"].append("e-fabricated")

        fabricated_result = evaluate_bundle(with_candidate(fabricated))
        self.assertIn("unsupported_or_fabricated_citation", finding_codes(fabricated_result))

        def missing(items):
            items[0]["claims"] = []

        missing_result = evaluate_bundle(with_candidate(missing))
        self.assertIn("missing_required_claim", finding_codes(missing_result))
        metric = missing_result["candidate_scorecard"]["per_case"]["dev-target-mechanism"]["unsupported_claim_rate"]
        self.assertEqual("measured", metric["status"])
        self.assertEqual(1.0, metric["value"])

    def test_candidate_cannot_self_report_wrong_evidence_record_lineage(self) -> None:
        def mutate(items):
            items[0]["evidence_lineage"][0]["record_id"] = "r-dev-counter"
            items[0]["evidence_lineage"][0]["artifact"] = "artifact://eval/dev-counter"

        result = evaluate_bundle(with_candidate(mutate))
        self.assertIn("evidence_lineage_break", finding_codes(result))
        self.assertIn("claim_lineage_break", finding_codes(result))

    def test_retrieval_record_provenance_mismatch_is_diagnosed(self) -> None:
        def mutate(items):
            items[0]["retrieved_hits"][0]["artifact"] = "artifact://eval/wrong"

        result = evaluate_bundle(with_candidate(mutate))
        self.assertIn("retrieval_record_mismatch", finding_codes(result))

    def test_orphan_canonical_record_is_retrieval_mismatch(self) -> None:
        def mutate(items):
            orphan = copy.deepcopy(items[0]["records"][0])
            orphan["record_id"] = "r-orphan"
            orphan["artifact"] = "artifact://eval/orphan"
            items[0]["records"].append(orphan)

        result = evaluate_bundle(with_candidate(mutate))
        self.assertIn("retrieval_record_mismatch", finding_codes(result))

    def test_negative_primary_delta_and_coverage_mismatch_block(self) -> None:
        def regress(items):
            items[0]["retrieved_hits"] = items[0]["retrieved_hits"][1:]
            items[0]["records"] = items[0]["records"][1:]

        regression = evaluate_bundle(with_candidate(regress))
        self.assertIn("primary_metric_regression", finding_codes(regression))
        mismatch = evaluate_bundle(with_candidate(lambda items: None, drop_last=True))
        self.assertIn("case_coverage_mismatch", finding_codes(mismatch))
        self.assertTrue(all(item["status"] == "not_comparable" for item in mismatch["metric_deltas"].values()))

    def test_extra_case_coverage_mismatch_returns_stable_rejected_result(self) -> None:
        bundle = loaded()
        candidate = copy.deepcopy(list(bundle.candidate))
        extra = copy.deepcopy(candidate[0])
        extra["case_id"] = "unexpected-case"
        candidate.append(extra)
        mutated = EvalBundle(
            bundle.root, bundle.manifest, bundle.cases, bundle.baseline,
            tuple(candidate), bundle.asset_digests,
        )
        result = evaluate_bundle(mutated)
        self.assertEqual("completed", result["execution_completion"])
        self.assertFalse(result["promotion_eligible"])
        self.assertIn("case_coverage_mismatch", finding_codes(result))
        self.assertIn("unexpected_case_output", finding_codes(result))

    def test_metric_measured_case_coverage_mismatch_is_not_comparable(self) -> None:
        def mutate(items):
            items[0]["retrieved_hits"] = []
            items[0]["records"] = []
            items[0]["evidence_lineage"] = []
            items[0]["qualified_evidence_ids"] = []
            items[0]["admitted_evidence_ids"] = []
            items[0]["memory_evidence_ids"] = []
            items[0]["claims"] = []

        result = evaluate_bundle(with_candidate(mutate))
        delta = result["metric_deltas"]["retrieval_precision"]
        self.assertEqual("not_comparable", delta["status"])
        self.assertEqual("metric_measured_case_coverage_mismatch", delta["reason"])
        self.assertIn("metric_coverage_mismatch", finding_codes(result))
        self.assertIn("primary_metric_unmeasured_or_not_comparable", finding_codes(result))
        self.assertFalse(result["promotion_eligible"])

    def test_missing_metric_states_never_look_like_passes(self) -> None:
        result = evaluate_bundle(loaded())
        item = result["candidate_scorecard"]["per_case"]["frozen-biomarker"]["counterevidence_recall"]
        self.assertEqual({"status": "not_applicable", "reason": "no_counterevidence_oracle"}, item)
        self.assertNotIn("value", item)

    def test_committed_result_has_fixture_only_authority_and_claim_limits(self) -> None:
        committed = json.loads((PLUGIN_ROOT / "evals/research-eval-v1.result.json").read_text(encoding="utf-8"))
        self.assertEqual("completed", committed["execution_completion"])
        self.assertEqual("not_evaluated", committed["effect_outcome"])
        self.assertFalse(committed["promotion_eligible"])
        self.assertEqual("evaluator_fixture", committed["authority_scope"])
        self.assertEqual("no_independent_score_owner_root", committed["claim_limits"]["preregistration_authority"])
        with self.assertRaisesRegex(ValueError, "not promotion eligible"):
            verify_result(committed, require_promotion=True)


if __name__ == "__main__":
    unittest.main()
