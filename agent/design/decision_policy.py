"""Typed policy for knowledge-led design and tool-calibrated decisions."""

from dataclasses import dataclass
from enum import StrEnum


class OptimizationRegime(StrEnum):
    QUALITATIVE = "qualitative"
    HYBRID = "hybrid"
    QUANTITATIVE = "quantitative"


class CalibrationOutcome(StrEnum):
    SUPPORT = "support"
    CONTRADICTION = "contradiction"
    HARD_BLOCK = "hard_block"
    UNAVAILABLE = "unavailable"


class HypothesisState(StrEnum):
    STRENGTHENED = "strengthened"
    RECOMMENDED = "recommended"
    DOWNGRADED = "downgraded"
    REJECTED = "rejected"


KNOWLEDGE_BASES = frozenset({
    "world_knowledge",
    "medicinal_chemistry_judgment",
    "mechanistic_reasoning",
    "literature_precedent",
    "computational_signal",
    "experimental_evidence",
})
CALIBRATION_CAPABILITIES = frozenset({
    "molecular.identity",
    "molecule.describe",
    "molecule.similarity",
    "literature.research",
    "admet.predict",
    "admet.compare",
    "docking.score",
    "sar.analyze",
    "retrosynthesis.flash",
    "retrosynthesis.explorer",
    "peptide.docking-score",
    "experimental.assay",
})


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")


def _texts(values: tuple[str, ...], name: str) -> None:
    if not values or len(values) != len(set(values)):
        raise ValueError(f"{name} must contain unique values")
    for value in values:
        _text(value, name)


@dataclass(frozen=True, slots=True)
class DecisionConstraint:
    text: str
    source_turn_id: str
    immutable: bool

    def __post_init__(self) -> None:
        _text(self.text, "decision constraint")
        _text(self.source_turn_id, "constraint source turn id")
        if type(self.immutable) is not bool:
            raise ValueError("constraint immutable flag must be boolean")


@dataclass(frozen=True, slots=True)
class OptimizationHandoff:
    objective: str
    constraints: tuple[str, ...]
    search_space: str
    discriminator: str
    optimizer: str
    stopping_rule: str
    residual_qualitative_choices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, name in ((self.objective, "optimization objective"),
                            (self.search_space, "optimization search space"),
                            (self.discriminator, "optimization discriminator"),
                            (self.optimizer, "optimizer"),
                            (self.stopping_rule, "optimization stopping rule")):
            _text(value, name)
        _texts(self.constraints, "optimization constraints")
        if self.residual_qualitative_choices:
            _texts(self.residual_qualitative_choices, "residual qualitative choices")


@dataclass(frozen=True, slots=True)
class DecisionContext:
    objective: str
    reliable_discriminator: bool
    unresolved_qualitative_choices: bool
    discriminator: str = ""
    constraints: tuple[DecisionConstraint, ...] = ()
    optimization_handoff: OptimizationHandoff | None = None

    def __post_init__(self) -> None:
        _text(self.objective, "decision objective")
        if type(self.reliable_discriminator) is not bool or \
                type(self.unresolved_qualitative_choices) is not bool:
            raise ValueError("decision flags must be boolean")
        if self.reliable_discriminator:
            _text(self.discriminator, "reliable discriminator")
        elif self.discriminator:
            raise ValueError("unverified discriminator cannot be marked as reliable")
        identities = tuple((item.source_turn_id, item.text) for item in self.constraints)
        if len(identities) != len(set(identities)):
            raise ValueError("decision constraints must be unique")
        quantitative = self.reliable_discriminator and not self.unresolved_qualitative_choices
        if quantitative != (self.optimization_handoff is not None):
            raise ValueError("quantitative regime requires an optimization handoff")

    @property
    def regime(self) -> OptimizationRegime:
        if not self.reliable_discriminator:
            return OptimizationRegime.QUALITATIVE
        if self.unresolved_qualitative_choices:
            return OptimizationRegime.HYBRID
        return OptimizationRegime.QUANTITATIVE


@dataclass(frozen=True, slots=True)
class CalibrationRequest:
    request_id: str
    capability_id: str
    purpose: str
    decision_rule: str

    def __post_init__(self) -> None:
        for value, name in ((self.request_id, "calibration request id"),
                            (self.purpose, "calibration purpose"),
                            (self.decision_rule, "calibration decision rule")):
            _text(value, name)
        if self.capability_id not in CALIBRATION_CAPABILITIES:
            raise ValueError("calibration capability is invalid")


@dataclass(frozen=True, slots=True)
class DesignHypothesis:
    hypothesis_id: str
    rank: int
    recommendation: str
    rationale: str
    expected_benefits: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    failure_modes: tuple[str, ...]
    knowledge_bases: tuple[str, ...]
    calibration_requests: tuple[CalibrationRequest, ...]
    decisive_experiment: str
    confidence: str

    def __post_init__(self) -> None:
        _text(self.hypothesis_id, "hypothesis id")
        if type(self.rank) is not int or self.rank <= 0:
            raise ValueError("hypothesis rank must be a positive integer")
        for value, name in ((self.recommendation, "recommendation"),
                            (self.rationale, "rationale"),
                            (self.decisive_experiment, "decisive experiment")):
            _text(value, name)
        for values, name in ((self.expected_benefits, "expected benefits"),
                             (self.tradeoffs, "tradeoffs"),
                             (self.failure_modes, "failure modes"),
                             (self.knowledge_bases, "knowledge bases")):
            _texts(values, name)
        requests = tuple(item.request_id for item in self.calibration_requests)
        if not requests or len(requests) != len(set(requests)):
            raise ValueError("calibration requests must have unique ids")
        if not set(self.knowledge_bases).issubset(KNOWLEDGE_BASES):
            raise ValueError("hypothesis knowledge basis is invalid")
        if self.confidence not in {"high", "medium", "low"}:
            raise ValueError("hypothesis confidence is invalid")


@dataclass(frozen=True, slots=True)
class HypothesisPortfolio:
    context: DecisionContext
    hypotheses: tuple[DesignHypothesis, ...]

    def __post_init__(self) -> None:
        if not self.hypotheses:
            raise ValueError("decision portfolio requires hypotheses")
        ids = tuple(item.hypothesis_id for item in self.hypotheses)
        ranks = tuple(item.rank for item in self.hypotheses)
        if len(ids) != len(set(ids)) or ranks != tuple(range(1, len(ranks) + 1)):
            raise ValueError("hypotheses require unique ids and contiguous ranked order")
        if self.context.regime in {OptimizationRegime.QUALITATIVE, OptimizationRegime.HYBRID} \
                and not 3 <= len(self.hypotheses) <= 6:
            raise ValueError("qualitative or hybrid portfolios require three to six hypotheses")


@dataclass(frozen=True, slots=True)
class CalibrationFinding:
    hypothesis_id: str
    outcome: CalibrationOutcome
    reason: str
    source: str

    def __post_init__(self) -> None:
        _text(self.hypothesis_id, "finding hypothesis id")
        _text(self.reason, "finding reason")
        _text(self.source, "finding source")


@dataclass(frozen=True, slots=True)
class CalibratedHypothesis:
    hypothesis: DesignHypothesis
    state: HypothesisState
    findings: tuple[CalibrationFinding, ...]
    adjusted_rank: int
