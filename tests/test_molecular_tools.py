"""Behavior tests for molecular identity normalization and prerequisite routing."""

import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.core.catalog import CAPABILITIES  # noqa: E402
from agent.molecular.molecular_identity import (  # noqa: E402
    DerivedMoleculeCandidate, MolecularIdentity, RDKitMoleculeNormalizer,
)
from agent.molecular.molecular_binding import MolecularInputBinding  # noqa: E402
from agent.molecular.molecular_routing import prepare_molecular_request  # noqa: E402


def identity(*, fragment_status="single", stereo="none", assigned=0, unassigned=0,
             charged=False, parent=None, original="", canonical="", inchikey=""):
    default = "CCN.CCO" if fragment_status == "multiple_organic_fragments" else "CCO"
    return MolecularIdentity(
        original_smiles=original or ("CCO.CCN" if fragment_status ==
                                     "multiple_organic_fragments" else default),
        canonical_isomeric_smiles=canonical or default,
        canonical_connectivity_smiles=canonical or default,
        inchi="InChI=1S/C2H6O", inchikey=inchikey or "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
        formula="C2H6O", exact_mass=46.041865, formal_charge=1 if charged else 0,
        heavy_atom_count=3, fragment_count=2 if fragment_status != "single" else 1,
        organic_fragment_count=2 if fragment_status == "multiple_organic_fragments" else 1,
        fragment_status=fragment_status, has_charged_fragments=charged,
        assigned_stereocenters=assigned, unassigned_stereocenters=unassigned,
        stereochemistry_status=stereo, parent_candidate=parent,
    )


class FakeNormalizer:
    def __init__(self, value): self.value, self.inputs = value, []
    def normalize(self, smiles):
        self.inputs.append(smiles)
        return self.value[smiles] if isinstance(self.value, dict) else self.value


