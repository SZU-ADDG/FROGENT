"""Behavioral checks for harness policy and evidence memory admission."""

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin import (  # noqa: E402
    ArtifactRef,
    CommandKind,
    EvidenceExcerpt,
    EvidenceLedger,
    EvidenceStrength,
    HarnessCommand,
    HarnessPhase,
    HarnessPolicy,
    HarnessState,
    LiteratureRecord,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
    SearchPlan,
    admit_evidence,
    advance,
    reconcile_evidence,
)

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def make_plan() -> SearchPlan:
    return SearchPlan(
        id="plan-1",
        question="Does target X affect disease Y?",
        as_of=date(2026, 7, 15),
        queries=("target X AND disease Y",),
        sources=("pubmed",),
        inclusion_criteria=("Reports target X and disease Y",),
        exclusion_criteria=("No decision-relevant outcome",),
        stop_rules=("Two expansion waves add no decision-relevant evidence",),
    )


def make_record() -> LiteratureRecord:
    return LiteratureRecord(
        id="record-1",
        plan_id="plan-1",
        source="pubmed",
        title="Target X in disease Y",
        retrieved_at=NOW,
        identifiers={"pmid": "123"},
        raw_artifact=ArtifactRef(
            id="artifact-1",
            name="pubmed-123.json",
            media_type="application/json",
            uri="artifact://literature/pubmed-123",
        ),
        published_on=date(2025, 1, 1),
        abstract="A test abstract.",
    )


def make_decision(
    decision_id: str,
    stage: ScreeningStage,
    outcome: ScreeningOutcome,
    decided_at: datetime = NOW,
) -> ScreeningDecision:
    return ScreeningDecision(
        id=decision_id,
        record_id="record-1",
        stage=stage,
        outcome=outcome,
        reasons=(f"{stage.value} review",),
        decided_at=decided_at,
    )


def make_evidence() -> EvidenceExcerpt:
    return EvidenceExcerpt(
        id="evidence-1",
        record_id="record-1",
        claim="Target X is associated with disease Y in the reported cohort.",
        locator="Results, paragraph 2",
        strength=EvidenceStrength.MODERATE,
        limitations=("Single cohort",),
    )


class EvidenceLedgerTests(unittest.TestCase):
    def test_plan_requires_reproducible_search_fields(self) -> None:
        self.assertEqual(date(2026, 7, 15), make_plan().as_of)
        with self.assertRaisesRegex(ValueError, "stop rules"):
            SearchPlan(
                id="plan-2",
                question="Question",
                as_of=date(2026, 7, 15),
                queries=("query",),
                sources=("source",),
                inclusion_criteria=("include",),
                exclusion_criteria=("exclude",),
                stop_rules=(),
            )

    def test_excluded_records_remain_auditable_and_out_of_memory(self) -> None:
        ledger = EvidenceLedger()
        ledger.add_record(make_record())
        ledger.add_decision(
            make_decision("decision-1", ScreeningStage.ABSTRACT, ScreeningOutcome.EXCLUDE)
        )

        with self.assertRaisesRegex(ValueError, "not eligible for memory"):
            ledger.admit(make_evidence())

        self.assertEqual(1, len(ledger.records()))
        self.assertEqual(1, len(ledger.decisions()))
        self.assertEqual((), ledger.admitted())

    def test_later_full_text_exclusion_revokes_memory_eligibility(self) -> None:
        ledger = EvidenceLedger()
        ledger.add_record(make_record())
        ledger.add_decision(
            make_decision("decision-1", ScreeningStage.ABSTRACT, ScreeningOutcome.INCLUDE)
        )
        ledger.admit(make_evidence())

        state = admit_evidence(
            HarnessState("run-1", date(2026, 7, 15)),
            "evidence-1",
            ledger,
            HarnessPolicy(),
        )
        ledger.add_decision(
            make_decision(
                "decision-2",
                ScreeningStage.FULL_TEXT,
                ScreeningOutcome.EXCLUDE,
                NOW + timedelta(minutes=1),
            )
        )

        self.assertFalse(ledger.has_admitted("evidence-1"))
        self.assertEqual((), reconcile_evidence(state, ledger).memory_evidence_ids)


class HarnessPolicyTests(unittest.TestCase):
    def test_typed_commands_drive_valid_transitions_and_counts(self) -> None:
        policy = HarnessPolicy(allowed_capabilities=frozenset({"literature.search"}))
        state = HarnessState("run-1", date(2026, 7, 15))
        state = advance(
            state,
            HarnessCommand(
                CommandKind.ACTIVATE_SKILL,
                HarnessPhase.PLANNING,
                "Plan the literature review",
                "$plan-literature-search",
            ),
            policy,
        )
        state = advance(
            state,
            HarnessCommand(
                CommandKind.CALL_CAPABILITY,
                HarnessPhase.RETRIEVAL,
                "Run the first query wave",
                "literature.search",
            ),
            policy,
        )

        self.assertEqual(HarnessPhase.RETRIEVAL, state.phase)
        self.assertEqual(2, state.step_count)
        self.assertEqual(1, state.tool_call_count)

    def test_policy_rejects_unlisted_capability_and_invalid_transition(self) -> None:
        policy = HarnessPolicy(allowed_capabilities=frozenset({"literature.search"}))
        planning = HarnessState(
            "run-1",
            date(2026, 7, 15),
            phase=HarnessPhase.PLANNING,
        )
        with self.assertRaisesRegex(PermissionError, "not allowed"):
            advance(
                planning,
                HarnessCommand(
                    CommandKind.CALL_CAPABILITY,
                    HarnessPhase.EXECUTION,
                    "Attempt an unapproved tool",
                    "shell.execute",
                ),
                policy,
            )
        with self.assertRaisesRegex(ValueError, "invalid harness transition"):
            advance(
                HarnessState("run-2", date(2026, 7, 15)),
                HarnessCommand(
                    CommandKind.COMPLETE,
                    HarnessPhase.COMPLETE,
                    "Premature completion",
                ),
                policy,
            )


if __name__ == "__main__":
    unittest.main()
