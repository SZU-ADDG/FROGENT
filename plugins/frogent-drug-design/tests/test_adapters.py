"""Fake-based checks for provider and v4 compatibility boundaries."""

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin import (  # noqa: E402
    ArtifactRef,
    ExecutionContext,
    LiteratureBatch,
    LiteratureQuery,
    LiteratureRecord,
    SearchPlan,
    V4ChatRequest,
    search_literature,
    v4_messages_to_events,
)


def make_plan() -> SearchPlan:
    return SearchPlan(
        "plan-1",
        "Does target X affect disease Y?",
        date(2026, 7, 15),
        ("target X AND disease Y",),
        ("pubmed",),
        ("Reports target X and disease Y",),
        ("No decision-relevant outcome",),
        ("One expansion wave adds no evidence",),
    )


def make_record(
    *,
    plan_id: str = "plan-1",
    source: str = "pubmed",
    published_on: date = date(2025, 2, 1),
) -> LiteratureRecord:
    return LiteratureRecord(
        "record-1",
        plan_id,
        source,
        "Target X in disease Y",
        datetime(2026, 7, 15, 12, tzinfo=timezone.utc),
        {"pmid": "123"},
        ArtifactRef("raw-1", "result.json", "application/json", "artifact://raw/1"),
        published_on,
        "Structured abstract.",
    )


class FakeLiteratureProvider:
    def __init__(
        self,
        record: LiteratureRecord,
        returned_query: LiteratureQuery | None = None,
    ) -> None:
        self.record = record
        self.returned_query = returned_query
        self.calls: list[tuple[LiteratureQuery, ExecutionContext]] = []

    def search(self, query: LiteratureQuery, context: ExecutionContext) -> LiteratureBatch:
        self.calls.append((query, context))
        return LiteratureBatch(self.returned_query or query, (self.record,), "fake-1")


class LiteratureProviderTests(unittest.TestCase):
    def test_planned_query_crosses_typed_provider_boundary(self) -> None:
        provider = FakeLiteratureProvider(make_record())
        context = ExecutionContext("user", "chat", "job", PLUGIN_ROOT)

        batch = search_literature(
            provider,
            make_plan(),
            "pubmed",
            "target X AND disease Y",
            context,
            limit=7,
        )

        self.assertEqual((make_record(),), batch.records)
        self.assertEqual(7, provider.calls[0][0].limit)
        self.assertIs(context, provider.calls[0][1])

    def test_unplanned_queries_never_reach_provider(self) -> None:
        provider = FakeLiteratureProvider(make_record())
        context = ExecutionContext("user", "chat", "job", PLUGIN_ROOT)
        with self.assertRaisesRegex(ValueError, "not present in search plan"):
            search_literature(provider, make_plan(), "pubmed", "other query", context)
        self.assertEqual([], provider.calls)

    def test_batch_rejects_misattributed_records(self) -> None:
        query = LiteratureQuery("plan-1", "pubmed", "query", date(2026, 7, 15))
        with self.assertRaisesRegex(ValueError, "source does not match"):
            LiteratureBatch(query, (make_record(source="other"),), "fake-1")

    def test_provider_batch_for_different_query_is_rejected(self) -> None:
        returned_query = LiteratureQuery(
            "plan-1", "pubmed", "different query", date(2026, 7, 15)
        )
        provider = FakeLiteratureProvider(make_record(), returned_query)
        context = ExecutionContext("user", "chat", "job", PLUGIN_ROOT)

        with self.assertRaisesRegex(ValueError, "different query"):
            search_literature(
                provider,
                make_plan(),
                "pubmed",
                "target X AND disease Y",
                context,
            )

    def test_batch_rejects_record_newer_than_plan_as_of(self) -> None:
        query = LiteratureQuery(
            "plan-1", "pubmed", "target X AND disease Y", date(2026, 7, 15)
        )
        with self.assertRaisesRegex(ValueError, "newer than the query as_of"):
            LiteratureBatch(
                query,
                (make_record(published_on=date(2026, 7, 16)),),
                "fake-1",
            )


class V4CompatibilityTests(unittest.TestCase):
    def test_request_aliases_create_explicit_execution_context(self) -> None:
        request = V4ChatRequest.from_mapping(
            {"user_id": "u1", "chat_id": "c1", "job_id": "j1", "query": "hello"}
        )
        self.assertEqual("hello", request.message)
        self.assertEqual("j1", request.execution_context(PLUGIN_ROOT).job_id)

    def test_empty_primary_fields_fall_back_to_valid_legacy_aliases(self) -> None:
        request = V4ChatRequest.from_mapping(
            {
                "user_id": "u1",
                "conversation_id": "  ",
                "chat_id": "legacy-chat",
                "job_id": "j1",
                "message": "",
                "query": "legacy query",
            }
        )
        self.assertEqual("legacy-chat", request.conversation_id)
        self.assertEqual("legacy query", request.message)

    def test_valid_primary_fields_take_priority_over_legacy_aliases(self) -> None:
        request = V4ChatRequest.from_mapping(
            {
                "user_id": "u1",
                "conversation_id": "primary-chat",
                "chat_id": "legacy-chat",
                "job_id": "j1",
                "message": "primary message",
                "query": "legacy query",
            }
        )
        self.assertEqual("primary-chat", request.conversation_id)
        self.assertEqual("primary message", request.message)

    def test_latest_v4_turn_becomes_typed_events(self) -> None:
        events = v4_messages_to_events(
            [
                {"role": "assistant", "content": "old answer"},
                {"role": "user", "content": "new question"},
                {
                    "role": "assistant",
                    "name": "Retrieval_Agent",
                    "function_call": {"name": "Pubmed_Search", "arguments": '{"query":"x"}'},
                },
                {"role": "function", "name": "Pubmed_Search", "content": "raw result"},
                {"role": "assistant", "name": "Retrieval_Agent", "content": "new answer"},
            ]
        )

        self.assertEqual(
            ("tool.started", "tool.completed", "message.delta", "done"),
            tuple(event.kind for event in events),
        )
        self.assertEqual("answer", events[2].payload["channel"])
        self.assertNotIn("old answer", repr(events))

    def test_missing_function_name_emits_error_event(self) -> None:
        events = v4_messages_to_events(({"role": "function", "content": "failure"},))
        self.assertEqual(("error", "done"), tuple(event.kind for event in events))

    def test_missing_assistant_function_name_emits_error_and_keeps_text(self) -> None:
        events = v4_messages_to_events(
            (
                {
                    "role": "assistant",
                    "name": "Retrieval_Agent",
                    "function_call": {"name": " ", "arguments": "{}"},
                    "reasoning_content": "diagnostic reasoning",
                    "content": "recoverable answer",
                },
            )
        )
        self.assertEqual(
            ("error", "message.delta", "message.delta", "done"),
            tuple(event.kind for event in events),
        )
        self.assertEqual("reasoning", events[1].payload["channel"])
        self.assertEqual("answer", events[2].payload["channel"])


if __name__ == "__main__":
    unittest.main()
