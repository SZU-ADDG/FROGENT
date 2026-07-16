"""Locked identity and causal comparison tests for PLAN forward v3."""

import copy
import ast
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frogent_plugin.plan_eval_v3_assets import (  # noqa: E402
    ARMS, EVALUATOR_FILES, HARD_GATES, REPLICATES, _load_revision, _safe,
    _validate_envelopes, bundle_identity, load_plan_v3_bundle, worker_envelope, worker_receipt,
)
from frogent_plugin.plan_eval_v3_runner import (  # noqa: E402
    BLOCKERS, decide_effect, evaluate_plan_outputs, verify_plan_result,
)
from frogent_plugin.plan_eval_v3_schema import validate_plan_output  # noqa: E402

BULLET = ("- Under a query cap, reserve query events before allocating expansion queries: schedule an "
          "anchor-recovery query for every decision-critical evidence branch in each route needed to recover "
          "it, using the strongest known title, identifier, study name, or dated action; schedule a distinct "
          "challenge query for each high-impact claim family to seek null, conflicting, or limiting evidence. "
          "If the cap forces a trade-off, remove expansion queries first.")


class PlanEvalV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = Path("evals/plan-forward-v3.manifest.json")
        cls.bundle = load_plan_v3_bundle(ROOT, cls.manifest)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "evals")
        self.temp_root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def output(self, case: str = "PLAN-01", arm: str = "skill_a", rep: str = "17",
               query: str = "LRRK2 Parkinson mutation") -> dict:
        receipt = worker_receipt(self.bundle, case, arm, rep)
        return {"case_id": case, "profile": arm, "replicate_label": rep,
                "worker_input_digest": receipt["worker_input_digest"], "execution_status": "completed",
                "question_frame": "Test plan", "as_of": "2024-12-31", "source_map": ["pubmed"],
                "concept_blocks": [{"block_id": "target", "terms": ["LRRK2", "Parkinson"]}],
                "queries": [{"query_id": "q1", "source": "pubmed", "wave": "sentinel",
                             "query": query, "purpose": "test"}],
                "inclusion_criteria": ["eligible"], "exclusion_criteria": ["ineligible"],
                "stop_rules": ["challenge search"], "coverage_gaps": []}

    def outputs(self) -> list[dict]:
        return [self.output(case, arm, rep) for case in ("PLAN-01", "PLAN-02")
                for arm in ARMS for rep in REPLICATES]

    def paired_outputs(self, outcome: str) -> list[dict]:
        locators = {"PLAN-01": {"good": "15541308", "bad": "21983832"},
                    "PLAN-02": {"good": "35081280", "bad": "28467869"}}
        values = []
        for case in ("PLAN-01", "PLAN-02"):
            for arm in ARMS:
                quality = "good"
                if outcome == "improved": quality = "good" if arm == "skill_b" else "bad"
                if outcome == "regression": quality = "bad" if arm == "skill_b" else "good"
                for rep in REPLICATES:
                    values.append(self.output(case, arm, rep, locators[case][quality]))
        if outcome == "not_comparable":
            values[-1]["execution_status"] = "failed"
        return values

    def test_snapshots_have_exact_single_bullet_delta_and_shared_reference(self) -> None:
        current = (ROOT / "evals/plan-forward-v3.current-skill.md").read_text()
        candidate = (ROOT / "evals/plan-forward-v3.candidate-skill.md").read_text()
        self.assertEqual(current.replace("- Record unavailable sources as coverage gaps.",
                                         "- Record unavailable sources as coverage gaps.\n" + BULLET), candidate)
        self.assertEqual(1, candidate.count(BULLET))
        active = (ROOT / "skills/plan-literature-search/SKILL.md").read_bytes()
        self.assertEqual(active, (ROOT / "evals/plan-forward-v3.current-skill.md").read_bytes())
        reference = (ROOT / "skills/plan-literature-search/references/query-strategy.md").read_bytes()
        self.assertEqual(reference, (ROOT / "evals/plan-forward-v3.query-strategy.md").read_bytes())

    def test_locked_pack_has_12_unique_typed_envelopes_and_no_result(self) -> None:
        self.assertEqual("locked", self.bundle.manifest["pack_status"])
        receipts = [worker_receipt(self.bundle, case, arm, rep) for case in ("PLAN-01", "PLAN-02")
                    for arm in ARMS for rep in REPLICATES]
        self.assertEqual(12, len({item["worker_input_digest"] for item in receipts}))
        envelopes = [worker_envelope(self.bundle, item["case_id"], item["profile"], item["replicate_label"])
                     for item in receipts]
        self.assertEqual(12, len({hashlib.sha256(item).hexdigest() for item in envelopes}))
        self.assertEqual({"skill_a": "baseline_current", "skill_b": "candidate"},
                         self.bundle.manifest["role_mapping"])
        self.assertFalse((ROOT / "evals/plan-forward-v3.outputs").exists())
        self.assertFalse((ROOT / "evals/plan-forward-v3.result.json").exists())

    def test_envelope_assets_match_reconstruction_and_reject_tamper(self) -> None:
        for key, spec in self.bundle.manifest["envelopes"].items():
            case, arm, rep = key.split("|")
            raw = (ROOT / spec["path"]).read_bytes()
            self.assertEqual(spec["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(raw, worker_envelope(self.bundle, case, arm, rep))
            self.assertTrue(raw.endswith(b"\n"))
            self.assertFalse(raw.endswith(b"\n\n"))
        sandbox = self.temp_root / "envelope-sandbox"
        target = sandbox / "evals/plan-forward-v3.envelopes"
        target.parent.mkdir(parents=True); shutil.copytree(ROOT / "evals/plan-forward-v3.envelopes", target)
        copied = target / "PLAN-01-skill_a-17.txt"
        copied.write_bytes(copied.read_bytes() + b"tamper")
        with self.assertRaisesRegex(ValueError, "envelope identity mismatch"):
            _validate_envelopes(replace(self.bundle, root=sandbox))

    def test_absolute_parent_and_symlink_escape_paths_fail_closed(self) -> None:
        for path in (Path("/etc/hosts"), Path("../outside")):
            with self.assertRaises(ValueError):
                _safe(ROOT, path)
        link = self.temp_root / "escape"
        link.symlink_to("/etc/hosts")
        with self.assertRaises(ValueError):
            _safe(ROOT, link.relative_to(ROOT))

    def test_schema_identity_policy_and_pairing(self) -> None:
        value = self.output()
        validate_plan_output(value, self.bundle)
        bad = copy.deepcopy(value); bad["worker_input_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "worker input identity"):
            validate_plan_output(bad, self.bundle)
        policy = self.output()
        policy["queries"] = [dict(policy["queries"][0], query_id=f"q{index}") for index in range(13)]
        result = evaluate_plan_outputs(self.bundle, [policy])
        self.assertEqual("rejected", result["effect_outcome"])
        self.assertIn("query_budget_exceeded", result["runs"][0]["findings"])
        unsupported = self.output(); unsupported["source_map"] = ["fda_regulatory"]
        unsupported["queries"][0]["source"] = "fda_regulatory"
        run = evaluate_plan_outputs(self.bundle, [unsupported])
        self.assertIn("unsupported_source", run["runs"][0]["findings"])
        self.assertEqual("completed", run["runs"][0]["plan"]["execution_status"])
        self.assertIn("pair_coverage_not_comparable", result["findings"])

    def test_synthetic_flat_missing_failed_and_exact_verify(self) -> None:
        values = self.outputs()
        result = evaluate_plan_outputs(self.bundle, values, require_complete=True)
        self.assertIn(result["effect_outcome"], {"flat", "rejected"})
        self.assertFalse(result["promotion_eligible"])
        self.assertEqual(self.bundle.manifest["role_mapping"], result["role_mapping"])
        verify_plan_result(self.bundle, values, result)
        missing = evaluate_plan_outputs(self.bundle, values[:-1])
        self.assertEqual("incomplete", missing["worker_completion"]["state"])
        failed = copy.deepcopy(values); failed[0]["execution_status"] = "failed"
        self.assertEqual("failed", evaluate_plan_outputs(self.bundle, failed)["worker_completion"]["state"])
        tampered = copy.deepcopy(result); tampered["promotion_eligible"] = True
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_plan_result(self.bundle, values, tampered)

    def test_effect_gate_distinguishes_improved_flat_regression_and_missing(self) -> None:
        measured = {metric: {"state": "measured", "delta": 0.0}
                    for metric in self.bundle.manifest.get("registered_metrics", ())}
        if not measured:
            from frogent_plugin.plan_eval_schema import METRICS
            measured = {metric: {"state": "measured", "delta": 0.0} for metric in METRICS}
        comparisons = [{"state": "comparable", "deltas": copy.deepcopy(measured)} for _ in range(6)]
        self.assertEqual("flat", decide_effect(comparisons, []))
        comparisons[0]["deltas"]["anchor_recall"]["delta"] = 0.25
        self.assertEqual("improved", decide_effect(comparisons, []))
        self.assertEqual("rejected", decide_effect(comparisons, ["quality_metric_regression"]))
        self.assertEqual("rejected", decide_effect(comparisons[:-1], []))

    def test_full_replay_scorecard_comparison_covers_all_effect_outcomes(self) -> None:
        improved = evaluate_plan_outputs(self.bundle, self.paired_outputs("improved"), require_complete=True)
        self.assertEqual("improved", improved["effect_outcome"])
        self.assertEqual(6, len(improved["comparisons"]))
        self.assertTrue(all(item["state"] == "comparable" for item in improved["comparisons"]))
        self.assertTrue(all(item["deltas"]["anchor_recall"]["delta"] > 0
                            for item in improved["comparisons"]))
        self.assertTrue(all(run["scorecard"]["anchor_recall"]["state"] == "measured"
                            for run in improved["runs"]))
        flat = evaluate_plan_outputs(self.bundle, self.paired_outputs("flat"), require_complete=True)
        self.assertEqual("flat", flat["effect_outcome"])
        regression = evaluate_plan_outputs(self.bundle, self.paired_outputs("regression"), require_complete=True)
        self.assertEqual("rejected", regression["effect_outcome"])
        self.assertIn("quality_metric_regression", regression["findings"])
        incomplete = evaluate_plan_outputs(self.bundle, self.paired_outputs("not_comparable"))
        self.assertEqual("rejected", incomplete["effect_outcome"])
        self.assertIn("metric_coverage_not_comparable", incomplete["findings"])
        self.assertEqual("failed", incomplete["worker_completion"]["state"])

    def test_manifest_hard_gates_are_the_runner_blocker_source(self) -> None:
        self.assertIs(BLOCKERS, HARD_GATES)
        self.assertEqual(list(BLOCKERS), self.bundle.manifest["hard_gates"])
        for blocker in BLOCKERS:
            self.assertEqual("rejected", decide_effect([], [blocker]))

    def test_manifest_path_redirect_revision_key_and_asset_tamper_fail_closed(self) -> None:
        manifest = json.loads((ROOT / self.manifest).read_bytes())
        redirected = copy.deepcopy(manifest)
        redirected["assets"]["current_skill"]["path"] = redirected["assets"]["candidate_skill"]["path"]
        with self.assertRaisesRegex(ValueError, "asset path identity"):
            load_plan_v3_bundle(ROOT, self._write_json("redirect.json", redirected))
        bad_digest = copy.deepcopy(manifest); bad_digest["assets"]["current_skill"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "asset digest mismatch"):
            load_plan_v3_bundle(ROOT, self._write_json("tamper.json", bad_digest))
        sandbox = self._revision_sandbox()
        revision_path = sandbox / "evals/plan-forward-v3.evaluator-revision.json"
        revision = json.loads(revision_path.read_bytes())
        revision["files"]["frogent_plugin/plan_eval_v3_schema.py"]["path"] = (
            "frogent_plugin/plan_eval_v3_runner.py")
        revision_path.write_text(json.dumps(revision, sort_keys=True), encoding="utf-8")
        spec = {"path": "evals/plan-forward-v3.evaluator-revision.json",
                "sha256": hashlib.sha256(revision_path.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "key path mismatch"):
            _load_revision(sandbox, spec)

    def test_recursive_cli_runtime_import_closure_is_revision_bound(self) -> None:
        pending = {"frogent_plugin/__init__.py", "frogent_plugin/plan_eval_v3_assets.py",
                   "frogent_plugin/plan_eval_v3_schema.py", "frogent_plugin/plan_eval_v3_runner.py",
                   "scripts/run_plan_forward_v3_eval.py"}
        closure = set()
        while pending:
            relative = pending.pop()
            if relative in closure:
                continue
            closure.add(relative)
            tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                pending.update(candidate for candidate in self._local_imports(relative, node)
                               if (ROOT / candidate).is_file())
        self.assertTrue(closure <= EVALUATOR_FILES)
        self.assertIn("frogent_plugin/plan_eval_v2_replay.py", closure)
        self.assertIn("frogent_plugin/eval_schema.py", closure)

    def test_cli_locked_receipt_and_envelope_are_exact(self) -> None:
        cli = ROOT / "scripts/run_plan_forward_v3_eval.py"
        base = [sys.executable, str(cli)]
        locked = subprocess.run(base + ["validate-preregistration", str(self.manifest)], cwd=ROOT,
                                check=True, capture_output=True, text=True)
        self.assertEqual({"effect_outcome": "not_evaluated", "fresh_workers": 0,
                          "pack_status": "locked", "promotion_eligible": False}, json.loads(locked.stdout))
        args = [str(self.manifest), "--case", "PLAN-02", "--profile", "skill_b", "--replicate", "43"]
        receipt = subprocess.run(base + ["worker-receipt"] + args, cwd=ROOT, check=True,
                                 capture_output=True, text=True)
        self.assertEqual(worker_receipt(self.bundle, "PLAN-02", "skill_b", "43"), json.loads(receipt.stdout))
        envelope = subprocess.run(base + ["worker-envelope"] + args, cwd=ROOT, check=True,
                                  capture_output=True)
        self.assertEqual(worker_envelope(self.bundle, "PLAN-02", "skill_b", "43"), envelope.stdout)

    def test_v1_v2_frozen_hashes_stay_fixed(self) -> None:
        expected = {
            "evals/plan-forward-v1.manifest.json": "010dc99061eb50e28cfeaeb164542df197243f6446cd55254a3586a2646b4e9f",
            "evals/plan-forward-v1.result.json": "2f6803824b7f82b54a16c19b840c5140ab7ccc8155836641dafd5b4f3a4d5473",
            "evals/plan-forward-v2.manifest.json": "6d0dc61255298dfff58b1f5cbb9a6440c401aaf37c9c4cb7e43263c1a3d7f813",
            "evals/plan-forward-v2.result.json": "f541ce196c803f7182aef8ea91277ab7f245acee2b3cfb93e7bd751973a1c3a9",
        }
        for relative, digest in expected.items():
            self.assertEqual(digest, hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())
        self.assertEqual(64, len(bundle_identity(self.bundle)))

    def _revision_sandbox(self) -> Path:
        sandbox = self.temp_root / "revision-sandbox"
        for relative in EVALUATOR_FILES:
            target = sandbox / relative; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        revision = sandbox / "evals/plan-forward-v3.evaluator-revision.json"
        revision.parent.mkdir(parents=True); shutil.copy2(ROOT / "evals/plan-forward-v3.evaluator-revision.json", revision)
        return sandbox

    @staticmethod
    def _local_imports(relative: str, node: ast.ImportFrom) -> tuple[str, ...]:
        if node.level:
            base = ROOT / Path(relative).parent
            for _ in range(node.level - 1):
                base = base.parent
            root = ROOT.resolve()
            modules = ([node.module] if node.module else [item.name for item in node.names])
            paths = [(base / (module.replace(".", "/") + ".py")).resolve() for module in modules]
            return tuple(path.relative_to(root).as_posix() for path in paths if path.is_relative_to(root))
        if node.module and node.module.startswith("frogent_plugin."):
            return (node.module.replace(".", "/") + ".py",)
        return ()

    def _write_json(self, name: str, value: object) -> Path:
        path = self.temp_root / name
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        return path.relative_to(ROOT)


if __name__ == "__main__":
    unittest.main()
