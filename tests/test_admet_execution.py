"""Behavior tests for exact-identity ADMET-AI execution."""

import json
import math
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.molecular.admet_ai_adapter import ADMETAIAdapter  # noqa: E402
from agent.molecular.admet_execution import (  # noqa: E402
    ADMETBatchPrediction, DEFAULT_ADMET_PROPERTIES, execute_admet_step,
)
from agent.molecular.admet_workflow import (  # noqa: E402
    run_admet_name_workflow, run_admet_workflow,
)
from agent.molecular.molecular_binding import (  # noqa: E402
    MolecularInputBinding, MolecularToolInput,
)
from agent.molecular.molecular_identity import (  # noqa: E402
    DerivedMoleculeCandidate, MolecularIdentity,
)
from agent.molecular.molecular_routing import MolecularToolStep  # noqa: E402
from agent.molecular.pubchem_identity import PubChemIdentityResolver  # noqa: E402


CAFFEINE = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"
CAFFEINE_KEY = "RYYVLZVUVIJVGH-UHFFFAOYSA-N"
THEOBROMINE = "CN1C=NC2=C1C(=O)NC(=O)N2C"
THEOBROMINE_KEY = "YAPQBXQYLJRXSA-UHFFFAOYSA-N"


def molecule(smiles=CAFFEINE, key=CAFFEINE_KEY, *, fragments=1, organic=1, parent=None):
    return MolecularIdentity(smiles, smiles, smiles, "InChI=1S/test", key, "C8H10N4O2",
        194.08, 0, 14, fragments, organic, "single" if fragments == 1 else "mixture",
        False, 0, 0, "none", parent)


class FakeNormalizer:
    def __init__(self, values):
        self.values = values

    def normalize(self, smiles):
        return self.values[smiles] if isinstance(self.values, dict) else self.values


class FakePredictor:
    provider_id = "fake-admet"
    model_name = "deterministic"
    model_version = "test-1"

    def __init__(self, rows=None, error=None, reported_inputs=None):
        self.rows = rows
        self.error = error
        self.reported_inputs = reported_inputs
        self.calls = []

    def predict(self, smiles):
        self.calls.append(smiles)
        if self.error:
            raise self.error
        rows = self.rows or tuple(_values(index + 1) for index in range(len(smiles)))
        return ADMETBatchPrediction(self.reported_inputs or smiles, tuple(rows))


class FakeTransport:
    def __init__(self, payload=None, error=None):
        self.payload, self.error = payload, error

    def get(self, url, params, headers={}):
        if self.error:
            raise self.error
        return json.dumps(self.payload).encode()


class FakeFrame:
    def __init__(self, index, rows):
        self.index, self.rows = index, rows

    def to_dict(self, orient):
        if orient != "records":
            raise AssertionError(orient)
        return self.rows


def _values(offset=0):
    return {name: float(index + offset) / 10
            for index, name in enumerate(DEFAULT_ADMET_PROPERTIES)}


def _step(capability="admet.predict", *, candidate=None, baseline=None, status="ready"):
    candidate = candidate or MolecularInputBinding("full", CAFFEINE, CAFFEINE_KEY, True)
    roles = ("candidate", "baseline") if baseline else ("candidate",)
    tool_input = MolecularToolInput(candidate, baseline, roles)
    return MolecularToolStep(capability, status, "ADMET", tool_input)


def _pubchem_payload(cid=2519, title="Caffeine", smiles=CAFFEINE, key=CAFFEINE_KEY):
    return {"PropertyTable": {"Properties": [{"CID": cid, "Title": title,
        "ConnectivitySMILES": smiles, "SMILES": smiles, "InChI": "InChI=1S/test",
        "InChIKey": key, "MolecularFormula": "C8H10N4O2", "Charge": 0}]}}


