"""Control-plane tests for composed literature retrieval."""

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin import (  # noqa: E402
    ArtifactRef,
    EvidenceExcerpt,
    EvidenceStrength,
    ExecutionContext,
    HarnessPhase,
    HarnessPolicy,
    HarnessState,
    LiteratureBatch,
    LiteratureQuery,
    LiteratureRecord,
    RetrievalCall,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
    SearchPlan,
    admit_evidence,
    run_retrieval,
)

AS_OF = date(2026, 7, 15)
NOW = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)


def make_plan() -> SearchPlan:
    return SearchPlan(
        "plan-1",
        "Does target X affect disease Y?",
        AS_OF,
        ("target X AND disease Y", "target X mechanism"),
        ("pubmed", "trials"),
        ("Reports target X",),
        ("No decision-relevant outcome",),
        ("One expansion wave adds no evidence",),
    )


def make_record(
    record_id: str = "record-1",
    *,
    source: str = "pubmed",
    published_on: date = date(2025, 1, 1),
) -> LiteratureRecord:
    return LiteratureRecord(
        record_id,
        "plan-1",
        source,
        f"Study {record_id}",
        NOW,
        {"provider_id": record_id},
        ArtifactRef(
            f"raw-{record_id}",
            f"{record_id}.json",
            "application/json",
            f"artifact://raw/{record_id}",
        ),
        published_on,
        "Structured abstract.",
    )


