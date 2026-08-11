"""Behavior tests for the project-contained TrioWorkspace MCP server."""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MCP_ROOT = PROJECT_ROOT / "mcp"
sys.path.insert(0, str(MCP_ROOT))

from trioworkspace_client import TrioClient, TrioConfig, TrioRemoteError  # noqa: E402
from trioworkspace_contracts import multipart, task_form  # noqa: E402
from trioworkspace_mcp import McpServer  # noqa: E402
from trioworkspace_schemas import TOOLS  # noqa: E402
from trioworkspace_tools import TrioTools  # noqa: E402


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bytes, str]] = []
        self.task = {
            "id": "task-12345678",
            "engine": "triomol2",
            "status": "queued",
            "artifacts": [],
        }

    def json(
        self,
        method: str,
        path: str,
        *,
        body: bytes = b"",
        content_type: str = "application/octet-stream",
    ) -> object:
        self.calls.append((method, path, body, content_type))
        if path == "/healthz":
            return {"status": "ok"}
        if path == "/v1/tasks" and method == "GET":
            return {"tasks": [self.task]}
        if path == "/v1/tasks" and method == "POST":
            return self.task
        return self.task

    def download(self, task_id: str, artifact: dict[str, object]) -> dict[str, object]:
        return {"task_id": task_id, "artifact_id": artifact["id"]}