class ADMETExecutionTests(unittest.TestCase):
    def test_single_full_binding_predicts_exact_input_and_typed_values(self):
        predictor = FakePredictor()
        result = execute_admet_step(_step(), predictor)
        self.assertEqual("completed", result.status)
        self.assertEqual(((CAFFEINE,), "candidate", CAFFEINE_KEY),
            (predictor.calls[0], result.arms[0].role, result.arms[0].binding.inchikey))
        self.assertEqual(DEFAULT_ADMET_PROPERTIES,
                         tuple(item.property_id for item in result.arms[0].values))
        self.assertFalse(result.experimental_evidence)
        self.assertIn("model predictions", result.warnings[0])
        self.assertIn("no calibrated", result.warnings[1])

    def test_salt_full_and_parent_preserve_distinct_inputs_and_fragments(self):
        parent = DerivedMoleculeCandidate("CC(=O)[O-]", "CC(=O)[O-]", "InChI=1S/acetate",
            "QTBSBXVTEAMEQO-UHFFFAOYSA-M", "C2H3O2-", ("[Na+]",))
        salt = molecule("CC(=O)[O-].[Na+]", "VMHLLURERBWHNL-UHFFFAOYSA-M",
                        fragments=2, parent=parent)
        acetate = molecule(parent.canonical_isomeric_smiles, parent.inchikey)
        adapter = FakeNormalizer({salt.canonical_isomeric_smiles: salt,
                                  acetate.canonical_isomeric_smiles: acetate})
        predictor = FakePredictor()
        full = run_admet_workflow(salt.original_smiles, "ADMET", predictor,
            normalizer=adapter, selected_structure_scope="full")
        parent_result = run_admet_workflow(salt.original_smiles, "ADMET", predictor,
            normalizer=adapter, selected_structure_scope="parent_candidate")
        self.assertEqual(((salt.canonical_isomeric_smiles,),
                          (parent.canonical_isomeric_smiles,)), tuple(predictor.calls))
        self.assertEqual(("full", "parent_candidate"),
            (full.execution.arms[0].binding.scope, parent_result.execution.arms[0].binding.scope))
        self.assertEqual(("[Na+]",), parent_result.execution.arms[0].binding.removed_fragments)

    def test_comparison_uses_one_batch_fixed_roles_and_auditable_deltas(self):
        baseline = MolecularInputBinding("full", THEOBROMINE, THEOBROMINE_KEY, True)
        predictor = FakePredictor((_values(3), _values(1)))
        result = execute_admet_step(_step("admet.compare", baseline=baseline), predictor,
                                    ("AMES", "DILI"))
        self.assertEqual(((CAFFEINE, THEOBROMINE),), tuple(predictor.calls))
        self.assertEqual(("candidate", "baseline"), result.role_order)
        self.assertEqual(("candidate", "baseline"), tuple(item.role for item in result.arms))
        self.assertEqual((0.2, 0.2), tuple(round(item.candidate_minus_baseline, 6)
                                         for item in result.deltas))

    def test_blockers_and_identity_ambiguity_prevent_model_calls(self):
        parent = DerivedMoleculeCandidate("CCO", "CCO", "InChI=1S/ethanol", "ETHANOL-KEY",
                                          "C2H6O", ("CCN",))
        mixture = molecule("CCO.CCN", "MIXTURE-KEY", fragments=2, organic=2, parent=parent)
        predictor = FakePredictor()
        blocked = run_admet_workflow(mixture.original_smiles, "ADMET", predictor,
                                     normalizer=FakeNormalizer(mixture))
        missing = run_admet_workflow(CAFFEINE, "compare ADMET", predictor,
                                     normalizer=FakeNormalizer(molecule()))
        same = run_admet_workflow(CAFFEINE, "ADMET compare", predictor,
            normalizer=FakeNormalizer(molecule()), baseline_smiles=CAFFEINE)
        self.assertEqual([], predictor.calls)
        self.assertEqual(("blocked", "blocked", "blocked"),
                         (blocked.execution.status, missing.execution.status,
                          same.execution.status))
        self.assertEqual((CAFFEINE_KEY,), tuple(item.inchikey
                         for item in missing.execution.input_bindings))
        self.assertIn("requires distinct", same.coverage_gaps[0])
        self.assertTrue(all(result.intake is not None for result in (blocked, missing, same)))

    def test_unconfirmed_direct_binding_and_invalid_properties_fail_safely(self):
        unconfirmed = MolecularInputBinding("full", "CCO.CCN", "MIXTURE", False)
        predictor = FakePredictor()
        first = execute_admet_step(_step(candidate=unconfirmed,
                                         status="requires_confirmation"), predictor)
        second = execute_admet_step(_step(), predictor, ("AMES", "unknown"))
        third = execute_admet_step(_step(), predictor, ("AMES", "AMES"))
        self.assertEqual([], predictor.calls)
        self.assertEqual(("blocked", "failed", "failed"),
                         (first.status, second.status, third.status))
        self.assertIn("unknown ADMET", second.coverage_gaps[0])

    def test_malformed_nonfinite_boolean_and_reordered_outputs_fail_closed(self):
        mutations = [
            FakePredictor(({"AMES": True},)),
            FakePredictor(({"AMES": math.nan},)),
            FakePredictor(({},)),
            FakePredictor((_values(),), reported_inputs=(THEOBROMINE,)),
        ]
        for predictor in mutations:
            with self.subTest(predictor=predictor):
                result = execute_admet_step(_step(), predictor, ("AMES",))
                self.assertEqual("failed", result.status)
                self.assertEqual((), result.arms)
                self.assertIn("ADMET prediction failed", result.coverage_gaps[0])
        baseline = MolecularInputBinding("full", THEOBROMINE, THEOBROMINE_KEY, True)
        missing_arm = execute_admet_step(_step("admet.compare", baseline=baseline),
                                          FakePredictor((_values(),)), ("AMES",))
        self.assertEqual("failed", missing_arm.status)

    def test_model_failure_is_local_and_keeps_intake_plan(self):
        predictor = FakePredictor(error=RuntimeError("model unavailable"))
        result = run_admet_workflow(CAFFEINE, "literature and ADMET", predictor,
                                    normalizer=FakeNormalizer(molecule()))
        self.assertEqual("failed", result.execution.status)
        self.assertEqual("ready", result.intake.tool_plan.steps[0].status)
        self.assertEqual(CAFFEINE_KEY, result.intake.selected_input.inchikey)
        self.assertIn("model unavailable", result.coverage_gaps[0])
        self.assertEqual(("research-biomedical-literature",), result.intake.tool_plan.skills)

    def test_pubchem_name_and_network_gap_paths_feed_confirmed_local_prediction(self):
        local = molecule()
        normalizer = FakeNormalizer(local)
        predictor = FakePredictor()
        resolver = PubChemIdentityResolver(FakeTransport(_pubchem_payload()), normalizer)
        named = run_admet_name_workflow("caffeine", "ADMET", resolver, predictor,
                                        normalizer=normalizer)
        offline = PubChemIdentityResolver(FakeTransport(error=OSError("offline")), normalizer)
        local_result = run_admet_workflow(CAFFEINE, "ADMET", predictor,
            normalizer=normalizer, pubchem_resolver=offline, claimed_name="caffeine")
        self.assertEqual(("completed", "completed"),
                         (named.execution.status, local_result.execution.status))
        self.assertEqual(CAFFEINE_KEY, named.verification.candidate.external.inchikey)
        self.assertIn("OSError: offline", local_result.coverage_gaps[0])
        self.assertEqual(((CAFFEINE,), (CAFFEINE,)), tuple(predictor.calls))

    def test_lazy_adapter_loads_one_model_and_rejects_reordered_frame(self):
        created = []
        class Model:
            def predict(self, smiles):
                return FakeFrame(smiles, [_values() for _ in smiles])
        adapter = ADMETAIAdapter(lambda: created.append(1) or Model(), model_version="2.test")
        execute_admet_step(_step(), adapter, ("AMES",))
        execute_admet_step(_step(), adapter, ("AMES",))
        self.assertEqual([1], created)
        self.assertEqual("2.test", adapter.model_version)
        bad = ADMETAIAdapter(lambda: type("Bad", (), {"predict": lambda self, smiles:
            FakeFrame(list(reversed(smiles)), [_values() for _ in smiles])})())
        baseline = MolecularInputBinding("full", THEOBROMINE, THEOBROMINE_KEY, True)
        self.assertEqual("failed", execute_admet_step(
            _step("admet.compare", baseline=baseline), bad, ("AMES",)).status)

    def test_lazy_import_or_constructor_failure_is_typed(self):
        def unavailable():
            raise ImportError("admet-ai missing")
        result = execute_admet_step(_step(), ADMETAIAdapter(unavailable), ("AMES",))
        self.assertEqual("failed", result.status)
        self.assertIn("ImportError: admet-ai missing", result.coverage_gaps[0])


if __name__ == "__main__":
    unittest.main()
