"""Prerequisite-aware tool routing with exact molecular input bindings."""

from dataclasses import dataclass

from .catalog import build_registry
from .molecular_binding import (
    MolecularInputBinding, MolecularToolInput, full_binding, normalized, selected_binding,
)
from .molecular_identity import (
    MolecularIdentity, MolecularSearchTerm, MoleculeNormalizer, RDKitMoleculeNormalizer,
    molecular_search_terms,
)


@dataclass(frozen=True, slots=True)
class MolecularToolStep:
    capability_id: str
    status: str
    purpose: str
    tool_input: MolecularToolInput

    def __post_init__(self) -> None:
        if not self.capability_id.strip() or not self.purpose.strip():
            raise ValueError("molecular tool step fields must be non-empty")
        if self.status not in {"ready", "blocked", "requires_confirmation"}:
            raise ValueError("molecular tool step status is invalid")
        values = (self.tool_input.candidate, self.tool_input.baseline)
        if self.status == "ready" and any(item is None or not item.selection_confirmed
                                           for item in values if item is not None):
            raise ValueError("ready molecular tool step requires confirmed exact inputs")
        if self.status == "ready" and self.tool_input.role_order[-1] == "baseline" \
                and self.tool_input.baseline is None:
            raise ValueError("ready molecular comparison requires an exact baseline")