class TrioMcpTests(unittest.TestCase):
    def test_mcp_modules_are_flat_small_and_stdlib_only(self) -> None:
        local_modules = {
            "agent",
            "mcp",
            "chemistry_mcp",
            "chemistry_schemas",
            "chemistry_tools",
            "trioworkspace_client",
            "trioworkspace_contracts",
            "trioworkspace_mcp",
            "trioworkspace_remote_relay",
            "trioworkspace_schemas",
            "trioworkspace_tools",
        }
        self.assertEqual([], list(MCP_ROOT.glob("*/*.py")))
        for path in sorted(MCP_ROOT.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            self.assertLessEqual(len(source.splitlines()), 260, path.name)
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [alias.name.partition(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    roots = [(node.module or "").partition(".")[0]]
                else:
                    continue
                self.assertTrue(
                    all(root in sys.stdlib_module_names or root in local_modules for root in roots),
                    f"{path.name} imports an unsupported dependency: {roots}",
                )

    def test_mcp_initialize_and_ten_typed_tools(self) -> None:
        server = McpServer(TrioTools(FakeClient(), PROJECT_ROOT))  # type: ignore[arg-type]
        initialized = server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"},
            }
        )
        self.assertEqual("2025-06-18", initialized["result"]["protocolVersion"])
        listed = server.handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        tools = listed["result"]["tools"]
        self.assertEqual(10, len(tools))
        self.assertEqual({item["name"] for item in TOOLS}, {item["name"] for item in tools})
        self.assertTrue(all(item["inputSchema"]["additionalProperties"] is False for item in tools))

    def test_mol2_submission_preserves_exact_contract(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "runtime") as temporary:
            receptor = Path(temporary) / "target.pdb"
            receptor.write_text(
                "ATOM      1  CA  GLY A   1      10.000  11.000  12.000  1.00 20.00           C\n",
                encoding="ascii",
            )
            arguments = {
                "task_name": "bounded mol2",
                "target_name": "Target A",
                "receptor_pdb_path": str(receptor),
                "center": [1.0, 2.0, 3.0],
                "size": [20.0, 21.0, 22.0],
                "candidate_count": 3,
                "search_budget": 200,
                "seed": 19,
                "notes": "knowledge-led hypothesis panel",
            }
            fields, files = task_form("trio_submit_mol2", arguments, PROJECT_ROOT)
            content_type, body = multipart(fields, files)
            self.assertEqual("triomol2", fields["engine"])
            self.assertEqual("3", fields["candidateCount"])
            self.assertEqual("200", fields["searchBudget"])
            self.assertIn("multipart/form-data; boundary=", content_type)
            self.assertIn(b'name="receptor"; filename="target.pdb"', body)
            self.assertIn(b"ATOM      1", body)

    def test_engine_contracts_fail_closed_before_remote_call(self) -> None:
        client = FakeClient()
        tools = TrioTools(client, PROJECT_ROOT)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "exactly 200"):
            tools.call(
                "trio_submit_dna",
                {
                    "task_name": "invalid DNA",
                    "cell_context": "HepG2",
                    "reference_sequence": "ACGT",
                    "editable_start": 1,
                    "editable_end": 4,
                    "candidate_count": 1,
                    "seed": 1,
                },
            )
        self.assertEqual([], client.calls)

    def test_all_non_mol2_engine_forms_match_remote_contracts(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "runtime") as temporary:
            receptor = Path(temporary) / "target.pdb"
            receptor.write_text(
                "ATOM      1  CA  GLY A   1      10.000  11.000  12.000  1.00 20.00           C\n",
                encoding="ascii",
            )
            peptide, _ = task_form(
                "trio_submit_peptide",
                {
                    "task_name": "peptide",
                    "receptor_pdb_path": str(receptor),
                    "receptor_chain": "A",
                    "peptide_chain": "P",
                    "peptide_length": 12,
                    "search_budget": 8,
                },
                PROJECT_ROOT,
            )
            protac, _ = task_form(
                "trio_submit_protac",
                {
                    "task_name": "protac",
                    "target_system": "brd4-8g46",
                    "search_budget": 16,
                    "seed": 23,
                },
                PROJECT_ROOT,
            )
            ires, _ = task_form(
                "trio_submit_ires",
                {
                    "task_name": "ires",
                    "family": "CrPV",
                    "search_budget": 2,
                    "seed": 29,
                },
                PROJECT_ROOT,
            )
            dna, _ = task_form(
                "trio_submit_dna",
                {
                    "task_name": "dna",
                    "cell_context": "K562",
                    "reference_sequence": "ACGT" * 50,
                    "editable_start": 21,
                    "editable_end": 40,
                    "candidate_count": 4,
                    "seed": 31,
                },
                PROJECT_ROOT,
            )
        self.assertEqual(("triopep", "trioprotac", "trioires", "triodna"), tuple(
            form["engine"] for form in (peptide, protac, ires, dna)
        ))
        self.assertEqual("1", peptide["candidateCount"])
        self.assertEqual("brd4-8g46", protac["targetSystem"])
        self.assertEqual("CrPV", ires["family"])
        self.assertEqual("200", str(len(dna["referenceSequence"])))

    def test_remote_client_uses_ssh_and_decodes_bounded_response(self) -> None:
        seen: dict[str, object] = {}

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            seen["command"] = command
            seen["request"] = json.loads(kwargs["input"])  # type: ignore[arg-type]
            response = {
                "status": 200,
                "content_type": "application/json",
                "content_disposition": "",
                "etag": "",
                "body_base64": base64.b64encode(b'{"status":"ok"}').decode(),
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(response).encode(), b"")

        config = TrioConfig(
            PROJECT_ROOT,
            PROJECT_ROOT,
            "doomx_3nd",
            "ssh",
            "/work/doomx/TrioWorkspace/runtime/envs/control-plane/current/bin/python",
            "frogent-test",
            "frogent-test@localhost.invalid",
            1024,
            None,
        )
        client = TrioClient(config, "print('relay')", runner)
        self.assertEqual({"status": "ok"}, client.json("GET", "/healthz"))
        command = seen["command"]
        self.assertEqual("ssh", command[0])  # type: ignore[index]
        self.assertIn("BatchMode=yes", command)  # type: ignore[operator]
        self.assertEqual("frogent-test", seen["request"]["user_id"])  # type: ignore[index]
        self.assertNotIn("SHARED_SECRET", json.dumps(seen["request"]))

    def test_remote_http_error_is_safe_and_specific(self) -> None:
        def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
            response = {
                "status": 429,
                "content_type": "application/json",
                "content_disposition": "",
                "etag": "",
                "body_base64": base64.b64encode(b'{"message":"private task quota reached"}').decode(),
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(response).encode(), b"")

        config = TrioConfig(
            PROJECT_ROOT,
            PROJECT_ROOT,
            "doomx_3nd",
            "ssh",
            "/work/doomx/TrioWorkspace/runtime/envs/control-plane/current/bin/python",
            "frogent-test",
            "frogent-test@localhost.invalid",
            1024,
            None,
        )
        with self.assertRaisesRegex(TrioRemoteError, "quota reached"):
            TrioClient(config, "print('relay')", runner).json("GET", "/v1/tasks")

    def test_artifact_download_verifies_and_reuses_exact_bytes(self) -> None:
        payload = b"verified trio artifact\n"

        def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
            response = {
                "status": 200,
                "content_type": "text/plain",
                "content_disposition": 'attachment; filename="result.txt"',
                "etag": "",
                "body_base64": base64.b64encode(payload).decode(),
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(response).encode(), b"")

        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "runtime") as temporary:
            runtime_root = Path(temporary)
            config = TrioConfig(
                runtime_root,
                PROJECT_ROOT,
                "doomx_3nd",
                "ssh",
                "/work/doomx/TrioWorkspace/runtime/envs/control-plane/current/bin/python",
                "frogent-test",
                "frogent-test@localhost.invalid",
                1024,
                None,
            )
            client = TrioClient(config, "print('relay')", runner)
            artifact = {
                "id": "artifact-12345678",
                "filename": "result.txt",
                "byteSize": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "contentType": "text/plain",
            }
            first = client.download("task-12345678", artifact)
            second = client.download("task-12345678", artifact)
            self.assertEqual(first, second)
            self.assertEqual(payload, Path(first["local_path"]).read_bytes())


if __name__ == "__main__":
    unittest.main()
