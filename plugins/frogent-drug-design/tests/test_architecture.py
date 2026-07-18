"""Regression checks for the plugin's intentionally small architecture."""

import ast
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin import (  # noqa: E402
    CAPABILITIES,
    SERVER_NAMES,
    Capability,
    CapabilityRegistry,
    ExecutionContext,
    StreamEvent,
    ToolResult,
    build_registry,
    load_app_connectors,
    load_mcp_servers,
)

CONTROL_FLOW_NODES = (ast.For, ast.If, ast.Match, ast.Try, ast.While, ast.With)


def max_control_flow_nesting(node: ast.AST, depth: int = 0) -> int:
    current_depth = depth + int(isinstance(node, CONTROL_FLOW_NODES))
    child_depths = [
        max_control_flow_nesting(child, current_depth)
        for child in ast.iter_child_nodes(node)
    ]
    return max((current_depth, *child_depths))


class ArchitectureTests(unittest.TestCase):
    def test_connector_manifests_match_catalog(self) -> None:
        servers = load_mcp_servers(PLUGIN_ROOT / ".mcp.json")
        self.assertEqual(9, len(servers))
        self.assertEqual(SERVER_NAMES, {server.name for server in servers})
        self.assertEqual((), load_app_connectors(PLUGIN_ROOT / ".app.json"))

    def test_capability_catalog_is_unique_and_complete(self) -> None:
        registry = build_registry()
        tool_pairs = {(item.server, item.tool) for item in CAPABILITIES}
        self.assertEqual(19, len(registry))
        self.assertEqual(len(CAPABILITIES), len(tool_pairs))
        registry.require_servers(SERVER_NAMES)

    def test_registry_rejects_duplicate_ids(self) -> None:
        capability = Capability("test.id", "server", "tool", "summary")
        with self.assertRaisesRegex(ValueError, "duplicate capability id"):
            CapabilityRegistry((capability, capability))

    def test_execution_context_requires_absolute_workspace(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute path"):
            ExecutionContext("user", "conversation", "job", Path("relative"))

    def test_result_and_event_invariants(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot contain an error"):
            ToolResult(ok=True, error="unexpected")
        with self.assertRaisesRegex(ValueError, "must contain an error"):
            ToolResult(ok=False)
        with self.assertRaisesRegex(ValueError, "unsupported event kind"):
            StreamEvent(kind="unknown", payload={})  # type: ignore[arg-type]

    def test_plugin_manifest_references_flat_components(self) -> None:
        manifest_path = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("frogent-drug-design", manifest["name"])
        self.assertEqual("./skills/", manifest["skills"])
        self.assertEqual("./.mcp.json", manifest["mcpServers"])
        self.assertEqual("./.app.json", manifest["apps"])

    def test_runtime_package_stays_small_flat_and_stdlib_only(self) -> None:
        package_dir = PLUGIN_ROOT / "frogent_plugin"
        self.assertEqual([], list(package_dir.glob("*/*.py")))

        for module_path in sorted(package_dir.glob("*.py")):
            source = module_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(module_path))
            self.assertLessEqual(len(source.splitlines()), 260, module_path.name)
            self.assertLessEqual(max_control_flow_nesting(tree), 3, module_path.name)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [alias.name.partition(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    roots = [(node.module or "").partition(".")[0]]
                else:
                    continue
                self.assertTrue(
                    all(root in sys.stdlib_module_names for root in roots),
                    f"{module_path.name} imports a non-stdlib dependency: {roots}",
                )

    def test_skills_have_finished_metadata_and_prompts(self) -> None:
        skill_names = {
            "design-ligand",
            "discover-target",
            "evaluate-candidate",
            "optimize-peptide",
            "optimize-small-molecule",
            "plan-literature-search",
            "plan-retrosynthesis",
            "prepare-molecule",
            "research-biomedical-literature",
            "screen-literature-evidence",
            "synthesize-biomedical-evidence",
        }
        self.assertEqual(
            skill_names,
            {path.name for path in (PLUGIN_ROOT / "skills").iterdir() if path.is_dir()},
        )

        for name in skill_names:
            skill_text = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            prompt_text = (
                PLUGIN_ROOT / "skills" / name / "agents" / "openai.yaml"
            ).read_text(encoding="utf-8")
            self.assertIn(f"name: {name}", skill_text)
            self.assertNotIn("TODO", skill_text)
            self.assertIn(f"${name}", prompt_text)


if __name__ == "__main__":
    unittest.main()
