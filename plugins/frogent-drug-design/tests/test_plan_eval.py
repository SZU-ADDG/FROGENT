"""Integrity and mutation tests for the PLAN forward eval boundary."""

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path

sys.dont_write_bytecode = True
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin.plan_eval_assets import (  # noqa: E402
    EVALUATOR_FILES, contained_directory, load_plan_bundle, worker_input_digest,
    write_contained_exclusive,
)
from frogent_plugin.plan_eval_replay import replay_plan, replay_provenance_findings  # noqa: E402
from frogent_plugin.plan_eval_runner import evaluate_plan_outputs, verify_plan_result  # noqa: E402
from frogent_plugin.plan_eval_schema import (  # noqa: E402
    CLAIM_LIMITS, METRICS, PRIMARY_METRICS, group_matches, normalize_lexical,
    validate_plan_output,
)


class PlanEvalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=PLUGIN_ROOT / "evals")
        self.root = Path(self.temp.name)
        self.cases = [
            {"case_id": "PLAN-01", "task": "Test-only task one", "as_of": "2025-01-15"},
            {"case_id": "PLAN-02", "task": "Test-only task two", "as_of": "2025-01-15"},
        ]
        self.oracles = [self.oracle(case["case_id"]) for case in self.cases]
        self.corpus = [
            self.record(case, suffix, label, groups)
            for case in ("PLAN-01", "PLAN-02")
            for suffix, label, groups in (
                ("ANCHOR", "anchor", [["kinase", "enzyme"]]),
                ("COUNTER", "counterevidence", [["safety", "risk"]]),
                ("NOISE", "irrelevant", [["broad"]]),
            )
        ]
        self.manifest_path = self._write_pack()
        self.bundle = load_plan_bundle(PLUGIN_ROOT, self.manifest_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def oracle(self, case: str) -> dict:
        return {
            "case_id": case,
            "required_concept_groups": [{"requirement_id": "target", "aliases": ["target", "target protein"]}],
            "required_sources": ["pubmed"], "required_waves": ["sentinel"],
            "max_query_events": 4,
            "anchor_record_ids": [f"{case}-ANCHOR"],
            "counterevidence_record_ids": [f"{case}-COUNTER"],
            "relevant_record_ids": [f"{case}-ANCHOR", f"{case}-COUNTER"],
            "required_stop_groups": [{"requirement_id": "saturation", "aliases": ["stop on saturation", "saturation reached"]}],
        }

    def record(
        self, case: str, suffix: str, relevance: str, groups: list[list[str]],
        published: str = "2024-01-01", precision: str = "day",
    ) -> dict:
        record_id = f"{case}-{suffix}"
        return {
            "case_id": case, "record_id": record_id, "title": f"Test-only {suffix}",
            "identifiers": {"test_id": record_id}, "source": "pubmed",
            "published_on": published, "date_precision": precision, "online_on": None,
            "event_dates": {}, "artifact": f"artifact:{record_id}",
            "relevance_class": relevance, "match_groups": groups,
        }

    def output(
        self, case: str = "PLAN-01", profile: str = "single_skill",
        rep: str = "17", query: str = "kinase safety",
    ) -> dict:
        value = {
            "case_id": case, "profile": profile, "replicate_label": rep,
            "worker_input_digest": worker_input_digest(self.bundle, case, profile, rep),
            "execution_status": "completed", "question_frame": "Test question",
            "as_of": "2025-01-15", "source_map": ["pubmed"],
            "concept_blocks": [{"block_id": "target-block", "terms": ["target protein"]}],
            "queries": [{"query_id": "q1", "source": "pubmed", "wave": "sentinel", "query": query, "purpose": "test replay"}],
            "inclusion_criteria": ["eligible"], "exclusion_criteria": ["ineligible"],
            "stop_rules": ["saturation reached"], "coverage_gaps": [],
        }
        return value

    def all_outputs(self, no_skill_query: str = "broad", single_query: str = "kinase safety") -> list[dict]:
        return [
            self.output(case, profile, rep, single_query if profile == "single_skill" else no_skill_query)
            for case in ("PLAN-01", "PLAN-02") for profile in ("no_skill", "single_skill")
            for rep in ("17", "29", "43")
        ]

    def test_grouped_matcher_normalization_identifier_and_case_scope(self) -> None:
        value = self.output(query="ＥＮＺＹＭＥ unrelated")
        run = replay_plan(validate_plan_output(value, self.bundle), self.bundle)
        self.assertEqual(["PLAN-01-ANCHOR"], [record["record_id"] for record in run["records"]])
        value = self.output(query="PLAN-01-COUNTER")
        run = replay_plan(validate_plan_output(value, self.bundle), self.bundle)
        self.assertEqual(["PLAN-01-COUNTER"], [record["record_id"] for record in run["records"]])
        self.assertEqual("alpha synuclein cp 690 550", normalize_lexical("α-synuclein CP-690,550"))
        self.assertTrue(group_matches(["CP690550"], ["CP-690,550", "CP690550"]))
        self.assertFalse(group_matches(["broad"], ["RA"]))

    def test_boolean_and_fielded_identifier_queries(self) -> None:
        official = load_plan_bundle(PLUGIN_ROOT, Path("evals/plan-forward-v1.manifest.json"))
        plan = self._official_output(official, "PLAN-01", "pubmed", "(LRRK2) AND Parkinson AND cloning")
        self.assertIn("PLAN01-PM-15541308", {item["record_id"] for item in replay_plan(plan, official)["records"]})
        for query in ("35081280[PMID]", "PMID:35081280", "DOI:10.1056/NEJMoa2109927"):
            plan = self._official_output(official, "PLAN-02", "pubmed", query)
            ids = {item["record_id"] for item in replay_plan(plan, official)["records"]}
            self.assertIn("PLAN02-PM-35081280", ids)

    def test_occurrences_dedup_and_query_level_precision(self) -> None:
        value = self.output(query="kinase safety broad")
        value["queries"].append(dict(value["queries"][0], query_id="q2"))
        run = replay_plan(validate_plan_output(value, self.bundle), self.bundle)
        self.assertEqual(6, len(run["hits"]))
        self.assertEqual(3, len(run["records"]))
        precision = run["scorecard"]["retrieval_precision"]
        self.assertEqual((4, 6), (precision["numerator"], precision["denominator"]))

    def test_grouped_metrics_save_matched_requirement_ids(self) -> None:
        run = replay_plan(validate_plan_output(self.output(), self.bundle), self.bundle)
        concept = run["scorecard"]["concept_block_coverage"]
        stop = run["scorecard"]["stop_rule_coverage"]
        self.assertEqual(["target"], concept["matched_requirement_ids"])
        self.assertEqual(["saturation"], stop["matched_requirement_ids"])

    def test_wave_schema_matches_skill_identity(self) -> None:
        for wave in ("sentinel", "discovery", "confirmation", "expansion", "challenge", "update"):
            value = self.output()
            value["queries"][0]["wave"] = wave
            validate_plan_output(value, self.bundle)
        value = self.output()
        value["queries"][0]["wave"] = "scoping"
        with self.assertRaisesRegex(ValueError, "wave"):
            validate_plan_output(value, self.bundle)

    def test_query_budget_is_auditable_hard_gate(self) -> None:
        value = self.output()
        value["queries"] = [dict(value["queries"][0], query_id=f"q{index}") for index in range(5)]
        run = replay_plan(validate_plan_output(value, self.bundle), self.bundle)
        self.assertIn("query_budget_exceeded", run["findings"])

    def test_month_upper_bound_and_future_record_gate(self) -> None:
        corpus = copy.deepcopy(self.corpus)
        corpus[0]["published_on"], corpus[0]["date_precision"] = "2025-01", "month"
        bundle = load_plan_bundle(PLUGIN_ROOT, self._write_pack(corpus=corpus))
        run = replay_plan(validate_plan_output(self._receipt(self.output(query="kinase"), bundle), bundle), bundle)
        self.assertIn("future_record", run["findings"])
        self.assertEqual(1, run["scorecard"]["temporal_violation_rate"]["numerator"])

    def test_future_online_and_event_metadata_are_gated(self) -> None:
        for mutation in (
            lambda record: record.update(online_on="2025-01-16"),
            lambda record: record.update(event_dates={"update_on": {"date": "2025-01", "precision": "month"}}),
        ):
            corpus = copy.deepcopy(self.corpus)
            mutation(corpus[0])
            bundle = load_plan_bundle(PLUGIN_ROOT, self._write_pack(corpus=corpus))
            plan = validate_plan_output(self._receipt(self.output(query="kinase"), bundle), bundle)
            run = replay_plan(plan, bundle)
            self.assertIn("future_metadata", run["findings"])
            self.assertEqual(1, run["scorecard"]["temporal_violation_rate"]["numerator"])

    def test_duplicate_corpus_id_is_loader_failure(self) -> None:
        corpus = self.corpus + [copy.deepcopy(self.corpus[0])]
        with self.assertRaisesRegex(ValueError, "record IDs"):
            load_plan_bundle(PLUGIN_ROOT, self._write_pack(corpus=corpus))

    def test_match_groups_dates_and_task_identifier_leak_fail_closed(self) -> None:
        for mutate, message in (
            (lambda corpus: corpus[0].update(match_groups=[]), "match_groups"),
            (lambda corpus: corpus[0].update(match_groups=[["kinase"], ["kinase"]]), "match groups"),
            (lambda corpus: corpus[0].update(published_on="2025-1", date_precision="month"), "precision"),
        ):
            corpus = copy.deepcopy(self.corpus)
            mutate(corpus)
            with self.assertRaisesRegex(ValueError, message):
                load_plan_bundle(PLUGIN_ROOT, self._write_pack(corpus=corpus))
        cases = copy.deepcopy(self.cases)
        cases[0]["task"] += " PLAN-01-ANCHOR"
        original = self.cases
        self.cases = cases
        try:
            path = self._write_pack()
        finally:
            self.cases = original
        with self.assertRaisesRegex(ValueError, "leaks"):
            load_plan_bundle(PLUGIN_ROOT, path)

    def test_provenance_conflict_and_orphan_taxonomy_are_stable(self) -> None:
        record = self.corpus[0]
        hit = {"record_id": record["record_id"], "source": record["source"],
               "artifact": "artifact:conflict", "published_on": record["published_on"],
               "date_precision": record["date_precision"]}
        self.assertEqual(["hit_record_mismatch"], replay_provenance_findings([hit], (record,)))
        self.assertEqual(["orphan_canonical_record"], replay_provenance_findings([], (record,)))

    def test_output_leakage_worker_identity_and_invalid_taxonomy(self) -> None:
        for mutation in (
            lambda value: value.update(extra="x"),
            lambda value: value["queries"][0].update(expected_query="kinase"),
            lambda value: value.update(worker_input_digest="0" * 64),
        ):
            value = self.output()
            mutation(value)
            with self.assertRaises(ValueError):
                validate_plan_output(value, self.bundle)
        values = self.all_outputs()
        values[0]["worker_input_digest"] = "0" * 64
        result = evaluate_plan_outputs(self.bundle, values)
        self.assertEqual(1, result["invalid_outputs"]["taxonomy"]["schema_or_worker_identity_invalid"])

    def test_missing_extra_metric_mismatch_negative_and_flat(self) -> None:
        values = self.all_outputs()
        missing = evaluate_plan_outputs(self.bundle, values[:-1])
        self.assertIn("missing_arm_or_replicate", missing["findings"])
        self.assertEqual("incomplete", missing["worker_completion"]["state"])
        extra = evaluate_plan_outputs(self.bundle, values + [copy.deepcopy(values[0])])
        self.assertEqual(1, extra["invalid_outputs"]["taxonomy"]["duplicate_output_identity"])
        values[1]["execution_status"] = "failed"
        mismatch = evaluate_plan_outputs(self.bundle, values)
        self.assertIn("metric_coverage_not_comparable", mismatch["findings"])
        self.assertEqual("failed", mismatch["worker_completion"]["state"])
        regressed = evaluate_plan_outputs(self.bundle, self.all_outputs("kinase safety", "broad"))
        self.assertIn("quality_metric_regression", regressed["findings"])
        flat = evaluate_plan_outputs(self.bundle, self.all_outputs("kinase safety", "kinase safety"))
        self.assertEqual("flat", flat["effect_outcome"])

    def test_invalid_result_preserves_digest_without_sensitive_payload(self) -> None:
        result = evaluate_plan_outputs(self.bundle, [{"gold": "do-not-preserve"}])
        self.assertEqual("rejected", result["effect_outcome"])
        self.assertEqual("invalid", result["input_receipts"][0]["status"])
        self.assertNotIn("do-not-preserve", json.dumps(result))

    def test_cli_writes_missing_arm_rejected_result(self) -> None:
        output_paths = []
        for index, value in enumerate(self.all_outputs()[:-1]):
            output_paths.append(self._write_json(f"worker-{index}.json", value))
        result_path = self.root / "negative-result.json"
        command = [
            sys.executable, str(PLUGIN_ROOT / "scripts/run_plan_forward_eval.py"),
            "evaluate", str(self.manifest_path), *(str(path) for path in output_paths),
            "--result", str(result_path.relative_to(PLUGIN_ROOT)),
        ]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        subprocess.run(command, cwd=PLUGIN_ROOT, env=env, check=True, capture_output=True)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual("rejected", result["effect_outcome"])
        self.assertEqual("incomplete", result["worker_completion"]["state"])

    def test_cli_complete_result_verifies_and_tamper_is_rejected(self) -> None:
        output_paths = [self._write_json(f"complete-{index}.json", value)
                        for index, value in enumerate(self.all_outputs())]
        result_path = self.root / "complete-result.json"
        base = [sys.executable, str(PLUGIN_ROOT / "scripts/run_plan_forward_eval.py")]
        relative_outputs = [str(path) for path in output_paths]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        evaluate = base + ["evaluate", str(self.manifest_path), *relative_outputs,
                           "--result", str(result_path.relative_to(PLUGIN_ROOT))]
        subprocess.run(evaluate, cwd=PLUGIN_ROOT, env=env, check=True, capture_output=True)
        verify = base + ["verify-result", str(self.manifest_path), *relative_outputs,
                         "--expected", str(result_path.relative_to(PLUGIN_ROOT))]
        subprocess.run(verify, cwd=PLUGIN_ROOT, env=env, check=True, capture_output=True)
        output_path = PLUGIN_ROOT / output_paths[0]
        original = output_path.read_bytes()
        output_path.write_bytes(original + b" ")
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.run(verify, cwd=PLUGIN_ROOT, env=env, check=True, capture_output=True)
        output_path.write_bytes(original)
        expected = json.loads(result_path.read_text(encoding="utf-8"))
        expected["promotion_eligible"] = True
        result_path.write_text(json.dumps(expected), encoding="utf-8")
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.run(verify, cwd=PLUGIN_ROOT, env=env, check=True, capture_output=True)

    def test_complete_verification_rejects_failed_workers(self) -> None:
        values = self.all_outputs()
        values[0]["execution_status"] = "failed"
        result = evaluate_plan_outputs(self.bundle, values)
        with self.assertRaisesRegex(ValueError, "completed workers"):
            verify_plan_result(self.bundle, values, result)

    def test_source_route_coverage_uses_queries_and_mismatch_gates(self) -> None:
        official = load_plan_bundle(PLUGIN_ROOT, Path("evals/plan-forward-v1.manifest.json"))
        plan = self._official_output(official, "PLAN-02", "pubmed", "35081280[PMID]")
        plan["source_map"] = ["pubmed", "clinicaltrials_gov", "fda_regulatory"]
        run = replay_plan(plan, official)
        self.assertIn("source_route_mismatch", run["findings"])
        metric = run["scorecard"]["source_route_coverage"]
        self.assertEqual((1, 3), (metric["numerator"], metric["denominator"]))

    def test_exact_replay_claim_limits_and_promotion(self) -> None:
        values = self.all_outputs()
        first = evaluate_plan_outputs(self.bundle, values, require_complete=True)
        second = evaluate_plan_outputs(self.bundle, copy.deepcopy(values), require_complete=True)
        self.assertEqual(first, second)
        verify_plan_result(self.bundle, values, first)
        self.assertFalse(first["promotion_eligible"])
        self.assertEqual(list(CLAIM_LIMITS), first["claim_limits"])

    def test_asset_identity_tamper_and_profile_policy_fail_closed(self) -> None:
        cases_path = self.root / "candidate_tasks.json"
        cases_path.write_bytes(cases_path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            load_plan_bundle(PLUGIN_ROOT, self.manifest_path)
        manifest = self._manifest()
        manifest["profiles"]["no_skill"]["skill"] = "plan-literature-search"
        with self.assertRaisesRegex(ValueError, "profile identity"):
            load_plan_bundle(PLUGIN_ROOT, self._write_json("bad-profile.json", manifest))
        fresh_path = self._write_pack()
        manifest = json.loads((PLUGIN_ROOT / fresh_path).read_text(encoding="utf-8"))
        manifest["identity_assets"]["common_prompt"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            load_plan_bundle(PLUGIN_ROOT, self._write_json("bad-identity.json", manifest))

    def test_asset_paths_and_ingest_symlink_escape_fail_closed(self) -> None:
        manifest = self._manifest()
        manifest["assets"] = {name: {"path": "/etc/hosts", "sha256": "0" * 64}
                              for name in ("candidate_tasks", "evaluator_oracles", "frozen_corpus")}
        with self.assertRaisesRegex(ValueError, "relative and contained"):
            load_plan_bundle(PLUGIN_ROOT, self._write_json("bad-path.json", manifest))
        link = self.root / "outputs"
        link.symlink_to("/etc")
        with self.assertRaisesRegex(ValueError, "symlink"):
            contained_directory(PLUGIN_ROOT, link.relative_to(PLUGIN_ROOT), create=True)
        leaf_dir = self.root / "leaf-dir"
        leaf_dir.mkdir()
        leaf = leaf_dir / "output.json"
        leaf.symlink_to("/tmp/frogent-must-not-touch")
        with self.assertRaisesRegex(ValueError, "symlink"):
            write_contained_exclusive(PLUGIN_ROOT, leaf.relative_to(PLUGIN_ROOT), "{}")

    def test_every_bound_evaluator_file_tamper_fails_load(self) -> None:
        revision = json.loads((self.root / "evaluator-revision.json").read_text(encoding="utf-8"))
        for spec in revision["files"].values():
            path = PLUGIN_ROOT / spec["path"]
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            try:
                with self.assertRaisesRegex(ValueError, "digest mismatch"):
                    load_plan_bundle(PLUGIN_ROOT, self.manifest_path)
            finally:
                path.write_bytes(original)

    def test_authoritative_post_run_pack_has_exact_replay_integrity(self) -> None:
        bundle = load_plan_bundle(PLUGIN_ROOT, Path("evals/plan-forward-v1.manifest.json"))
        self.assertEqual("locked", bundle.manifest["pack_status"])
        self.assertEqual((10, 12), tuple(sum(record["case_id"] == case for record in bundle.corpus)
                                        for case in ("PLAN-01", "PLAN-02")))
        output_dir = PLUGIN_ROOT / "evals/plan-forward-v1.outputs"
        paths = sorted(output_dir.glob("*.json"))
        expected_identities = {
            f"{case}|{profile}|{replicate}"
            for case in ("PLAN-01", "PLAN-02")
            for profile in ("no_skill", "single_skill")
            for replicate in ("17", "29", "43")
        }
        values = [json.loads(path.read_bytes()) for path in paths]
        identities = {
            "|".join((value["case_id"], value["profile"], value["replicate_label"]))
            for value in values
        }
        self.assertEqual(12, len(paths))
        self.assertEqual(expected_identities, identities)
        metadata = [
            {
                "identity": str(path.relative_to(PLUGIN_ROOT)),
                "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in paths
        ]
        result_path = PLUGIN_ROOT / "evals/plan-forward-v1.result.json"
        self.assertTrue(result_path.is_file())
        result = json.loads(result_path.read_bytes())
        verify_plan_result(bundle, values, result, input_metadata=metadata)
        self.assertEqual("completed", result["worker_completion"]["state"])
        self.assertEqual(12, result["worker_completion"]["completed"])
        self.assertEqual("completed", result["execution_completion"])
        self.assertEqual("rejected", result["effect_outcome"])
        self.assertFalse(result["promotion_eligible"])
        self.assertIn("exposed_development_panel", result["claim_limits"])

    def test_bound_common_prompt_exposes_exact_worker_schema_tokens(self) -> None:
        bundle = load_plan_bundle(PLUGIN_ROOT, Path("evals/plan-forward-v1.manifest.json"))
        spec = bundle.manifest["identity_assets"]["common_prompt"]
        prompt = (PLUGIN_ROOT / spec["path"]).read_text(encoding="utf-8")
        for route in ("pubmed", "clinicaltrials_gov", "fda_regulatory"):
            self.assertIn(route, prompt)
        for token in (
            "case_id", "profile", "replicate_label", "worker_input_digest", "as_of",
            "completed", "failed", "source_map", "concept_blocks", "block_id", "terms",
            "queries", "query_id", "source", "wave", "query", "purpose",
            "inclusion_criteria", "exclusion_criteria", "stop_rules", "coverage_gaps",
            "sentinel", "discovery", "confirmation", "expansion", "challenge", "update",
            "JSON only", "Markdown", "commentary", "evaluator fields",
        ):
            self.assertIn(token, prompt)

    def test_authoritative_routes_aliases_and_identifier_bypass_replay(self) -> None:
        bundle = load_plan_bundle(PLUGIN_ROOT, Path("evals/plan-forward-v1.manifest.json"))
        plan01 = self._official_output(bundle, "PLAN-01", "pubmed", "LRRK2 α-synuclein negative")
        ids = {record["record_id"] for record in replay_plan(plan01, bundle)["records"]}
        self.assertIn("PLAN01-PM-29855356", ids)
        plan02 = self._official_output(bundle, "PLAN-02", "clinicaltrials_gov", "NCT01458951")
        ids = {record["record_id"] for record in replay_plan(plan02, bundle)["records"]}
        self.assertEqual({"PLAN02-CT-NCT01458951"}, ids)
        wrong_route = self._official_output(bundle, "PLAN-02", "pubmed", "NCT01458951")
        ids = {record["record_id"] for record in replay_plan(wrong_route, bundle)["records"]}
        self.assertNotIn("PLAN02-CT-NCT01458951", ids)

    def _official_output(self, bundle: object, case: str, source: str, query: str) -> dict:
        value = self.output(case=case, query=query)
        value["as_of"] = "2024-12-31"
        value["source_map"] = [source]
        value["queries"][0]["source"] = source
        return validate_plan_output(self._receipt(value, bundle), bundle)

    def _receipt(self, value: dict, bundle: object) -> dict:
        value["worker_input_digest"] = worker_input_digest(
            bundle, value["case_id"], value["profile"], value["replicate_label"]
        )
        return value

    def _write_pack(self, corpus: list[dict] | None = None) -> Path:
        specs = {}
        for name, value in (("candidate_tasks", self.cases),
                            ("evaluator_oracles", self.oracles),
                            ("frozen_corpus", corpus or self.corpus)):
            relative = self._write_json(name + ".json", value)
            specs[name] = self._spec(relative)
        manifest = self._manifest()
        manifest["assets"] = specs
        return self._write_json("manifest.json", manifest)

    def _manifest(self) -> dict:
        identity_paths = {
            "common_prompt": Path("evals/plan-forward-v1.worker-common.txt"),
            "baseline_instruction": Path("evals/plan-forward-v1.baseline-instruction.txt"),
            "skill": Path("skills/plan-literature-search/SKILL.md"),
            "reference": Path("skills/plan-literature-search/references/query-strategy.md"),
        }
        return {
            "eval_id": "plan-forward-test-v1", "schema_version": "1.0", "pack_status": "locked",
            "authority_scope": "exposed_development_diagnostic", "provider_mode": "frozen_snapshot",
            "network": "denied", "seed_control": "unverified", "output_schema_id": "plan-forward-output-v1",
            "replicate_labels": ["17", "29", "43"],
            "profiles": {"no_skill": {"skill": "none", "declared_reference": "none"},
                         "single_skill": {"skill": "plan-literature-search", "declared_reference": "skills/plan-literature-search/references/query-strategy.md"}},
            "sole_variable": "plan-literature-search_skill_and_declared_reference",
            "registered_metrics": list(METRICS), "primary_metrics": list(PRIMARY_METRICS),
            "claim_limits": list(CLAIM_LIMITS), "assets": {},
            "identity_assets": {name: self._spec(path) for name, path in identity_paths.items()},
            "evaluator_identity": self._evaluator_spec(),
        }

    def _evaluator_spec(self) -> dict:
        specs = {}
        for relative in sorted(EVALUATOR_FILES):
            source = PLUGIN_ROOT / relative
            target = self.root / "bound-evaluator" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            rel = target.relative_to(PLUGIN_ROOT)
            specs[relative] = self._spec(rel)
        revision = self._write_json(
            "evaluator-revision.json", {"schema_version": "1.0", "files": specs}
        )
        return self._spec(revision)

    def _spec(self, relative: Path) -> dict:
        return {"path": str(relative), "sha256": hashlib.sha256((PLUGIN_ROOT / relative).read_bytes()).hexdigest()}

    def _write_json(self, name: str, value: object) -> Path:
        path = self.root / name
        path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return path.relative_to(PLUGIN_ROOT)


if __name__ == "__main__":
    unittest.main()
