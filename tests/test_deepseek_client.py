"""Behavior tests for the DeepSeek FROGENT Agent boundary and canary."""

import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.llm.deepseek_client import DeepSeekClient  # noqa: E402
from agent.llm.client_factory import build_llm_client  # noqa: E402
from scripts.probe_deepseek_tool_call import run_canary  # noqa: E402


class DeepSeekClientTests(unittest.TestCase):
    def test_factory_selects_pinned_deepseek_and_terra_boundaries(self):
        deepseek = build_llm_client(
            ROOT, backend="deepseek", deepseek_model="deepseek-v4-flash",
            deepseek_base_url="https://api.deepseek.com", deepseek_timeout=None,
            codex_model="gpt-5.6-terra", codex_executable="codex", codex_timeout=None)
        self.assertEqual("deepseek-v4-flash", deepseek.model)
        terra = build_llm_client(
            ROOT, backend="codex", deepseek_model="deepseek-v4-flash",
            deepseek_base_url="https://api.deepseek.com", deepseek_timeout=None,
            codex_model="gpt-5.6-terra", codex_executable="codex", codex_timeout=None)
        self.assertEqual("gpt-5.6-terra", terra.model)
        with self.assertRaisesRegex(ValueError, "FROGENT_LLM_BACKEND"):
            build_llm_client(
                ROOT, backend="unknown", deepseek_model="deepseek-v4-flash",
                deepseek_base_url="https://api.deepseek.com", deepseek_timeout=None,
                codex_model="gpt-5.6-terra", codex_executable="codex", codex_timeout=None)

    def test_structured_client_pins_model_schema_and_hides_key_from_payload(self):
        calls = []

        def transport(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {"choices": [{"message": {"content": '{"answer":"ok"}'}}]}

        schema = {"type": "object", "properties": {"answer": {"type": "string"}},
                  "required": ["answer"], "additionalProperties": False}
        client = DeepSeekClient(ROOT, api_key="test-only-key", timeout=11, transport=transport)
        result = client.generate("reader", "answer the task", {"input": "safe"}, schema=schema)
        self.assertEqual({"answer": "ok"}, result)
        url, headers, payload, timeout = calls[0]
        self.assertEqual(("https://api.deepseek.com/chat/completions", 11), (url, timeout))
        self.assertEqual("deepseek-v4-flash", payload["model"])
        self.assertEqual({"type": "json_object"}, payload["response_format"])
        self.assertIn("JSON Schema", payload["messages"][0]["content"])
        self.assertNotIn("test-only-key", json.dumps(payload))
        self.assertEqual("Bearer test-only-key", headers["Authorization"])

    def test_client_fails_closed_on_missing_key_bad_json_and_external_cwd(self):
        client = DeepSeekClient(ROOT, api_key="", transport=lambda *args: {})
        with self.assertRaisesRegex(RuntimeError, "DEEPSEEK_API_KEY"):
            client.generate("reader", "contract", {})
        bad = DeepSeekClient(ROOT, api_key="x", transport=lambda *args: {
            "choices": [{"message": {"content": "[]"}}]})
        with self.assertRaisesRegex(ValueError, "object"):
            bad.generate("reader", "contract", {})
        with self.assertRaisesRegex(ValueError, "inside project root"):
            bad.generate("reader", "contract", {}, cwd=ROOT.parent)

    def test_tool_call_canary_requires_one_exact_call(self):
        response = {"model": "deepseek-v4-flash", "choices": [{"finish_reason": "tool_calls",
                    "message": {"tool_calls": [{"function": {
                        "name": "frogent_canary_echo", "arguments": '{"value":"ok"}'}}]}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        captured = []
        report = run_canary(lambda payload: captured.append(payload) or response)
        self.assertEqual(("pass", "frogent_canary_echo", False),
                         (report["status"], report["tool_call"]["name"],
                          report["credential_persisted"]))
        self.assertEqual({"type": "disabled"}, captured[0]["thinking"])
        self.assertEqual("frogent_canary_echo",
                         captured[0]["tool_choice"]["function"]["name"])
        with self.assertRaisesRegex(RuntimeError, "unexpected"):
            run_canary(lambda payload: {"choices": [{"message": {"tool_calls": [
                {"function": {"name": "wrong", "arguments": '{}'}}]}}]})


if __name__ == "__main__":
    unittest.main()
