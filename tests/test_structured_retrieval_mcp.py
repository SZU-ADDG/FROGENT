"""Tests for structured Open Targets and UniProtKB retrieval capabilities."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.research.structured_target_evidence import (  # noqa: E402
    list_target_drugbank_links,
    rank_disease_targets,
)
from mcp.structured_retrieval_mcp import McpServer  # noqa: E402


class StructuredRetrievalTests(unittest.TestCase):
    def test_open_targets_prefers_exact_disease_name(self) -> None:
        calls = []

        def fetcher(url, payload):
            calls.append(payload)
            if "Search" in payload["query"]:
                return {"data": {"search": {"hits": [
                    {"id": "EFO_OTHER", "name": "Related disease", "entity": "disease"},
                    {"id": "MONDO_1", "name": "Example disease", "entity": "disease"},
                ]}}}
            return {"data": {"disease": {"id": "MONDO_1", "name": "Example disease",
                "associatedTargets": {"count": 1, "rows": [{"score": 0.8,
                    "target": {"id": "ENSG1", "approvedSymbol": "GENE1",
                               "approvedName": "Gene one"}}]}}}}

        result = rank_disease_targets("Example disease", fetcher=fetcher)
        self.assertTrue(result["resolved_disease"]["exact_name_match"])
        self.assertEqual("GENE1", result["results"][0]["symbol"])
        self.assertEqual("MONDO_1", calls[1]["variables"]["id"])

    def test_uniprot_extracts_drugbank_cross_references(self) -> None:
        def fetcher(url, payload):
            return {"results": [{
                "primaryAccession": "P00001", "uniProtkbId": "EXAMPLE_HUMAN",
                "genes": [{"geneName": {"value": "EXAMPLE"}}],
                "proteinDescription": {"recommendedName": {"fullName": {
                    "value": "Example protein"}}},
                "uniProtKBCrossReferences": [
                    {"database": "DrugBank", "id": "DB00001",
                     "properties": [{"key": "GenericName", "value": "Example drug"}]},
                    {"database": "PDB", "id": "1ABC", "properties": []},
                ],
            }]}

        result = list_target_drugbank_links("EXAMPLE", fetcher=fetcher)
        self.assertTrue(result["resolved_target"]["exact_alias_match"])
        self.assertEqual([{"drugbank_id": "DB00001", "name": "Example drug"}],
                         result["results"])

    def test_server_lists_both_tools(self) -> None:
        response = McpServer().handle({"jsonrpc": "2.0", "id": 1,
                                       "method": "tools/list", "params": {}})
        self.assertEqual({"rank_disease_targets", "list_target_drugbank_links"},
                         {item["name"] for item in response["result"]["tools"]})

    def test_stdio_protocol_round_trip(self) -> None:
        request = json.dumps({"jsonrpc": "2.0", "id": 1,
                              "method": "tools/list", "params": {}}) + "\n"
        completed = subprocess.run(
            ["python3", "./mcp/structured_retrieval_mcp.py"], input=request,
            text=True, capture_output=True, cwd=PROJECT_ROOT, check=True,
        )
        response = json.loads(completed.stdout)
        self.assertEqual(2, len(response["result"]["tools"]))


if __name__ == "__main__":
    unittest.main()