@dataclass(frozen=True, slots=True)
class MolecularToolPlan:
    skills: tuple[str, ...]
    steps: tuple[MolecularToolStep, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MolecularInputProvenance:
    original_smiles: str
    full_canonical_isomeric_smiles: str
    full_inchikey: str
    parent_candidate_smiles: str = ""
    removed_fragments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MolecularIntakeResult:
    input_provenance: str
    provenance: MolecularInputProvenance
    identity: MolecularIdentity
    baseline_identity: MolecularIdentity | None
    search_terms: tuple[MolecularSearchTerm, ...]
    baseline_search_terms: tuple[MolecularSearchTerm, ...]
    selected_input: MolecularInputBinding
    selected_baseline_input: MolecularInputBinding | None
    tool_plan: MolecularToolPlan


def prepare_molecular_request(smiles: str, intent: str,
                              normalizer: MoleculeNormalizer | None = None, *,
                              target_id: str = "", pocket_id: str = "", baseline_smiles: str = "",
                              interaction_evidence: bool = False,
                              selected_structure_scope: str | None = None,
                              selected_structure_smiles: str = "",
                              baseline_structure_scope: str | None = None,
                              baseline_structure_smiles: str = "",
                              include_formula: bool = False) -> MolecularIntakeResult:
    _request_fields(smiles, intent, target_id, pocket_id, baseline_smiles,
                    selected_structure_smiles, baseline_structure_smiles)
    if not isinstance(interaction_evidence, bool) or not isinstance(include_formula, bool):
        raise ValueError("molecular request flags must be boolean")
    if (baseline_structure_scope is not None or baseline_structure_smiles) \
            and not baseline_smiles.strip():
        raise ValueError("baseline structure selection requires a baseline molecule")
    adapter = normalizer or RDKitMoleculeNormalizer()
    identity = normalized(adapter, smiles)
    baseline = normalized(adapter, baseline_smiles) if baseline_smiles.strip() else None
    candidate_input = selected_binding(adapter, identity, selected_structure_scope,
                                       selected_structure_smiles)
    baseline_input = selected_binding(adapter, baseline, baseline_structure_scope,
                                      baseline_structure_smiles) if baseline else None
    terms = molecular_search_terms(identity, include_formula=include_formula)
    baseline_terms = molecular_search_terms(baseline, include_formula=include_formula) \
        if baseline else ()
    plan = route_molecular_tools(intent, identity, candidate_input=candidate_input,
        target_id=target_id, pocket_id=pocket_id, baseline=baseline,
        baseline_input=baseline_input, interaction_evidence=interaction_evidence)
    return MolecularIntakeResult(smiles, _provenance(identity), identity, baseline, terms,
                                 baseline_terms, candidate_input, baseline_input, plan)


def route_molecular_tools(intent: str, identity: MolecularIdentity, *, target_id: str = "",
                          pocket_id: str = "", baseline: MolecularIdentity | None = None,
                          interaction_evidence: bool = False,
                          candidate_input: MolecularInputBinding | None = None,
                          baseline_input: MolecularInputBinding | None = None) -> MolecularToolPlan:
    text = intent.casefold()
    primary = candidate_input or full_binding(identity)
    comparison = _molecular_comparison(text, baseline is not None)
    skills, specs, blockers = [], [], []
    if _has(text, "literature", "research", "evidence", "paper", "search"):
        skills.append("research-biomedical-literature")
    if _has(text, "admet", "property", "properties", "toxicity", "safety"):
        specs.append(("admet.compare" if comparison else "admet.predict", "ready",
                      "computational ADMET prediction"))
    if _has(text, "dock", "docking", "pose"):
        status = "ready" if target_id.strip() and pocket_id.strip() else "blocked"
        if status == "blocked":
            blockers.append("docking requires an explicit target and prepared pocket")
        specs.append(("docking.score", status, "computational pocket scoring"))
    if _has(text, "retrosynthesis", "retro", "synthesis", "synthetic route"):
        specs.extend((("retrosynthesis.flash", "ready", "fast route hypothesis"),
                      ("retrosynthesis.explorer", "ready", "conditional deeper route hypothesis")))
    if _has(text, "fragment", "sar", "analogue", "analog", "optimize"):
        status = "ready" if interaction_evidence else "blocked"
        specs.extend((("sar.analyze", status, "interaction-grounded fragment analysis"),
                      ("fragment.reconstruct", status,
                       "interaction-grounded fragment reconstruction")))
        if not interaction_evidence:
            blockers.append("fragment reconstruction requires interaction evidence")
    role_order = ("candidate", "baseline") if comparison else ("candidate",)
    tool_input = MolecularToolInput(primary, baseline_input if comparison else None,
                                    role_order, target_id, pocket_id)
    if comparison and baseline_input is None:
        blockers.append("molecular comparison requires a normalized baseline molecule")
        specs = [(capability, "blocked", purpose) for capability, _, purpose in specs]
    if comparison and baseline_input and primary.inchikey == baseline_input.inchikey:
        blockers.append("molecular comparison requires distinct candidate and baseline identities")
        specs = [(capability, "blocked", purpose) for capability, _, purpose in specs]
    specs = _selection_specs(specs, identity, primary, "input", blockers)
    if comparison and baseline:
        specs = _selection_specs(specs, baseline, baseline_input, "baseline", blockers)
    steps = tuple(MolecularToolStep(capability, status, purpose, tool_input)
                  for capability, status, purpose in specs)
    steps = _apply_stereo(steps, identity, blockers)
    _validate_capabilities(steps)
    return MolecularToolPlan(tuple(dict.fromkeys(skills)), steps, tuple(dict.fromkeys(blockers)),
                             tuple(_warnings(identity, bool(steps))))


def _selection_specs(specs, identity, binding, label, blockers):
    if not specs or binding and binding.selection_confirmed:
        return specs
    kind = "multiple organic fragments" if identity.organic_fragment_count > 1 else "salt or mixture"
    blockers.append(f"{label} {kind} requires an explicit executable structure selection")
    return [(capability, "requires_confirmation" if status == "ready" else status, purpose)
            for capability, status, purpose in specs]


def _apply_stereo(steps, identity, blockers):
    if not identity.unassigned_stereocenters:
        return steps
    affected = {"docking.score", "sar.analyze", "fragment.reconstruct"}
    if any(item.capability_id in affected for item in steps):
        blockers.append("unresolved stereo requires confirmation before 3D-dependent tools")
    return tuple(_status(item, "requires_confirmation") if item.capability_id in affected
                 and item.status == "ready" else item for item in steps)


def _status(item, status):
    return MolecularToolStep(item.capability_id, status, item.purpose, item.tool_input)


def _molecular_comparison(text, has_baseline):
    if has_baseline or _has(text, "versus", "baseline"):
        return True
    if not _has(text, "compare", "comparison"):
        return False
    return _has(text, "admet", "property", "molecule", "compound", "candidate",
                "compare docking", "docking score")


def _provenance(identity):
    parent = identity.parent_candidate
    return MolecularInputProvenance(identity.original_smiles, identity.canonical_isomeric_smiles,
        identity.inchikey, parent.canonical_isomeric_smiles if parent else "",
        parent.removed_fragments if parent else ())


def _warnings(identity, has_steps):
    values = []
    if identity.has_charged_fragments:
        values.append("charged fragments are retained in the full molecular identity")
    if identity.parent_candidate:
        values.append("parent is a derived candidate; removed fragments remain in provenance")
    if identity.unassigned_stereocenters:
        values.append("unassigned stereocenters may change structure-dependent predictions")
    if has_steps:
        values.append("tool outputs are computational predictions, separate from experimental evidence")
    return tuple(dict.fromkeys(values))


def _request_fields(*values):
    if any(not isinstance(value, str) for value in values) or not values[0].strip() \
            or not values[1].strip():
        raise ValueError("molecular request text fields must be strings with input and intent")


def _validate_capabilities(steps) -> None:
    registry = build_registry()
    for step in steps:
        registry.get(step.capability_id)


def _has(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)
