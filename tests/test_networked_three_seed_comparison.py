"""Regression tests for the network-enabled three-repeat comparison."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_clean_ten_model_panel as clean_runner
from scripts import run_networked_three_seed_comparison as runner
from scripts import run_networked_chinese_model_panel as chinese_runner


ROOT = Path(__file__).resolve().parents[1]


class NetworkedThreeSeedProtocolTests(unittest.TestCase):
    def test_protocol_freezes_three_distinct_seeds_and_expected_cell_count(self) -> None:
        protocol = runner._load_protocol(runner.DEFAULT_RUN_ROOT)
        self.assertEqual(protocol["seeds"], [20260807, 20260808, 20260809])
        self.assertEqual(len(set(protocol["seeds"])), 3)
        expected = 3 * (12 * 5 + 5 + 6)
        self.assertEqual(expected, 213)

    def test_direct_prompt_allows_only_public_web_from_resource_classes(self) -> None:
        prompt = clean_runner._prompt(
            "retrieve_known_targets",
            {1},
            allow_public_web=True,
            case_order_seed=20260807,
        )
        self.assertIn("General public live web search is available", prompt)
        for prohibited in (
            "local files",
            "shell",
            "MCP",
            "skills",
            "persistent memory",
            "FROGENT/user tools",
        ):
            self.assertIn(prohibited, prompt)
        self.assertNotIn('"answer"', prompt)
        self.assertNotIn('"gold"', prompt)

    def test_external_prompt_contains_public_sources_and_resource_boundary(self) -> None:
        protocol = runner._load_protocol(runner.DEFAULT_RUN_ROOT)
        robin = next(
            system for system in protocol["external_systems"]
            if system["name"] == "Robin"
        )
        prompt, resources = runner._external_prompt(
            robin, "retrieve_known_targets", [1], 20260807
        )
        self.assertIn("General public live web search is available", prompt)
        self.assertIn(robin["commit"], prompt)
        self.assertIn("EDISON_API_KEY is absent", prompt)
        self.assertTrue(resources["files"])
        self.assertTrue(all(record["sha256"] for record in resources["files"]))
        self.assertNotIn('"answer"', prompt)


class NetworkedTransportTests(unittest.TestCase):
    def test_openrouter_402_sets_global_budget_circuit_breaker_without_retry(self) -> None:
        calls = 0

        def insufficient_credit(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            raise RuntimeError("OpenRouter HTTP 402: Insufficient credits")

        chinese_runner.BUDGET_STOP.clear()
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as temporary, patch.object(
                clean_runner, "_openrouter_call", side_effect=insufficient_credit
            ):
                with self.assertRaises(chinese_runner.BudgetExhausted):
                    chinese_runner._run_batch(
                        ROOT,
                        Path(temporary),
                        {"model_id": "example/model", "display_name": "Example"},
                        "retrieve_known_targets",
                        20260808,
                        [1, 2, 3, 4, 5],
                        3,
                    )
            self.assertEqual(calls, 1)
            self.assertTrue(chinese_runner.BUDGET_STOP.is_set())
        finally:
            chinese_runner.BUDGET_STOP.clear()

    def test_openrouter_request_exposes_only_web_tool_and_real_seed(self) -> None:
        captured: dict[str, object] = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                envelope = {
                    "id": "response-1",
                    "model": "example/model",
                    "provider": "example",
                    "choices": [{
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps({
                                "results": [{"case_index": 1, "targets": ["EGFR"]}]
                            }),
                            "annotations": [{"type": "url_citation"}],
                        },
                    }],
                    "usage": {"server_tool_use": {"web_search_requests": 1}},
                }
                return json.dumps(envelope).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured.update(json.loads(request.data.decode("utf-8")))
            return Response()

        with tempfile.TemporaryDirectory(dir=ROOT) as temporary, patch.dict(
            os.environ, {"OPENROUTER_API_KEY": "test-key"}
        ), patch("urllib.request.urlopen", side_effect=fake_urlopen):
            outcome = clean_runner._openrouter_call(
                {
                    "model_id": "example/model",
                    "reasoning": {"enabled": False},
                    "seed": 20260809,
                    "allow_public_web": True,
                },
                "retrieve_known_targets",
                "test",
                clean_runner._schema("retrieve_known_targets", 1),
                Path(temporary),
            )
        self.assertEqual(captured["seed"], 20260809)
        self.assertEqual(captured["tools"], [{"type": "openrouter:web_search"}])
        self.assertEqual(outcome["transport_metadata"]["web_search_requests"], 1)

    def test_codex_command_disables_project_tools_and_retains_web_search(self) -> None:
        captured: list[str] = []

        def fake_run(args, **kwargs):
            if args[0] == "git":
                return subprocess.CompletedProcess(args, 0, "", "")
            captured.extend(args)
            output_path = Path(args[args.index("--output-last-message") + 1])
            output_path.write_text(
                json.dumps({
                    "results": [{"case_index": 1, "targets": ["EGFR"]}]
                }),
                encoding="utf-8",
            )
            events = "\n".join((
                json.dumps({
                    "type": "item.completed",
                    "item": {"type": "web_search", "query": "EGFR"},
                }),
                json.dumps({
                    "type": "item.completed",
                    "item": {"type": "agent_message"},
                }),
            ))
            return subprocess.CompletedProcess(args, 0, events, "")

        with tempfile.TemporaryDirectory(dir=ROOT) as temporary, patch.object(
            clean_runner.subprocess, "run", side_effect=fake_run
        ):
            outcome = clean_runner._codex_call(
                {
                    "model_id": "gpt-5.5",
                    "reasoning_effort": "low",
                    "allow_public_web": True,
                    "seed": 20260808,
                },
                "retrieve_known_targets",
                "test",
                clean_runner._schema("retrieve_known_targets", 1),
                Path(temporary),
            )
        command = " ".join(captured)
        self.assertIn('web_search="live"', command)
        self.assertIn("skills.include_instructions=false", command)
        self.assertIn("skills.bundled.enabled=false", command)
        for feature in ("shell_tool", "plugins", "apps", "memories", "multi_agent"):
            self.assertIn(f"--disable {feature}", command)
        self.assertEqual(outcome["transport_metadata"]["web_search_events"], 1)
        self.assertEqual(outcome["transport_metadata"]["prohibited_tool_events"], 0)


if __name__ == "__main__":
    unittest.main()
