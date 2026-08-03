"""Regression checks for the Agent-first repository architecture."""

import ast
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent import (  # noqa: E402
    CAPABILITIES,
    SERVER_NAMES,
    Capability,
    CapabilityRegistry,
    ExecutionContext,
    StreamEvent,
    ToolResult,
    build_registry,
    load_app_connectors,
)
from agent.core.connector_inventory import load_connector_inventory  # noqa: E402
from agent.core.trioworkspace_catalog import (  # noqa: E402
    CURRENT_CAPABILITIES,
    CURRENT_SERVER_NAMES,
    build_current_registry,
)

CONTROL_FLOW_NODES = (ast.For, ast.If, ast.Match, ast.Try, ast.While, ast.With)
DOMAIN_DEPENDENCIES = {
    "core": set(),
    "research": {"core"},
    "llm": {"core", "research"},
    "design": {"core", "llm"},
    "molecular": {"core", "llm", "research"},
    "docking": {"core", "llm", "molecular", "research"},
    "app": {"core", "design", "docking", "llm", "molecular", "research"},
    "evaluation": set(),
}


def max_control_flow_nesting(node: ast.AST, depth: int = 0) -> int:
    current_depth = depth + int(isinstance(node, CONTROL_FLOW_NODES))
    child_depths = [
        max_control_flow_nesting(child, current_depth)
        for child in ast.iter_child_nodes(node)
    ]
    return max((current_depth, *child_depths))


class ArchitectureTests(unittest.TestCase):
    def test_connector_manifests_match_catalog(self) -> None:
        servers = load_connector_inventory(PROJECT_ROOT / ".mcp.json")
        self.assertEqual(10, len(servers))
        self.assertEqual(CURRENT_SERVER_NAMES, {server.name for server in servers})
        trio = next(server for server in servers if server.name == "trio-workspace")
        self.assertEqual("stdio", trio.transport)
        self.assertEqual("python3", trio.command)
        self.assertEqual(("./mcp/trioworkspace_mcp.py",), trio.args)
        self.assertEqual((), load_app_connectors(PROJECT_ROOT / ".app.json"))

    def test_capability_catalog_is_unique_and_complete(self) -> None:
        registry = build_registry()
        self.assertEqual(19, len(registry))
        registry.require_servers(SERVER_NAMES)
        current = build_current_registry()
        tool_pairs = {(item.server, item.tool) for item in CURRENT_CAPABILITIES}
        self.assertEqual(29, len(current))
        self.assertEqual(len(CURRENT_CAPABILITIES), len(tool_pairs))
        current.require_servers(CURRENT_SERVER_NAMES)

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

    def test_plugin_manifest_references_root_components(self) -> None:
        manifest_path = PROJECT_ROOT / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("frogent-drug-design", manifest["name"])
        self.assertEqual("./skills/", manifest["skills"])
        self.assertEqual("./.mcp.json", manifest["mcpServers"])
        self.assertEqual("./.app.json", manifest["apps"])

    def test_agent_packages_stay_small_flat_and_stdlib_only(self) -> None:
        package_dir = PROJECT_ROOT / "agent"
        self.assertEqual(
            {"app", "core", "design", "docking", "evaluation", "llm", "molecular", "research"},
            {path.name for path in package_dir.iterdir()
             if path.is_dir() and path.name != "__pycache__"},
        )

        for module_path in sorted(package_dir.rglob("*.py")):
            self.assertLessEqual(
                len(module_path.relative_to(package_dir).parts), 2, module_path
            )
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
                    all(root == "agent" or root in sys.stdlib_module_names for root in roots),
                    f"{module_path.name} imports a non-stdlib dependency: {roots}",
                )

    def test_agent_domain_dependencies_are_acyclic(self) -> None:
        package_dir = PROJECT_ROOT / "agent"
        actual = {domain: set() for domain in DOMAIN_DEPENDENCIES}
        for module_path in package_dir.rglob("*.py"):
            relative = module_path.relative_to(package_dir)
            if len(relative.parts) != 2:
                continue
            source_domain = relative.parts[0]
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    parts = name.split(".")
                    if (
                        len(parts) > 1
                        and parts[0] == "agent"
                        and parts[1] in DOMAIN_DEPENDENCIES
                        and parts[1] != source_domain
                    ):
                        actual[source_domain].add(parts[1])
        for domain, dependencies in actual.items():
            self.assertLessEqual(
                dependencies,
                DOMAIN_DEPENDENCIES[domain],
                f"{domain} has a reverse or undeclared domain dependency",
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
            "prioritize-design-hypotheses",
            "research-biomedical-literature",
            "run-trioworkspace",
            "screen-literature-evidence",
            "synthesize-biomedical-evidence",
        }
        self.assertEqual(
            skill_names,
            {path.name for path in (PROJECT_ROOT / "skills").iterdir() if path.is_dir()},
        )

        for name in skill_names:
            skill_text = (PROJECT_ROOT / "skills" / name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            prompt_text = (
                PROJECT_ROOT / "skills" / name / "agents" / "openai.yaml"
            ).read_text(encoding="utf-8")
            self.assertIn(f"name: {name}", skill_text)
            self.assertNotIn("TODO", skill_text)
            self.assertIn(f"${name}", prompt_text)

    def test_design_skills_preserve_knowledge_led_semantic_contract(self) -> None:
        skill_root = PROJECT_ROOT / "skills"
        hypothesis_skills = {
            "design-ligand", "discover-target", "evaluate-candidate", "optimize-peptide",
            "optimize-small-molecule", "plan-retrosynthesis",
        }
        for name in hypothesis_skills:
            text = (skill_root / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("$prioritize-design-hypotheses", text, name)
        core = (skill_root / "prioritize-design-hypotheses" / "SKILL.md").read_text(
            encoding="utf-8")
        for phrase in ("qualitative", "quantitative", "hybrid", "world knowledge",
                       "three to six", "Preserve a useful recommendation",
                       "Lead with the ranked recommendations", "decisive experiment"):
            self.assertIn(phrase, core)
        peptide = (skill_root / "optimize-peptide" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("target-independent branch", peptide)
        self.assertIn("protein docking is not a prerequisite", peptide)
        target = (skill_root / "discover-target" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("clearly labeled causal or mechanistic target hypothesis", target)
        retro = (skill_root / "plan-retrosynthesis" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("reagent classes and condition families as expert route hypotheses", retro)
        research = (skill_root / "research-biomedical-literature" / "SKILL.md").read_text(
            encoding="utf-8")
        self.assertIn("hand the admitted evidence IDs", research)


if __name__ == "__main__":
    unittest.main()
