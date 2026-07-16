"""Integrity, calibration, and mutation tests for PLAN forward v2."""

import copy
import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

sys.dont_write_bytecode = True
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin.plan_eval_assets import load_plan_bundle  # noqa: E402
from frogent_plugin.plan_eval_runner import verify_plan_result as verify_v1_result  # noqa: E402
from frogent_plugin.plan_eval_v2_assets import (  # noqa: E402
    EVALUATOR_FILES, bundle_identity, load_plan_v2_bundle, worker_input_digest,
    worker_receipt,
)
from frogent_plugin.plan_eval_v2_replay import _matches, score_plan  # noqa: E402
from frogent_plugin.plan_eval_v2_runner import evaluate_plan_outputs, verify_plan_result  # noqa: E402
from frogent_plugin.plan_eval_v2_schema import group_matches, query_group_matches, validate_plan_output  # noqa: E402


class PlanEvalV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest_path = Path("evals/plan-forward-v2.manifest.json")
        self.bundle = load_plan_v2_bundle(PLUGIN_ROOT, self.manifest_path)
        self.temp = tempfile.TemporaryDirectory(dir=PLUGIN_ROOT / "evals")
        self.temp_root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def output(self, case: str = "PLAN-01", profile: str = "single_skill",
               replicate: str = "17", status: str = "completed") -> dict:
        constraint = self.bundle.constraints[case]
        value = {
            "case_id": case, "profile": profile, "replicate_label": replicate,
            "worker_input_digest": worker_input_digest(self.bundle, case, profile, replicate),
            "execution_status": status, "question_frame": "Candidate-visible test plan",
            "as_of": "2024-12-31", "source_map": [constraint["available_source_routes"][0]],
            "concept_blocks": [{"block_id": "scope", "terms": ["LRRK2", "Parkinson"]}],
            "queries": [{"query_id": "q1", "source": constraint["available_source_routes"][0],
                         "wave": "sentinel", "query": "LRRK2 Parkinson* mutation*",
                         "purpose": "test retrieval"}],
            "inclusion_criteria": ["eligible evidence"],
            "exclusion_criteria": ["ineligible evidence"],
            "stop_rules": ["challenge search then two consecutive expansion passes add no decision relevant evidence"],
            "coverage_gaps": [],
        }
        return value

    def all_outputs(self) -> list[dict]:
        return [self.output(case, profile, replicate) for case in ("PLAN-01", "PLAN-02")
                for profile in ("no_skill", "single_skill") for replicate in ("17", "29", "43")]

    def test_locked_pack_is_pending_fresh_workers_and_has_exact_constraints(self) -> None:
        self.assertEqual("locked", self.bundle.manifest["pack_status"])
        self.assertEqual(["pubmed"], self.bundle.constraints["PLAN-01"]["available_source_routes"])
        self.assertEqual(12, self.bundle.constraints["PLAN-01"]["max_query_events"])
        self.assertEqual(["pubmed", "clinicaltrials_gov", "fda_regulatory"],
                         self.bundle.constraints["PLAN-02"]["available_source_routes"])
        self.assertEqual(16, self.bundle.constraints["PLAN-02"]["max_query_events"])
        self.assertFalse((PLUGIN_ROOT / "evals/plan-forward-v2.outputs").exists())
        self.assertFalse((PLUGIN_ROOT / "evals/plan-forward-v2.result.json").exists())

    def test_worker_receipts_bind_case_constraints_and_are_unique(self) -> None:
        receipts = [worker_receipt(self.bundle, case, profile, replicate)
                    for case in ("PLAN-01", "PLAN-02") for profile in ("no_skill", "single_skill")
                    for replicate in ("17", "29", "43")]
        self.assertEqual(12, len({item["worker_input_digest"] for item in receipts}))
        self.assertTrue(all(item["constraint"]["case_id"] == item["case_id"] for item in receipts))
        changed = dict(self.bundle.constraints)
        changed["PLAN-01"] = dict(changed["PLAN-01"], max_query_events=11)
        self.assertNotEqual(
            worker_input_digest(self.bundle, "PLAN-01", "no_skill", "17"),
            worker_input_digest(replace(self.bundle, constraints=changed), "PLAN-01", "no_skill", "17"),
        )
        prompt = (PLUGIN_ROOT / "evals/plan-forward-v2.worker-common.txt").read_text(encoding="utf-8")
        for token in ("available_source_routes", "max_query_events", "less than or equal", "candidate constraint"):
            self.assertIn(token, prompt)

    def test_candidate_policy_violations_are_accepted_audited_and_rejected(self) -> None:
        wrong_route = self.output()
        wrong_route["source_map"] = ["fda_regulatory"]
        wrong_route["queries"][0]["source"] = "fda_regulatory"
        validate_plan_output(wrong_route, self.bundle)
        route_values = self.all_outputs()
        route_values[3] = wrong_route
        route_result = evaluate_plan_outputs(self.bundle, route_values, require_complete=True)
        route_run = next(run for run in route_result["runs"] if
                         (run["case_id"], run["profile"], run["replicate_label"]) ==
                         ("PLAN-01", "single_skill", "17"))
        self.assertIn("unsupported_source", route_run["findings"])
        self.assertEqual("fda_regulatory", route_run["plan"]["queries"][0]["source"])
        self.assertEqual("rejected", route_result["effect_outcome"])
        self.assertEqual("completed", route_result["worker_completion"]["state"])
        self.assertTrue(all(receipt["status"] == "accepted" for receipt in route_result["input_receipts"]))
        verify_plan_result(self.bundle, route_values, route_result)
        over_budget = self.output()
        over_budget["queries"] = [dict(over_budget["queries"][0], query_id=f"q{index}") for index in range(13)]
        validate_plan_output(over_budget, self.bundle)
        budget_values = self.all_outputs()
        budget_values[3] = over_budget
        budget_result = evaluate_plan_outputs(self.bundle, budget_values, require_complete=True)
        budget_run = next(run for run in budget_result["runs"] if
                          (run["case_id"], run["profile"], run["replicate_label"]) ==
                          ("PLAN-01", "single_skill", "17"))
        self.assertIn("query_budget_exceeded", budget_run["findings"])
        self.assertEqual(13, len(budget_run["plan"]["queries"]))
        self.assertEqual("rejected", budget_result["effect_outcome"])
        self.assertEqual("completed", budget_result["worker_completion"]["state"])
        verify_plan_result(self.bundle, budget_values, budget_result)

    def test_schema_contract_and_worker_identity_remain_fail_closed(self) -> None:
        mismatch = self.output()
        mismatch["worker_input_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "worker input identity"):
            validate_plan_output(mismatch, self.bundle)
        for mutation in (
            lambda value: value.update(extra_field=True),
            lambda value: value.update(as_of="2025-01-01"),
            lambda value: value["queries"][0].update(wave="unknown"),
            lambda value: value["queries"][0].update(query=""),
            lambda value: value.update(gold={}),
        ):
            value = self.output()
            mutation(value)
            with self.assertRaises((KeyError, TypeError, ValueError)):
                validate_plan_output(value, self.bundle)

    def test_terminal_truncation_is_query_only_and_field_tag_aware(self) -> None:
        positives = (("Parkinson*[Title/Abstract]", "Parkinson"),
                     ("mutation*[Title/Abstract]", "mutations"),
                     ("substrate*", "substrates"), ("phosphorylat*", "phosphorylation"),
                     ("LRRK2 AND Parkinson*[Title/Abstract] OR mutation*", "Parkinson"))
        for query, alias in positives:
            self.assertTrue(query_group_matches(query, [alias]))
        self.assertFalse(group_matches(["Parkinson*"], ["Parkinson"]))
        for query in ("*kinson", "Park*son", "*", "park"):
            self.assertFalse(query_group_matches(query, ["Parkinson"]))
        self.assertFalse(query_group_matches("NOT Parkinson*", ["Parkinson"]))
        negated = {"query_id": "negated", "source": "pubmed", "wave": "challenge",
                   "query": "LRRK2 AND NOT Parkinson* AND mutation*", "purpose": "negative clause"}
        self.assertEqual((), _matches(negated, "PLAN-01", self.bundle.corpus))

    def test_v1_plan01_queries_restore_expected_records_under_v2_calibration(self) -> None:
        expected = {"PLAN01-PM-15541308", "PLAN01-PM-15541309", "PLAN01-PM-26824392",
                    "PLAN01-PM-26062626", "PLAN01-PM-29855356"}
        recovered = set()
        for path in sorted((PLUGIN_ROOT / "evals/plan-forward-v1.outputs").glob("PLAN-01-single_skill-*.json")):
            output = json.loads(path.read_bytes())
            for query in output["queries"]:
                if "*" in query["query"]:
                    recovered.update(record["record_id"] for record in _matches(query, "PLAN-01", self.bundle.corpus))
        self.assertTrue(expected <= recovered)

    def test_v2_stop_requirements_have_discriminating_matches_on_v1_plans(self) -> None:
        measured = []
        for path in sorted((PLUGIN_ROOT / "evals/plan-forward-v1.outputs").glob("*.json")):
            output = json.loads(path.read_bytes())
            oracle = self.bundle.oracles[output["case_id"]]
            metric = score_plan(output, oracle, [], ())["stop_rule_coverage"]
            measured.append(metric["numerator"])
            self.assertGreater(metric["numerator"], 0)
            self.assertLessEqual(metric["numerator"], metric["denominator"])
        self.assertGreater(len(set(measured)), 1)

    def test_constraint_unknown_fields_and_asset_paths_fail_closed(self) -> None:
        constraints = json.loads((PLUGIN_ROOT / "evals/plan-forward-v2.candidate-constraints.json").read_bytes())
        constraints[0]["oracle_record_ids"] = []
        with self._mutated_bound_asset("candidate_constraints", constraints) as manifest:
            with self.assertRaisesRegex(ValueError, "fields must match schema exactly"):
                load_plan_v2_bundle(PLUGIN_ROOT, manifest)
        value = json.loads((PLUGIN_ROOT / self.manifest_path).read_bytes())
        value["assets"]["candidate_constraints"] = {"path": "/etc/hosts", "sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "path identity mismatch"):
            load_plan_v2_bundle(PLUGIN_ROOT, self._write_json("absolute.json", value))
        value["assets"]["candidate_constraints"]["path"] = "../outside.json"
        with self.assertRaisesRegex(ValueError, "path identity mismatch"):
            load_plan_v2_bundle(PLUGIN_ROOT, self._write_json("parent.json", value))
        link = self.temp_root / "constraint-link.json"
        link.symlink_to("/etc/hosts")
        value["assets"]["candidate_constraints"] = {
            "path": str(link.relative_to(PLUGIN_ROOT)),
            "sha256": hashlib.sha256(Path("/etc/hosts").read_bytes()).hexdigest(),
        }
        with self.assertRaisesRegex(ValueError, "path identity mismatch"):
            load_plan_v2_bundle(PLUGIN_ROOT, self._write_json("symlink.json", value))

    def test_asset_and_evaluator_byte_tamper_fail_closed(self) -> None:
        constraints = json.loads((PLUGIN_ROOT / "evals/plan-forward-v2.candidate-constraints.json").read_bytes())
        constraints[0]["max_query_events"] = 11
        with self._mutated_bound_asset("candidate_constraints", constraints) as manifest:
            with self.assertRaisesRegex(ValueError, "budget differs"):
                load_plan_v2_bundle(PLUGIN_ROOT, manifest)
        revision = json.loads((PLUGIN_ROOT / "evals/plan-forward-v2.evaluator-revision.json").read_bytes())
        self.assertEqual(EVALUATOR_FILES, set(revision["files"]))
        for relative in ("frogent_plugin/__init__.py", "frogent_plugin/catalog.py",
                         "frogent_plugin/plan_eval_v2_replay.py"):
            source = PLUGIN_ROOT / relative
            original = source.read_bytes()
            source.write_bytes(original + b" ")
            try:
                with self.assertRaisesRegex(ValueError, "evaluator file digest mismatch"):
                    load_plan_v2_bundle(PLUGIN_ROOT, self.manifest_path)
            finally:
                source.write_bytes(original)

    def test_evaluator_revision_key_path_redirect_fails_closed(self) -> None:
        revision_path = PLUGIN_ROOT / "evals/plan-forward-v2.evaluator-revision.json"
        original = revision_path.read_bytes()
        revision = json.loads(original)
        name = "frogent_plugin/plan_eval_v2_replay.py"
        redirected = "frogent_plugin/plan_eval_v2_runner.py"
        revision["files"][name] = copy.deepcopy(revision["files"][redirected])
        revision_path.write_text(json.dumps(revision, sort_keys=True), encoding="utf-8")
        try:
            manifest = json.loads((PLUGIN_ROOT / self.manifest_path).read_bytes())
            manifest["evaluator_identity"]["sha256"] = hashlib.sha256(revision_path.read_bytes()).hexdigest()
            path = self._write_json("redirected-revision.json", manifest)
            with self.assertRaisesRegex(ValueError, "key and path identity mismatch"):
                load_plan_v2_bundle(PLUGIN_ROOT, path)
        finally:
            revision_path.write_bytes(original)

    def test_package_eager_import_graph_is_fully_bound(self) -> None:
        closure, pending = set(), ["__init__.py"]
        package = PLUGIN_ROOT / "frogent_plugin"
        while pending:
            relative = pending.pop()
            if relative in closure:
                continue
            closure.add(relative)
            tree = ast.parse((package / relative).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.level:
                    continue
                candidates = ([node.module.replace(".", "/") + ".py"] if node.module else
                              [alias.name.replace(".", "/") + ".py" for alias in node.names])
                pending.extend(item for item in candidates if (package / item).is_file())
        bound = {Path(item).relative_to("frogent_plugin").as_posix()
                 for item in EVALUATOR_FILES if item.startswith("frogent_plugin/")}
        self.assertTrue(closure <= bound)

    def test_duplicate_same_and_conflicting_constraints_fail_closed(self) -> None:
        constraints = json.loads((PLUGIN_ROOT / "evals/plan-forward-v2.candidate-constraints.json").read_bytes())
        same = [copy.deepcopy(constraints[0]), copy.deepcopy(constraints[0])]
        with self._mutated_bound_asset("candidate_constraints", same) as manifest:
            with self.assertRaisesRegex(ValueError, "constraint case IDs"):
                load_plan_v2_bundle(PLUGIN_ROOT, manifest)
        conflicting = [copy.deepcopy(constraints[0]), copy.deepcopy(constraints[0])]
        conflicting[1]["available_source_routes"] = ["fda_regulatory"]
        conflicting[1]["max_query_events"] = 99
        with self._mutated_bound_asset("candidate_constraints", conflicting) as manifest:
            with self.assertRaisesRegex(ValueError, "constraint case IDs"):
                load_plan_v2_bundle(PLUGIN_ROOT, manifest)
        with self._mutated_bound_asset("candidate_constraints", [constraints[0], "PLAN-02"]) as manifest:
            with self.assertRaisesRegex(ValueError, "must be an object"):
                load_plan_v2_bundle(PLUGIN_ROOT, manifest)

    def test_negative_results_and_exact_complete_verify(self) -> None:
        missing = evaluate_plan_outputs(self.bundle, [self.output()])
        self.assertEqual("incomplete", missing["worker_completion"]["state"])
        self.assertEqual("rejected", missing["effect_outcome"])
        invalid = self.output()
        invalid["worker_input_digest"] = "0" * 64
        rejected = evaluate_plan_outputs(self.bundle, [invalid])
        self.assertEqual(1, rejected["invalid_outputs"]["count"])
        failed = self.all_outputs()
        failed[0]["execution_status"] = "failed"
        failed_result = evaluate_plan_outputs(self.bundle, failed)
        self.assertEqual("failed", failed_result["worker_completion"]["state"])
        values = self.all_outputs()
        result = evaluate_plan_outputs(self.bundle, values, require_complete=True)
        verify_plan_result(self.bundle, values, result)
        self.assertFalse(result["promotion_eligible"])
        tampered = copy.deepcopy(result)
        tampered["effect_outcome"] = "improved"
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_plan_result(self.bundle, values, tampered)

    def test_cli_preregistration_and_receipt_are_candidate_safe(self) -> None:
        cli = PLUGIN_ROOT / "scripts/run_plan_forward_v2_eval.py"
        locked = subprocess.run([sys.executable, str(cli), "validate-preregistration", str(self.manifest_path)],
                                cwd=PLUGIN_ROOT, check=True, capture_output=True, text=True)
        self.assertEqual("not_evaluated", json.loads(locked.stdout)["effect_outcome"])
        receipt = subprocess.run([sys.executable, str(cli), "worker-receipt", str(self.manifest_path),
                                  "--case", "PLAN-01", "--profile", "no_skill", "--replicate", "17"],
                                 cwd=PLUGIN_ROOT, check=True, capture_output=True, text=True)
        value = json.loads(receipt.stdout)
        self.assertEqual(["pubmed"], value["constraint"]["available_source_routes"])
        self.assertFalse(any(token in json.dumps(value).lower() for token in ("record_id", "match_group", "relevance")))

    def test_cli_validate_and_ingest_preserve_policy_violation(self) -> None:
        cli = PLUGIN_ROOT / "scripts/run_plan_forward_v2_eval.py"
        value = self.output()
        value["source_map"] = ["fda_regulatory"]
        value["queries"][0]["source"] = "fda_regulatory"
        source = self._write_json("policy-violation.json", value)
        validate = [sys.executable, str(cli), "validate-output", str(self.manifest_path), str(source)]
        subprocess.run(validate, cwd=PLUGIN_ROOT, check=True, capture_output=True, text=True)
        output_dir = PLUGIN_ROOT / "evals/plan-forward-v2.outputs"
        target = output_dir / "PLAN-01-single_skill-17.json"
        self.assertFalse(output_dir.exists())
        try:
            ingest = [sys.executable, str(cli), "ingest", str(self.manifest_path), str(source)]
            subprocess.run(ingest, cwd=PLUGIN_ROOT, check=True, capture_output=True, text=True)
            stored = json.loads(target.read_bytes())
            self.assertEqual("fda_regulatory", stored["queries"][0]["source"])
        finally:
            if target.exists():
                target.unlink()
            if output_dir.exists():
                output_dir.rmdir()

    def test_cli_complete_result_has_asset_bound_exact_verify(self) -> None:
        cli = PLUGIN_ROOT / "scripts/run_plan_forward_v2_eval.py"
        output_paths = [self._write_json(f"output-{index:02d}.json", value)
                        for index, value in enumerate(self.all_outputs())]
        result_path = self.temp_root / "result.json"
        relative_result = result_path.relative_to(PLUGIN_ROOT)
        command = [sys.executable, str(cli), "evaluate", str(self.manifest_path),
                   *(str(path) for path in output_paths), "--result", str(relative_result)]
        subprocess.run(command, cwd=PLUGIN_ROOT, check=True, capture_output=True, text=True)
        verify = [sys.executable, str(cli), "verify-result", str(self.manifest_path),
                  *(str(path) for path in output_paths), "--expected", str(relative_result)]
        subprocess.run(verify, cwd=PLUGIN_ROOT, check=True, capture_output=True, text=True)
        tampered = json.loads(result_path.read_bytes())
        tampered["promotion_eligible"] = True
        result_path.write_text(json.dumps(tampered), encoding="utf-8")
        rejected = subprocess.run(verify, cwd=PLUGIN_ROOT, capture_output=True, text=True)
        self.assertNotEqual(0, rejected.returncode)

    def test_v1_frozen_identity_and_exact_result_remain_unchanged(self) -> None:
        expected = {
            "evals/plan-forward-v1.manifest.json": "010dc99061eb50e28cfeaeb164542df197243f6446cd55254a3586a2646b4e9f",
            "evals/plan-forward-v1.evaluator-revision.json": "44dd1cd0156f3a038b138a6dcf7666642ba9006d0f3c20c0aadeb192eecc7d1e",
            "evals/plan-forward-v1.result.json": "2f6803824b7f82b54a16c19b840c5140ab7ccc8155836641dafd5b4f3a4d5473",
        }
        for relative, digest in expected.items():
            self.assertEqual(digest, hashlib.sha256((PLUGIN_ROOT / relative).read_bytes()).hexdigest())
        bundle = load_plan_bundle(PLUGIN_ROOT, Path("evals/plan-forward-v1.manifest.json"))
        paths = sorted((PLUGIN_ROOT / "evals/plan-forward-v1.outputs").glob("*.json"))
        values = [json.loads(path.read_bytes()) for path in paths]
        metadata = [{"identity": str(path.relative_to(PLUGIN_ROOT)),
                     "digest": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]
        result = json.loads((PLUGIN_ROOT / "evals/plan-forward-v1.result.json").read_bytes())
        verify_v1_result(bundle, values, result, input_metadata=metadata)

    @contextmanager
    def _mutated_bound_asset(self, name: str, value: object):
        manifest = json.loads((PLUGIN_ROOT / self.manifest_path).read_bytes())
        asset = PLUGIN_ROOT / manifest["assets"][name]["path"]
        original = asset.read_bytes()
        asset.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        try:
            manifest["assets"][name]["sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
            yield self._write_json(f"manifest-{name}.json", manifest)
        finally:
            asset.write_bytes(original)

    def _write_json(self, name: str, value: object) -> Path:
        path = self.temp_root / name
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        return path.relative_to(PLUGIN_ROOT)


if __name__ == "__main__":
    unittest.main()
