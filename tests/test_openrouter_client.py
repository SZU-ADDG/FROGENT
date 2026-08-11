"""Behavior tests for the pinned OpenRouter FROGENT role boundary."""

import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.llm.client_factory import build_llm_client  # noqa: E402
from agent.llm.openrouter_client import OpenRouterClient  # noqa: E402


class OpenRouterClientTests(unittest.TestCase):
    def test_factory_selects_exact_openrouter_model(self):
        client = build_llm_client(
            ROOT,
            backend="openrouter",
            deepseek_model="deepseek-v4-flash",
            deepseek_base_url="https://api.deepseek.com",
            deepseek_timeout=None,
            codex_model="gpt-5.6-luna",
            codex_reasoning_effort="max",
            codex_executable="codex",
            codex_timeout=None,
            openrouter_model="moonshotai/kimi-k3",
            openrouter_reasoning={"enabled": False},
        )
        self.assertEqual("moonshotai/kimi-k3", client.model)
        self.assertEqual({"enabled": False}, client.reasoning)

    def test_structured_request_pins_schema_provider_and_hides_key(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {
                "id": "response-1",
                "model": "qwen/qwen3.8-max",
                "provider": "Alibaba",
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"answer":"ok"}'},
                }],
                "usage": {"cost": 0.01},
            }

        schema = {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        }
        client = OpenRouterClient(
            ROOT,
            model="qwen/qwen3.8-max",
            api_key="test-only-key",
            timeout=13,
            reasoning={"effort": "low"},
            provider_order=("Alibaba",),
            transport=transport,
        )
        result = client.generate("reader", "answer", {"input": "safe"}, schema=schema)
        self.assertEqual({"answer": "ok"}, result)
        url, headers, payload, timeout = calls[0]
        self.assertEqual(("https://openrouter.ai/api/v1/chat/completions", 13), (url, timeout))
        self.assertEqual("qwen/qwen3.8-max", payload["model"])
        self.assertEqual(["Alibaba"], payload["provider"]["order"])
        self.assertFalse(payload["provider"]["allow_fallbacks"])
        self.assertEqual(schema, payload["response_format"]["json_schema"]["schema"])
        self.assertNotIn("test-only-key", json.dumps(payload))
        self.assertEqual("Bearer test-only-key", headers["Authorization"])
        self.assertEqual("Alibaba", client.last_metadata["provider"])

    def test_client_fails_closed_on_missing_key_bad_json_and_external_cwd(self):
        client = OpenRouterClient(
            ROOT,
            model="qwen/qwen3.8-max",
            api_key="",
            transport=lambda *args: {},
        )
        with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY"):
            client.generate("reader", "contract", {})
        bad = OpenRouterClient(
            ROOT,
            model="qwen/qwen3.8-max",
            api_key="x",
            transport=lambda *args: {
                "choices": [{"message": {"content": "[]"}}],
            },
        )
        with self.assertRaisesRegex(ValueError, "object"):
            bad.generate("reader", "contract", {})
        with self.assertRaisesRegex(ValueError, "inside project root"):
            bad.generate("reader", "contract", {}, cwd=ROOT.parent)

    def test_retryable_transport_error_uses_bounded_attempts(self):
        calls = []

        def transport(*args):
            calls.append(args)
            if len(calls) < 3:
                raise RuntimeError("OpenRouter request failed with HTTP 429: retry")
            return {
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"answer":"ok"}'},
                }],
            }

        client = OpenRouterClient(
            ROOT,
            model="minimax/minimax-m3",
            api_key="test-only-key",
            max_attempts=3,
            retry_base_seconds=0,
            transport=transport,
        )
        self.assertEqual(
            {"answer": "ok"},
            client.generate("reader", "answer", {"input": "safe"}),
        )
        self.assertEqual(3, len(calls))
        self.assertEqual(3, client.last_metadata["request_attempts"])

    def test_non_retryable_transport_error_fails_immediately(self):
        calls = []

        def transport(*args):
            calls.append(args)
            raise RuntimeError("OpenRouter request failed with HTTP 400: invalid")

        client = OpenRouterClient(
            ROOT,
            model="qwen/qwen3.8-max",
            api_key="test-only-key",
            max_attempts=4,
            retry_base_seconds=0,
            transport=transport,
        )
        with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
            client.generate("reader", "answer", {"input": "safe"})
        self.assertEqual(1, len(calls))

    def test_invalid_structured_content_is_retried_when_enabled(self):
        calls = []

        def transport(*args):
            calls.append(args)
            content = None if len(calls) == 1 else '{"answer":"ok"}'
            return {
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": content},
                }],
            }

        client = OpenRouterClient(
            ROOT,
            model="deepseek/deepseek-v4-flash-0731",
            api_key="test-only-key",
            max_attempts=2,
            retry_base_seconds=0,
            transport=transport,
        )
        self.assertEqual(
            {"answer": "ok"},
            client.generate("reader", "answer", {"input": "safe"}),
        )
        self.assertEqual(2, len(calls))
        self.assertEqual(2, client.last_metadata["request_attempts"])

    def test_provider_fallbacks_are_explicitly_opt_in(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append(payload)
            return {
                "provider": "alternate",
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"answer":"ok"}'},
                }],
            }

        client = OpenRouterClient(
            ROOT,
            model="minimax/minimax-m3",
            api_key="test-only-key",
            allow_provider_fallbacks=True,
            transport=transport,
        )
        client.generate("reader", "answer", {"input": "safe"})
        self.assertTrue(calls[0]["provider"]["allow_fallbacks"])
        self.assertEqual("alternate", client.last_metadata["provider"])


if __name__ == "__main__":
    unittest.main()
