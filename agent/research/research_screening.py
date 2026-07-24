"""Low-cost deterministic screening with Codex delegation for ambiguity."""

from agent.core.evidence import EvidenceStrength
from agent.research.research_types import ReaderReport, ScreeningAssessment


def conservative_assessment(report: ReaderReport) -> ScreeningAssessment:
    if report.integrity_status == "retracted":
        return ScreeningAssessment("exclude", ("retracted record",), EvidenceStrength.UNASSESSED)
    complete = all(claim.statement.strip() and claim.locator.strip() for claim in report.claims)
    if report.integrity_status in {"clear", "corrected"} and complete:
        return ScreeningAssessment("include", ("complete structured claim and locator",),
                                   EvidenceStrength.LOW)
    return ScreeningAssessment("uncertain", ("semantic or integrity review required",),
                               EvidenceStrength.UNASSESSED)


class HybridScreener:
    """Resolve safe mechanical cases locally and delegate ambiguous evidence."""

    def __init__(self, delegate) -> None:
        self.delegate = delegate

    def assess(self, report, record) -> ScreeningAssessment:
        local = conservative_assessment(report)
        return self.delegate.assess(report, record) if local.outcome == "uncertain" else local
