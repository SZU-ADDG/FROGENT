"""Behavior tests for official PubChem molecular identity verification."""

import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin.molecular_binding import MolecularInputBinding  # noqa: E402
from frogent_plugin.molecular_identity import (  # noqa: E402
    DerivedMoleculeCandidate, MolecularIdentity,
)
from frogent_plugin.pubchem_identity import (  # noqa: E402
    PubChemIdentityResolver, VerifiedMolecularRequest,
    prepare_molecular_request_from_name, verify_molecular_request,
)


CAFFEINE_KEY = "RYYVLZVUVIJVGH-UHFFFAOYSA-N"
THEOBROMINE_KEY = "YAPQBXQYLJRXSA-UHFFFAOYSA-N"


def molecule(smiles="CN1C=NC2=C1C(=O)N(C(=O)N2C)C", key=CAFFEINE_KEY, *,
             original="", fragments=1, organic=1, parent=None):
    return MolecularIdentity(original or smiles, smiles, smiles, "InChI=1S/C8H10N4O2",
        key, "C8H10N4O2", 194.080376, 0, 14, fragments, organic,
        "single" if fragments == 1 else "salt_or_counterion", False, 0, 0, "none", parent)


def properties(cid=2519, title="Caffeine", smiles="CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
               key=CAFFEINE_KEY, formula="C8H10N4O2", charge=0):
    return {"PropertyTable": {"Properties": [{"CID": cid, "Title": title,
        "ConnectivitySMILES": smiles, "SMILES": smiles, "InChI": "InChI=1S/test",
        "InChIKey": key, "MolecularFormula": formula, "Charge": charge}]}}


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def get(self, url, params, headers={}):
        self.calls.append((url, params, headers))
        if self.error:
            raise self.error
        value = self.response(url) if callable(self.response) else self.response
        return json.dumps(value).encode()


class FakeNormalizer:
    def __init__(self, values): self.values, self.inputs = values, []

    def normalize(self, smiles):
        self.inputs.append(smiles)
        return self.values[smiles] if isinstance(self.values, dict) else self.values