class FakeProvider:
    def __init__(
        self,
        records: tuple[LiteratureRecord, ...] = (),
        *,
        returned_query: LiteratureQuery | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.records = records
        self.returned_query = returned_query
        self.failure = failure
        self.calls: list[LiteratureQuery] = []

    def search(self, query: LiteratureQuery, context: ExecutionContext) -> LiteratureBatch:
        self.calls.append(query)
        if self.failure:
            raise self.failure
        return LiteratureBatch(self.returned_query or query, self.records, "fake-1")


def context() -> ExecutionContext:
    return ExecutionContext("user", "conversation", "job", PLUGIN_ROOT)


def state(*, tool_calls: int = 0) -> HarnessState:
    return HarnessState(
        "run-1",
        AS_OF,
        phase=HarnessPhase.PLANNING,
        tool_call_count=tool_calls,
    )


def policy(*, max_tool_calls: int = 3) -> HarnessPolicy:
    return HarnessPolicy(
        max_tool_calls=max_tool_calls,
        allowed_capabilities=frozenset({"literature.pubmed", "literature.trials"}),
    )


class RetrievalCompositionTests(unittest.TestCase):
    def test_success_is_typed_deterministic_and_raw_only(self) -> None:
        provider = FakeProvider((make_record(),))
        call = RetrievalCall("literature.pubmed", "pubmed", "target X AND disease Y", 5)

        result = run_retrieval(
            make_plan(), (call,), {"literature.pubmed": provider}, context(), state(), policy()
        )

        self.assertTrue(result.ok)
        self.assertEqual(1, result.completed_calls)
        self.assertEqual(("tool.started", "tool.completed", "done"), tuple(e.kind for e in result.events))
        self.assertEqual((make_record(),), result.ledger.records())
        self.assertEqual((), result.ledger.admitted())
        self.assertEqual((), result.state.memory_evidence_ids)
        self.assertEqual(1, result.state.tool_call_count)
        self.assertEqual(1, result.events[-1].payload["raw_hit_count"])
        self.assertEqual(1, result.events[-1].payload["unique_record_count"])

    def test_consistent_duplicate_preserves_two_links_and_one_record(self) -> None:
        record = make_record()
        first = FakeProvider((record,))
        second = FakeProvider((record,))
        calls = (
            RetrievalCall("literature.pubmed", "pubmed", "target X AND disease Y"),
            RetrievalCall("literature.pubmed", "pubmed", "target X mechanism"),
        )
        result = run_retrieval(
            make_plan(),
            calls,
            {"literature.pubmed": first},
            context(),
            state(),
            policy(),
        )
        self.assertTrue(result.ok)
        self.assertEqual((record,), result.ledger.records())
        self.assertEqual((0, 1), tuple(hit.call_index for hit in result.hits))
        self.assertEqual(
            ("target X AND disease Y", "target X mechanism"),
            tuple(hit.query for hit in result.hits),
        )
        self.assertEqual(2, result.events[-1].payload["raw_hit_count"])
        self.assertEqual(1, result.events[-1].payload["unique_record_count"])

    def test_conflicting_duplicate_fails_closed_after_first_canonical_record(self) -> None:
        canonical = make_record()
        conflict = LiteratureRecord(
            canonical.id,
            canonical.plan_id,
            canonical.source,
            "Conflicting title",
            canonical.retrieved_at,
            canonical.identifiers,
            canonical.raw_artifact,
            canonical.published_on,
            canonical.abstract,
        )
        provider = FakeProvider((canonical, conflict))
        call = RetrievalCall("literature.pubmed", "pubmed", "target X AND disease Y")
        result = run_retrieval(
            make_plan(), (call,), {"literature.pubmed": provider}, context(), state(), policy()
        )
        self.assertFalse(result.ok)
        self.assertEqual((canonical,), result.ledger.records())
        self.assertEqual(2, len(result.hits))
        self.assertEqual(("record-1", "record-1"), tuple(hit.record_id for hit in result.hits))
        self.assertEqual(("tool.started", "error", "done"), tuple(e.kind for e in result.events))
        self.assertEqual(2, result.events[-1].payload["raw_hit_count"])
        self.assertEqual(1, result.events[-1].payload["unique_record_count"])

    def test_empty_execution_plan_fails_without_provider_calls(self) -> None:
        provider = FakeProvider()
        result = run_retrieval(
            make_plan(), (), {"literature.pubmed": provider}, context(), state(), policy()
        )
        self.assertFalse(result.ok)
        self.assertEqual(HarnessPhase.FAILED, result.state.phase)
        self.assertEqual([], provider.calls)
        self.assertEqual(("error", "done"), tuple(event.kind for event in result.events))
        self.assertEqual(0, result.events[-1].payload["raw_hit_count"])
        self.assertEqual(0, result.events[-1].payload["unique_record_count"])

    def test_one_explicit_pair_does_not_expand_across_plan_lists(self) -> None:
        provider = FakeProvider()
        pair = RetrievalCall(
            "literature.pubmed", "pubmed", "target X mechanism"
        )
        result = run_retrieval(
            make_plan(),
            (pair,),
            {"literature.pubmed": provider},
            context(),
            state(),
            policy(),
        )
        self.assertTrue(result.ok)
        self.assertEqual(1, len(provider.calls))
        self.assertEqual("pubmed", provider.calls[0].source)
        self.assertEqual("target X mechanism", provider.calls[0].query)

    def test_unplanned_pair_is_rejected_before_provider(self) -> None:
        provider = FakeProvider()
        invalid_pair = RetrievalCall(
            "literature.pubmed", "unplanned-source", "target X AND disease Y"
        )
        result = run_retrieval(
            make_plan(),
            (invalid_pair,),
            {"literature.pubmed": provider},
            context(),
            state(),
            policy(),
        )
        self.assertFalse(result.ok)
        self.assertEqual([], provider.calls)
        self.assertEqual(("error", "done"), tuple(e.kind for e in result.events))

    def test_unknown_and_unallowed_capabilities_have_zero_provider_calls(self) -> None:
        unknown = FakeProvider()
        denied = FakeProvider()
        call = RetrievalCall("literature.unknown", "pubmed", "target X AND disease Y")
        unknown_result = run_retrieval(
            make_plan(), (call,), {}, context(), state(), policy()
        )
        denied_result = run_retrieval(
            make_plan(),
            (call,),
            {"literature.unknown": denied},
            context(),
            state(),
            policy(),
        )
        self.assertFalse(unknown_result.ok)
        self.assertFalse(denied_result.ok)
        self.assertEqual([], unknown.calls)
        self.assertEqual([], denied.calls)

    def test_phase_and_tool_budget_denials_have_zero_provider_calls(self) -> None:
        provider = FakeProvider()
        call = RetrievalCall("literature.pubmed", "pubmed", "target X AND disease Y")
        intake = HarnessState("run-intake", AS_OF)
        phase_result = run_retrieval(
            make_plan(), (call,), {"literature.pubmed": provider}, context(), intake, policy()
        )
        budget_result = run_retrieval(
            make_plan(),
            (call,),
            {"literature.pubmed": provider},
            context(),
            state(tool_calls=1),
            policy(max_tool_calls=1),
        )
        self.assertFalse(phase_result.ok)
        self.assertFalse(budget_result.ok)
        self.assertEqual([], provider.calls)

    def test_mismatched_batch_and_future_record_are_auditable_failures(self) -> None:
        call = RetrievalCall("literature.pubmed", "pubmed", "target X AND disease Y")
        mismatch = FakeProvider(
            returned_query=LiteratureQuery(
                "plan-1", "pubmed", "target X mechanism", AS_OF
            )
        )
        future = FakeProvider((make_record(published_on=date(2026, 7, 16)),))
        mismatch_result = run_retrieval(
            make_plan(), (call,), {"literature.pubmed": mismatch}, context(), state(), policy()
        )
        future_result = run_retrieval(
            make_plan(), (call,), {"literature.pubmed": future}, context(), state(), policy()
        )
        for result in (mismatch_result, future_result):
            self.assertEqual(("tool.started", "error", "done"), tuple(e.kind for e in result.events))
            self.assertEqual((), result.ledger.records())
            self.assertEqual((), result.state.memory_evidence_ids)
            self.assertIn("error_type", result.events[1].payload)

    def test_partial_failure_preserves_raw_ledger_and_memory_isolation(self) -> None:
        first = FakeProvider((make_record(),))
        second = FakeProvider(failure=RuntimeError("provider unavailable"))
        calls = (
            RetrievalCall("literature.pubmed", "pubmed", "target X AND disease Y"),
            RetrievalCall("literature.trials", "trials", "target X mechanism"),
        )
        result = run_retrieval(
            make_plan(),
            calls,
            {"literature.pubmed": first, "literature.trials": second},
            context(),
            state(),
            policy(),
        )
        self.assertFalse(result.ok)
        self.assertEqual(1, result.completed_calls)
        self.assertEqual((make_record(),), result.ledger.records())
        self.assertEqual((), result.ledger.admitted())
        self.assertEqual((), result.state.memory_evidence_ids)
        self.assertEqual(
            ("tool.started", "tool.completed", "tool.started", "error", "done"),
            tuple(event.kind for event in result.events),
        )

    def test_raw_record_needs_screening_and_excerpt_before_memory(self) -> None:
        provider = FakeProvider((make_record(),))
        call = RetrievalCall("literature.pubmed", "pubmed", "target X AND disease Y")
        result = run_retrieval(
            make_plan(), (call,), {"literature.pubmed": provider}, context(), state(), policy()
        )
        evidence = EvidenceExcerpt(
            "evidence-1",
            "record-1",
            "Target X is associated with disease Y.",
            "Results",
            EvidenceStrength.MODERATE,
        )
        with self.assertRaisesRegex(KeyError, "no screening decision"):
            result.ledger.admit(evidence)
        result.ledger.add_decision(
            ScreeningDecision(
                "decision-1",
                "record-1",
                ScreeningStage.ABSTRACT,
                ScreeningOutcome.INCLUDE,
                ("Eligible evidence",),
                NOW,
            )
        )
        result.ledger.admit(evidence)
        admitted_state = admit_evidence(result.state, "evidence-1", result.ledger, policy())
        self.assertEqual(("evidence-1",), admitted_state.memory_evidence_ids)


if __name__ == "__main__":
    unittest.main()
