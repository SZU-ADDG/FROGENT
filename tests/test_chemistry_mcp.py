"""Tests for the deterministic local chemistry MCP capabilities."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.molecular.chembl_evidence import (  # noqa: E402
    normalize_target_query,
    rank_candidates_against_target_actives,
)
from agent.molecular.pdb_ligand_evidence import (  # noqa: E402
    rank_candidates_against_pdb_ligands,
)
from agent.molecular.physchem import describe_smiles, rank_similarity  # noqa: E402
from mcp.chemistry_mcp import McpServer  # noqa: E402


class ChemistryCapabilityTests(unittest.TestCase):
    def test_target_query_removes_mutation_annotation(self) -> None:
        self.assertEqual("ABL1", normalize_target_query("ABL1(M351T)-phosphorylated"))

    def test_target_active_similarity_uses_curated_records(self) -> None:
        def fetcher(url: str) -> dict:
            if "/target/search.json" in url:
                return {"targets": [{
                    "target_chembl_id": "CHEMBL1",
                    "pref_name": "Example kinase",
                    "organism": "Homo sapiens",
                    "target_type": "SINGLE PROTEIN",
                    "score": 20,
                    "target_components": [{"target_component_synonyms": [
                        {"component_synonym": "EXK", "syn_type": "GENE_SYMBOL"}
                    ]}],
                }]}
            return {
                "activities": [
                    {"canonical_smiles": "CCO", "molecule_chembl_id": "CHEMBL10",
                     "pchembl_value": "8.0", "data_validity_comment": None,
                     "potential_duplicate": 0},
                    {"canonical_smiles": "c1ccccc1", "molecule_chembl_id": "CHEMBL11",
                     "pchembl_value": "7.0", "data_validity_comment": None,
                     "potential_duplicate": 0},
                ],
                "page_meta": {"next": None},
            }

        result = rank_candidates_against_target_actives(
            "EXK", ["CCO", "CCN"], max_unique_actives=10, fetcher=fetcher
        )
        self.assertEqual("CHEMBL1", result["target"]["target_chembl_id"])
        self.assertEqual("CCO", result["results"][0]["input_smiles"])
        self.assertEqual(1.0, result["results"][0]["max_tanimoto"])

    def test_pdb_ligand_similarity_matches_structured_component(self) -> None:
        def fetcher(url: str) -> dict:
            if "/entry/" in url:
                return {"rcsb_entry_container_identifiers": {
                    "non_polymer_entity_ids": ["2"]
                }}
            if "/nonpolymer_entity/" in url:
                return {"pdbx_entity_nonpoly": {"comp_id": "LIG", "name": "Ligand"}}
            return {"rcsb_chem_comp_descriptor": {"SMILES_stereo": "c1ccccc1"}}

        result = rank_candidates_against_pdb_ligands(
            "1ABC", ["CCN", "c1ccccc1"], fetcher=fetcher
        )
        self.assertEqual("resolved", result["status"])
        self.assertEqual("c1ccccc1", result["results"][0]["input_smiles"])
        self.assertEqual(1.0, result["results"][0]["max_tanimoto"])

    def test_ethanol_descriptors_are_deterministic(self) -> None:
        result = describe_smiles("CCO")
        self.assertEqual("CCO", result.canonical_smiles)
        self.assertAlmostEqual(46.069, result.molecular_weight, places=3)
        self.assertEqual((1, 1), (result.hydrogen_bond_donors,
                                 result.hydrogen_bond_acceptors))
        self.assertEqual((), result.lipinski_violations)
        self.assertTrue(result.veber_pass)

    def test_similarity_ranking_preserves_identity_and_order(self) -> None:
        results = rank_similarity("CCO", ("c1ccccc1", "CCN", "CCO"))
        self.assertEqual("CCO", results[0].canonical_smiles)
        self.assertEqual(1.0, results[0].tanimoto)
        self.assertGreater(results[1].tanimoto, results[2].tanimoto)

    def test_invalid_smiles_fails_explicitly(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid SMILES"):
            describe_smiles("not-a-smiles")

    def test_server_lists_all_tools(self) -> None:
        server = McpServer()
        listed = server.handle({
            "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}
        })
        self.assertEqual(
            {"describe_molecules", "rank_molecular_similarity",
             "rank_target_active_similarity", "rank_pdb_ligand_similarity"},
            {tool["name"] for tool in listed["result"]["tools"]},
        )
        called = server.handle({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "rank_molecular_similarity",
                "arguments": {
                    "query_smiles": "CCO",
                    "candidate_smiles": ["CCO", "CCN"],
                },
            },
        })
        self.assertFalse(called["result"]["isError"])
        self.assertEqual(1.0, called["result"]["structuredContent"]["results"][0]["tanimoto"])

    def test_stdio_protocol_round_trip(self) -> None:
        requests = "\n".join((
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                "name": "describe_molecules", "arguments": {"smiles": ["CCO"]}
            }}),
        )) + "\n"
        completed = subprocess.run(
            ["python3", "./scripts/launch_chemistry_mcp.py"],
            input=requests,
            text=True,
            capture_output=True,
            cwd=PROJECT_ROOT,
            check=True,
        )
        responses = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual("frogent-chemistry", responses[0]["result"]["serverInfo"]["name"])
        self.assertEqual("CCO", responses[1]["result"]["structuredContent"]["results"][0]["canonical_smiles"])


if __name__ == "__main__":
    unittest.main()
