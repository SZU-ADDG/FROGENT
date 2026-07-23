"""Apply tool findings to ranked design hypotheses."""

from .decision_policy import (
    CalibratedHypothesis, CalibrationFinding, CalibrationOutcome, HypothesisPortfolio,
    HypothesisState,
)


def calibrate_portfolio(portfolio: HypothesisPortfolio,
                        findings: tuple[CalibrationFinding, ...]) -> tuple[CalibratedHypothesis, ...]:
    known = {item.hypothesis_id for item in portfolio.hypotheses}
    if any(item.hypothesis_id not in known for item in findings):
        raise ValueError("calibration finding references an unknown hypothesis")
    values = []
    for hypothesis in portfolio.hypotheses:
        related = tuple(item for item in findings if item.hypothesis_id == hypothesis.hypothesis_id)
        outcomes = {item.outcome for item in related}
        values.append((hypothesis, _calibration_state(outcomes), related))
    precedence = {HypothesisState.STRENGTHENED: 0, HypothesisState.RECOMMENDED: 1,
                  HypothesisState.DOWNGRADED: 2, HypothesisState.REJECTED: 3}
    values.sort(key=lambda item: (precedence[item[1]], item[0].rank))
    return tuple(CalibratedHypothesis(item[0], item[1], item[2], rank)
                 for rank, item in enumerate(values, 1))


def _calibration_state(outcomes: set[CalibrationOutcome]) -> HypothesisState:
    if CalibrationOutcome.HARD_BLOCK in outcomes:
        return HypothesisState.REJECTED
    if CalibrationOutcome.CONTRADICTION in outcomes:
        return HypothesisState.DOWNGRADED
    if CalibrationOutcome.SUPPORT in outcomes:
        return HypothesisState.STRENGTHENED
    return HypothesisState.RECOMMENDED


def render_portfolio(portfolio: HypothesisPortfolio,
                     calibrated: tuple[CalibratedHypothesis, ...] = ()) -> str:
    values = calibrated or calibrate_portfolio(portfolio, ())
    lines = ["Recommended design hypotheses",
             f"Decision regime: {portfolio.context.regime.value}"]
    if portfolio.context.constraints:
        lines.append("User constraints: " + "; ".join(
            f"{item.text} ({'immutable' if item.immutable else 'preference'})"
            for item in portfolio.context.constraints))
    if portfolio.context.optimization_handoff:
        handoff = portfolio.context.optimization_handoff
        lines.extend((f"Quantitative handoff: {handoff.optimizer}",
                      f"   Objective: {handoff.objective}",
                      f"   Search space: {handoff.search_space}",
                      f"   Stop rule: {handoff.stopping_rule}"))
    for item in values:
        hypothesis = item.hypothesis
        rank_change = (f", initial rank {hypothesis.rank}"
                       if item.adjusted_rank != hypothesis.rank else "")
        lines.extend((f"{item.adjusted_rank}. [{item.state.value}{rank_change}] "
                      f"{hypothesis.recommendation}",
                      f"   Rationale: {hypothesis.rationale}",
                      f"   Expected benefit: {'; '.join(hypothesis.expected_benefits)}",
                      f"   Tradeoff: {'; '.join(hypothesis.tradeoffs)}",
                      f"   Confidence: {hypothesis.confidence}",
                      f"   Failure mode: {'; '.join(hypothesis.failure_modes)}",
                      f"   Knowledge basis: {', '.join(hypothesis.knowledge_bases)}",
                      "   Calibration plan: " + "; ".join(
                          f"{request.capability_id}: {request.purpose} "
                          f"[decision: {request.decision_rule}]"
                          for request in hypothesis.calibration_requests)))
        if item.findings:
            lines.append("   Tool calibration: " + "; ".join(
                f"{finding.outcome.value} via {finding.source}: {finding.reason}"
                for finding in item.findings))
        lines.append(f"   Decisive experiment: {hypothesis.decisive_experiment}")
    return "\n".join(lines)