class PubChemIdentityTests(unittest.TestCase):
    def test_exact_binding_resolves_verified_identity_terms_and_artifact(self):
        identity = molecule()
        transport = FakeTransport(properties())
        resolver = PubChemIdentityResolver(transport, FakeNormalizer(identity))
        result = resolver.resolve_binding(MolecularInputBinding("full",
            identity.canonical_isomeric_smiles, identity.inchikey, True))
        self.assertEqual((2519, "Caffeine", CAFFEINE_KEY, "exact_inchikey", "full"),
            (result.external.cid, result.external.verified_name, result.external.inchikey,
             result.external.resolution_method, result.external.scope))
        self.assertEqual(("pubchem_cid", "verified_name"),
                         tuple(item.kind for item in result.search_terms))
        self.assertEqual(((True, "full"), (False, "full")),
                         tuple((item.exact, item.scope) for item in result.search_terms))
        self.assertTrue(all(item.provenance == "pubchem_pug_rest"
                            and item.artifact_url == result.external.artifact_url
                            for item in result.search_terms))
        self.assertIn("/inchikey/RYYVLZVUVIJVGH-UHFFFAOYSA-N/property/", transport.calls[0][0])
        self.assertEqual({}, transport.calls[0][1])

    def test_mismatch_conflict_and_malformed_payloads_fail_closed(self):
        binding = MolecularInputBinding("full", "CCO", CAFFEINE_KEY, True)
        mismatch = PubChemIdentityResolver(FakeTransport(properties(key=THEOBROMINE_KEY)),
            FakeNormalizer(molecule(key=THEOBROMINE_KEY))).resolve_binding(binding)
        self.assertIsNone(mismatch.external)
        self.assertIn("does not match selected", mismatch.coverage_gaps[0])
        conflict = properties()
        conflict["PropertyTable"]["Properties"].append(dict(
            conflict["PropertyTable"]["Properties"][0], CID=999))
        for payload in (conflict, {"PropertyTable": {"Properties": [{"CID": 1}]}}):
            with self.subTest(payload=payload):
                result = PubChemIdentityResolver(FakeTransport(payload),
                    FakeNormalizer(molecule())).resolve_binding(binding)
                self.assertIsNone(result.external)
                self.assertEqual((), result.search_terms)
                self.assertTrue(result.coverage_gaps)

    def test_exact_inchikey_selects_one_complete_consistent_duplicate(self):
        complete = properties()["PropertyTable"]["Properties"][0]
        incomplete = dict(complete, CID=31372)
        incomplete.pop("Title")
        payload = {"PropertyTable": {"Properties": [incomplete, complete]}}
        resolver = PubChemIdentityResolver(FakeTransport(payload), FakeNormalizer(molecule()))
        result = resolver.resolve_binding(MolecularInputBinding("full",
            molecule().canonical_isomeric_smiles, CAFFEINE_KEY, True))
        self.assertEqual((2519, "Caffeine"),
                         (result.external.cid, result.external.verified_name))

    def test_exact_duplicate_structural_title_cid_and_shape_ambiguity_fail_closed(self):
        complete = properties()["PropertyTable"]["Properties"][0]
        incomplete = dict(complete, CID=31372)
        incomplete.pop("Title")
        mutations = []
        mutations.append([dict(incomplete, MolecularFormula="C7H8N4O2"), complete])
        mutations.append([dict(complete, CID=31372, Title="Other title"), complete])
        mutations.append([dict(complete, CID=31372), complete])
        mutations.append([incomplete, dict(incomplete, CID=999)])
        mutations.append([incomplete, "malformed"])
        for records in mutations:
            with self.subTest(records=records):
                payload = {"PropertyTable": {"Properties": records}}
                result = PubChemIdentityResolver(FakeTransport(payload),
                    FakeNormalizer(molecule())).resolve_binding(MolecularInputBinding(
                        "full", molecule().canonical_isomeric_smiles, CAFFEINE_KEY, True))
                self.assertIsNone(result.external)
                self.assertTrue(result.coverage_gaps)

    def test_name_resolution_prepares_verified_structure_without_trusting_label(self):
        identity = molecule()
        resolver = PubChemIdentityResolver(FakeTransport(properties()),
                                           FakeNormalizer(identity))
        result = prepare_molecular_request_from_name("caffeine", "literature ADMET", resolver,
                                                     normalizer=FakeNormalizer(identity))
        self.assertIsInstance(result, VerifiedMolecularRequest)
        self.assertEqual(("Caffeine", CAFFEINE_KEY, "ready", "resolved_name"),
            (result.candidate.external.verified_name, result.intake.selected_input.inchikey,
             result.intake.tool_plan.steps[0].status, result.candidate.external.scope))
        self.assertIn("/name/caffeine/property/", result.candidate.external.artifact_url)

    def test_network_failure_keeps_local_identity_and_tool_plan_usable(self):
        local = molecule()
        normalizer = FakeNormalizer(local)
        resolver = PubChemIdentityResolver(FakeTransport(error=OSError("offline")), normalizer)
        result = verify_molecular_request(local.canonical_isomeric_smiles, "ADMET", resolver,
                                          normalizer=normalizer)
        self.assertEqual("ready", result.intake.tool_plan.steps[0].status)
        self.assertEqual(CAFFEINE_KEY, result.intake.selected_input.inchikey)
        self.assertIsNone(result.candidate.external)
        self.assertIn("OSError: offline", result.coverage_gaps[0])
        self.assertEqual(result.intake.search_terms, result.search_terms)

    def test_salt_full_and_parent_verify_the_exact_selected_identity(self):
        parent = DerivedMoleculeCandidate("CC(=O)[O-]", "CC(=O)[O-]", "InChI=1S/C2H4O2",
            "QTBSBXVTEAMEQO-UHFFFAOYSA-M", "C2H3O2-", ("[Na+]",))
        salt = molecule("CC(=O)[O-].[Na+]", "VMHLLURERBWHNL-UHFFFAOYSA-M", fragments=2,
                        parent=parent)
        acetate = molecule("CC(=O)[O-]", parent.inchikey)
        def response(url):
            return (properties(517045, "Sodium acetate", salt.canonical_isomeric_smiles,
                               salt.inchikey, "C2H3NaO2") if salt.inchikey in url else
                    properties(176, "Acetate", acetate.canonical_isomeric_smiles,
                               acetate.inchikey, "C2H3O2", -1))
        adapter = FakeNormalizer({salt.canonical_isomeric_smiles: salt,
                                  acetate.canonical_isomeric_smiles: acetate})
        resolver = PubChemIdentityResolver(FakeTransport(response), adapter)
        full = verify_molecular_request(salt.canonical_isomeric_smiles, "ADMET", resolver,
            normalizer=adapter, selected_structure_scope="full")
        parent_result = verify_molecular_request(salt.canonical_isomeric_smiles, "ADMET", resolver,
            normalizer=adapter, selected_structure_scope="parent_candidate")
        self.assertEqual((salt.inchikey, parent.inchikey),
                         (full.candidate.external.inchikey,
                          parent_result.candidate.external.inchikey))
        self.assertEqual(("full", "parent_candidate"),
                         (full.candidate.external.scope, parent_result.candidate.external.scope))

    def test_candidate_baseline_terms_are_symmetric_and_false_label_is_rejected(self):
        caffeine = molecule()
        theobromine_smiles = "CN1C=NC2=C1C(=O)NC(=O)N2C"
        theobromine = molecule(theobromine_smiles, THEOBROMINE_KEY)
        def response(url):
            if THEOBROMINE_KEY in url:
                return properties(5429, "Theobromine", theobromine_smiles, THEOBROMINE_KEY)
            return properties()
        adapter = FakeNormalizer({caffeine.canonical_isomeric_smiles: caffeine,
                                  theobromine_smiles: theobromine})
        result = verify_molecular_request(caffeine.canonical_isomeric_smiles,
            "literature compare ADMET", PubChemIdentityResolver(FakeTransport(response), adapter),
            normalizer=adapter, baseline_smiles=theobromine_smiles,
            claimed_name="theobromine", baseline_claimed_name="theobromine")
        self.assertEqual((CAFFEINE_KEY, THEOBROMINE_KEY),
            (result.intake.selected_input.inchikey, result.intake.selected_baseline_input.inchikey))
        self.assertEqual(("candidate", "baseline"),
                         result.intake.tool_plan.steps[0].tool_input.role_order)
        self.assertIn("Caffeine", {term.value for term in result.search_terms})
        self.assertNotIn("Theobromine", {term.value for term in result.search_terms})
        self.assertIn("Theobromine", {term.value for term in result.baseline_search_terms})
        self.assertIn("candidate supplied name rejected", result.coverage_gaps[0])

        same = verify_molecular_request(caffeine.canonical_isomeric_smiles,
            "literature compare ADMET", PubChemIdentityResolver(FakeTransport(response), adapter),
            normalizer=adapter, baseline_smiles=caffeine.canonical_isomeric_smiles,
            claimed_name="caffeine", baseline_claimed_name="theobromine")
        self.assertEqual("blocked", same.intake.tool_plan.steps[0].status)
        self.assertTrue(any("distinct candidate and baseline" in item
                            for item in same.intake.tool_plan.blockers))
        self.assertNotIn("Theobromine", {term.value for term in same.baseline_search_terms})


if __name__ == "__main__":
    unittest.main()