class MolecularToolTests(unittest.TestCase):
    def test_real_rdkit_identity_preserves_full_structure_and_stereo(self):
        try:
            normalizer = RDKitMoleculeNormalizer()
            aspirin = normalizer.normalize("CC(=O)Oc1ccccc1C(=O)O")
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional RDKit unavailable: {exc}")
        self.assertEqual(("C9H8O4", "BSYNRYMUTXBXSQ-UHFFFAOYSA-N", 1, "single"),
                         (aspirin.formula, aspirin.inchikey, aspirin.fragment_count,
                          aspirin.fragment_status))
        self.assertAlmostEqual(180.0423, aspirin.exact_mass, places=3)
        defined = normalizer.normalize("C[C@H](O)C(=O)O")
        unspecified = normalizer.normalize("CC(O)C(=O)O")
        self.assertEqual((1, 0, "assigned"),
                         (defined.assigned_stereocenters, defined.unassigned_stereocenters,
                          defined.stereochemistry_status))
        self.assertEqual((0, 1, "unassigned"),
                         (unspecified.assigned_stereocenters, unspecified.unassigned_stereocenters,
                          unspecified.stereochemistry_status))
        left = normalizer.normalize("C[C@@H](O)C(=O)O")
        right = normalizer.normalize("C[C@H](O)C(=O)O")
        self.assertEqual({"JVTAAEKCZFNVCJ-REOHCLBHSA-N", "JVTAAEKCZFNVCJ-UWTATZPHSA-N"},
                         {left.inchikey, right.inchikey})
        self.assertNotEqual(left.inchikey, right.inchikey)

    def test_real_rdkit_salt_multi_fragment_charge_and_invalid_are_explicit(self):
        try:
            normalizer = RDKitMoleculeNormalizer()
            salt = normalizer.normalize("CC(=O)[O-].[Na+]")
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional RDKit unavailable: {exc}")
        self.assertEqual((2, 1, "salt_or_counterion", True),
                         (salt.fragment_count, salt.organic_fragment_count,
                          salt.fragment_status, salt.has_charged_fragments))
        self.assertIsNotNone(salt.parent_candidate)
        self.assertIn("[Na+]", salt.parent_candidate.removed_fragments)
        pending = prepare_molecular_request("CC(=O)[O-].[Na+]", "ADMET retrosynthesis",
                                            normalizer)
        self.assertTrue(all(item.status == "requires_confirmation"
                            for item in pending.tool_plan.steps))
        self.assertTrue(all(item.tool_input.candidate.scope == "full"
                            and not item.tool_input.candidate.selection_confirmed
                            for item in pending.tool_plan.steps))
        full = prepare_molecular_request("CC(=O)[O-].[Na+]", "ADMET retrosynthesis",
                                         normalizer, selected_structure_scope="full")
        parent = prepare_molecular_request("CC(=O)[O-].[Na+]", "ADMET retrosynthesis",
                                           normalizer, selected_structure_scope="parent_candidate")
        self.assertTrue(all(item.status == "ready" for item in full.tool_plan.steps
                            + parent.tool_plan.steps))
        self.assertEqual(salt.canonical_isomeric_smiles,
                         full.tool_plan.steps[0].tool_input.candidate.canonical_isomeric_smiles)
        self.assertEqual(salt.parent_candidate.inchikey,
                         parent.tool_plan.steps[0].tool_input.candidate.inchikey)
        self.assertEqual(("[Na+]",), parent.provenance.removed_fragments)
        mixed = normalizer.normalize("CCO.CCN")
        self.assertEqual((2, "multiple_organic_fragments"),
                         (mixed.organic_fragment_count, mixed.fragment_status))
        with self.assertRaisesRegex(ValueError, "exact selected fragment"):
            prepare_molecular_request("CCO.CCN", "ADMET", normalizer,
                                      selected_structure_scope="parent_candidate")
        selected = prepare_molecular_request("CCO.CCN", "ADMET", normalizer,
            selected_structure_scope="parent_candidate", selected_structure_smiles="CCN")
        self.assertEqual(("ready", "CCN"),
                         (selected.tool_plan.steps[0].status,
                          selected.tool_plan.steps[0].tool_input.candidate.canonical_isomeric_smiles))
        charged = normalizer.normalize("C[NH3+]")
        self.assertTrue(charged.has_charged_fragments)
        self.assertEqual(1, charged.formal_charge)
        with self.assertRaisesRegex(ValueError, "invalid SMILES"):
            normalizer.normalize("C1(CC")

    def test_real_rdkit_parent_selection_rejects_counterion_and_accepts_organic_fragment(self):
        try:
            normalizer = RDKitMoleculeNormalizer()
            normalizer.normalize("CCO.CCN.[Na+]")
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional RDKit unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "exact normalized input fragment"):
            prepare_molecular_request("CCO.CCN.[Na+]", "ADMET", normalizer,
                selected_structure_scope="parent_candidate", selected_structure_smiles="[Na+]")
        for fragment in ("CCO", "CCN"):
            with self.subTest(fragment=fragment):
                result = prepare_molecular_request("CCO.CCN.[Na+]", "ADMET", normalizer,
                    selected_structure_scope="parent_candidate",
                    selected_structure_smiles=fragment)
                binding = result.tool_plan.steps[0].tool_input.candidate
                self.assertEqual(("ready", "parent_candidate", fragment),
                                 (result.tool_plan.steps[0].status, binding.scope,
                                  binding.canonical_isomeric_smiles))

    def test_exact_terms_keep_original_and_derived_parent_provenance(self):
        parent = DerivedMoleculeCandidate("CCO", "CCO", "InChI=1S/C2H6O",
            "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", "C2H6O", ("CCN",))
        source = identity(fragment_status="multiple_organic_fragments", parent=parent)
        result = prepare_molecular_request("CCO.CCN", "literature", FakeNormalizer(source),
                                           include_formula=True)
        self.assertEqual("CCO.CCN", result.identity.original_smiles)
        values = {(item.kind, item.scope, item.value, item.exact) for item in result.search_terms}
        self.assertIn(("canonical_smiles", "full", "CCN.CCO", True), values)
        self.assertIn(("inchikey", "parent_candidate", parent.inchikey, True), values)
        self.assertIn(("formula", "full", "C2H6O", False), values)
        self.assertEqual(("research-biomedical-literature",), result.tool_plan.skills)
        self.assertEqual(("CCO.CCN", ("CCN",)),
                         (result.provenance.original_smiles, result.provenance.removed_fragments))

    def test_prerequisites_block_unsafe_tools_but_leave_literature_search_usable(self):
        parent = DerivedMoleculeCandidate("CCO", "CCO", "InChI=1S/C2H6O",
            "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", "C2H6O", ("CCN",))
        source = identity(fragment_status="multiple_organic_fragments", stereo="unassigned",
                          unassigned=1, parent=parent)
        result = prepare_molecular_request("CCO.CCN", "literature docking fragment SAR",
                                           FakeNormalizer(source))
        routes = {item.capability_id: item for item in result.tool_plan.steps}
        self.assertEqual("blocked", routes["docking.score"].status)
        self.assertEqual("blocked", routes["fragment.reconstruct"].status)
        self.assertTrue(any("target" in item for item in result.tool_plan.blockers))
        self.assertTrue(any("multiple organic" in item for item in result.tool_plan.blockers))
        self.assertTrue(result.search_terms)
        self.assertEqual("CCO.CCN", result.input_provenance)
        self.assertTrue(all(item.tool_input.candidate.canonical_isomeric_smiles == "CCN.CCO"
                            for item in result.tool_plan.steps))

        selected_fragment = identity(original="CCN", canonical="CCN",
                                     inchikey="QUSNBJAOOMFDIB-UHFFFAOYSA-N")
        selected = prepare_molecular_request("CCO.CCN", "ADMET retrosynthesis",
            FakeNormalizer({"CCO.CCN": source, "CCN": selected_fragment}),
            selected_structure_scope="parent_candidate", selected_structure_smiles="CCN")
        self.assertTrue(all(item.status == "ready" for item in selected.tool_plan.steps))
        self.assertTrue(all(item.tool_input.candidate.scope == "parent_candidate"
                            and item.tool_input.candidate.canonical_isomeric_smiles == "CCN"
                            and item.tool_input.candidate.inchikey == selected_fragment.inchikey
                            for item in selected.tool_plan.steps))

    def test_admet_comparison_requires_baseline_and_routes_use_catalog_ids(self):
        source = identity()
        missing = prepare_molecular_request("CCO", "compare ADMET", FakeNormalizer(source))
        step = next(item for item in missing.tool_plan.steps
                    if item.capability_id == "admet.compare")
        self.assertEqual("blocked", step.status)
        self.assertTrue(any("baseline" in item for item in missing.tool_plan.blockers))
        docking = prepare_molecular_request("CCO", "compare docking", FakeNormalizer(source),
                                            target_id="P12345", pocket_id="pocket-1")
        self.assertEqual("blocked", docking.tool_plan.steps[0].status)
        baseline = MolecularIdentity("CCN", "CCN", "CCN", "InChI=1S/C2H7N",
            "QUSNBJAOOMFDIB-UHFFFAOYSA-N", "C2H7N", 45.057849, 0, 3, 1, 1,
            "single", False, 0, 0, "none")
        comparison = prepare_molecular_request("CCO", "literature compare ADMET",
            FakeNormalizer({"CCO": source, "CCN": baseline}), baseline_smiles="CCN")
        compared = comparison.tool_plan.steps[0]
        self.assertEqual(("ready", ("candidate", "baseline"), source.inchikey,
                          baseline.inchikey),
                         (compared.status, compared.tool_input.role_order,
                          compared.tool_input.candidate.inchikey,
                          compared.tool_input.baseline.inchikey))
        self.assertIn(baseline.inchikey, {item.value for item in comparison.baseline_search_terms})
        self.assertEqual(("candidate", "baseline"), compared.tool_input.role_order)
        ready = prepare_molecular_request("CCO", "ADMET retrosynthesis", FakeNormalizer(source))
        self.assertEqual(("admet.predict", "retrosynthesis.flash", "retrosynthesis.explorer"),
                         tuple(item.capability_id for item in ready.tool_plan.steps))
        known = {item.id for item in CAPABILITIES}
        self.assertTrue(all(item.capability_id in known for item in ready.tool_plan.steps))
        self.assertTrue(any("computational" in item for item in ready.tool_plan.warnings))

    def test_docking_unresolved_stereo_requires_confirmation_after_context_exists(self):
        source = identity(stereo="unassigned", unassigned=1)
        result = prepare_molecular_request("CCO", "dock", FakeNormalizer(source),
                                           target_id="P12345", pocket_id="pocket-1")
        step = next(item for item in result.tool_plan.steps
                    if item.capability_id == "docking.score")
        self.assertEqual("requires_confirmation", step.status)
        self.assertTrue(any("stereo" in item for item in result.tool_plan.blockers))
        self.assertEqual(("P12345", "pocket-1"),
                         (step.tool_input.target_id, step.tool_input.pocket_id))

    def test_physchem_and_similarity_route_to_local_chemistry_tools(self):
        source = identity()
        baseline = identity(original="CCN", canonical="CCN",
                            inchikey="QUSNBJAOOMFDIB-UHFFFAOYSA-N")
        described = prepare_molecular_request(
            "CCO", "calculate QED and Lipinski descriptors", FakeNormalizer(source)
        )
        self.assertEqual(
            ("molecule.describe",),
            tuple(step.capability_id for step in described.tool_plan.steps),
        )
        compared = prepare_molecular_request(
            "CCO",
            "calculate Tanimoto similarity to the baseline",
            FakeNormalizer({"CCO": source, "CCN": baseline}),
            baseline_smiles="CCN",
        )
        self.assertEqual("molecule.similarity", compared.tool_plan.steps[0].capability_id)
        self.assertEqual("ready", compared.tool_plan.steps[0].status)
        blocked = prepare_molecular_request(
            "CCO", "calculate molecular similarity", FakeNormalizer(source)
        )
        self.assertEqual("blocked", blocked.tool_plan.steps[0].status)
        self.assertTrue(any("reference" in item for item in blocked.tool_plan.blockers))

    def test_target_aware_screening_routes_to_known_active_evidence(self):
        source = identity()
        result = prepare_molecular_request(
            "CCO",
            "target-aware virtual screening against known actives",
            FakeNormalizer(source),
            target_id="EGFR",
        )
        self.assertEqual(
            "screening.target-active-similarity",
            result.tool_plan.steps[1].capability_id,
        )
        self.assertEqual("ready", result.tool_plan.steps[1].status)
        self.assertEqual("blocked", result.tool_plan.steps[0].status)

    def test_selection_must_name_an_executable_fragment_and_baseline_scope(self):
        parent = DerivedMoleculeCandidate("CCO", "CCO", "InChI=1S/C2H6O",
            "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", "C2H6O", ("CCN",))
        source = identity(fragment_status="multiple_organic_fragments", parent=parent)
        adapter = FakeNormalizer({"CCO.CCN": source})
        pending = prepare_molecular_request("CCO.CCN", "ADMET", adapter)
        self.assertEqual("requires_confirmation", pending.tool_plan.steps[0].status)
        with self.assertRaisesRegex(ValueError, "exact selected fragment"):
            prepare_molecular_request("CCO.CCN", "ADMET", adapter,
                                      selected_structure_scope="parent_candidate")
        baseline = identity(original="CCC", canonical="CCC",
                            inchikey="ATUOYWHBWRKTHZ-UHFFFAOYSA-N")
        compared = prepare_molecular_request("CCO", "literature compare ADMET",
            FakeNormalizer({"CCO": identity(), "CCC": baseline}), baseline_smiles="CCC",
            selected_structure_scope="full", baseline_structure_scope="full")
        binding = compared.tool_plan.steps[0].tool_input
        self.assertEqual(("full", "full", ("candidate", "baseline")),
                         (binding.candidate.scope, binding.baseline.scope, binding.role_order))

    def test_boolean_contracts_reject_integer_and_text_flags(self):
        adapter = FakeNormalizer(identity())
        for keyword, value in (("interaction_evidence", 1), ("include_formula", "yes")):
            with self.subTest(keyword=keyword):
                with self.assertRaisesRegex(ValueError, "flags must be boolean"):
                    prepare_molecular_request("CCO", "ADMET", adapter, **{keyword: value})
        with self.assertRaisesRegex(ValueError, "selection flag must be boolean"):
            MolecularInputBinding("full", "CCO", "KEY", 1)

    def test_descriptive_interaction_comparison_does_not_require_molecular_baseline(self):
        result = prepare_molecular_request("CCO", "compare interactions in this docking pose",
            FakeNormalizer(identity()), target_id="P12345", pocket_id="pocket-1")
        self.assertEqual("ready", result.tool_plan.steps[0].status)
        self.assertIsNone(result.tool_plan.steps[0].tool_input.baseline)
        self.assertFalse(any("baseline" in item for item in result.tool_plan.blockers))


if __name__ == "__main__":
    unittest.main()
