"""Strict native-schema planner for natural-language ADMET chat requests."""

import re
from dataclasses import dataclass
from typing import Mapping, Protocol

from .admet_execution import ADMET_PROPERTY_ALLOWLIST, DEFAULT_ADMET_PROPERTIES
from .codex_schemas import molecular_planner_schema


_FIELDS = frozenset({"operation", "candidate_kind", "candidate_value", "baseline_kind",
    "baseline_value", "candidate_scope", "candidate_structure_smiles", "baseline_scope",
    "baseline_structure_smiles", "candidate_selection_text", "baseline_selection_text"})


class StructuredClient(Protocol):
    def generate(self, role: str, contract: str, payload: Mapping[str, object], *, schema): ...


@dataclass(frozen=True, slots=True)
class MolecularChatEntity:
    kind: str
    value: str
    scope: str | None = None
    selected_structure_smiles: str = ""
    selection_evidence: str = ""

    def __post_init__(self) -> None:
        if self.kind not in {"name", "smiles"} or not self.value.strip():
            raise ValueError("molecular chat entity is invalid")
        if self.scope not in {None, "full", "parent_candidate"}:
            raise ValueError("molecular chat structure scope is invalid")


@dataclass(frozen=True, slots=True)
class MolecularChatPlan:
    operation: str
    candidate: MolecularChatEntity
    baseline: MolecularChatEntity | None
    requested_properties: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.operation not in {"predict", "compare"}:
            raise ValueError("molecular chat operation is invalid")
        if (self.operation == "compare") != (self.baseline is not None):
            raise ValueError("molecular comparison requires exactly one baseline")
        values = self.requested_properties
        if not values or len(values) != len(set(values)) or any(
                item not in ADMET_PROPERTY_ALLOWLIST for item in values):
            raise ValueError("requested ADMET properties are invalid")


class CodexMolecularPlanner:
    def __init__(self, client: StructuredClient) -> None:
        self.client = client

    def plan(self, message: str) -> MolecularChatPlan:
        if not isinstance(message, str) or not message.strip():
            raise ValueError("molecular chat message must be non-empty")
        properties = _requested_properties(message)
        value = self.client.generate("molecular ADMET planner", _CONTRACT,
            {"message": message, "runtime_selected_properties": list(properties)},
            schema=molecular_planner_schema())
        return _plan(value, message, properties)


def _plan(value, message, properties):
    if not isinstance(value, Mapping) or set(value) != _FIELDS:
        raise ValueError("molecular planner output fields are invalid")
    operation = _choice(value, "operation", {"predict", "compare"})
    baseline_kind = _choice(value, "baseline_kind", {"none", "name", "smiles"})
    baseline_value = _text(value, "baseline_value", allow_empty=True)
    candidate_value = _text(value, "candidate_value")
    candidate = _entity(value, "candidate", message,
                        baseline_value if baseline_kind != "none" else "")
    baseline = (None if baseline_kind == "none" else
                _entity(value, "baseline", message, candidate_value))
    unused_baseline = (baseline_value, value.get("baseline_structure_smiles"),
                       value.get("baseline_selection_text"))
    if baseline_kind == "none" and (any(unused_baseline)
                                    or value.get("baseline_scope") != "unspecified"):
        raise ValueError("unused baseline fields must be empty")
    if operation == "predict" and baseline is not None:
        raise ValueError("single prediction cannot include a baseline")
    return MolecularChatPlan(operation, candidate, baseline, properties)


def _entity(value, prefix, message, other_entity):
    kind = _choice(value, prefix + "_kind", {"name", "smiles"})
    entity_value = _text(value, prefix + "_value")
    if entity_value not in message:
        raise ValueError(f"{prefix} must be an exact user-text span")
    scope_value = _choice(value, prefix + "_scope",
                          {"unspecified", "full", "parent_candidate"})
    selected = _text(value, prefix + "_structure_smiles", allow_empty=True)
    evidence = _text(value, prefix + "_selection_text", allow_empty=True)
    scope = None if scope_value == "unspecified" else scope_value
    _selection(scope, selected, evidence, entity_value, other_entity, message, prefix)
    return MolecularChatEntity(kind, entity_value, scope, selected, evidence)


def _selection(scope, selected, evidence, entity, other_entity, message, prefix):
    if scope is None and (selected or evidence):
        raise ValueError(f"{prefix} selection requires an explicit scope")
    if scope is None:
        return
    if not evidence or evidence not in message or entity not in evidence:
        raise ValueError(f"{prefix} scope requires role-specific exact selection text")
    if other_entity and other_entity != entity and other_entity in evidence:
        raise ValueError(f"{prefix} selection text cannot cover both molecular roles")
    if selected and (selected not in message or selected not in evidence):
        raise ValueError(f"{prefix} selected structure must be an exact user-text span")
    lowered = evidence.casefold()
    if scope == "parent_candidate" and (not selected or not any(
            term in lowered for term in ("parent", "fragment", "母体", "片段"))):
        raise ValueError(f"{prefix} parent selection requires an explicit user-supplied fragment")
    if scope == "full" and not any(
            term in lowered for term in ("full", "salt", "mixture", "complete structure",
                                         "完整", "全结构", "全分子", "盐", "混合物")):
        raise ValueError(f"{prefix} full selection must be explicit in selection text")


def _requested_properties(message):
    lowered = message.casefold()
    found = []
    for name in ADMET_PROPERTY_ALLOWLIST:
        match = re.search(rf"(?<![a-z0-9_]){re.escape(name.casefold())}(?![a-z0-9_])",
                          lowered)
        if match:
            found.append((match.start(), name))
    return tuple(name for _, name in sorted(found)) or DEFAULT_ADMET_PROPERTIES


def _choice(value, key, allowed):
    item = value.get(key)
    if not isinstance(item, str) or item not in allowed:
        raise ValueError(f"molecular planner field is invalid: {key}")
    return item


def _text(value, key, allow_empty=False):
    item = value.get(key)
    if not isinstance(item, str) or not allow_empty and not item.strip():
        raise ValueError(f"molecular planner field is invalid: {key}")
    return item


_CONTRACT = (
    "Extract one ADMET predict or compare request. Candidate and baseline values must be exact "
    "case-sensitive spans copied from the current message. Preserve candidate then baseline order. "
    "Use kind name or smiles. For each full or parent_candidate scope, copy a separate exact "
    "selection_text span that contains that role's entity and its scope wording; it cannot include "
    "the other role. Supply any selected fragment SMILES inside the same span. Otherwise use "
    "unspecified and empty selection fields. Property IDs are selected deterministically by the "
    "runtime and are not planner output. Never invent a name, structure, or scope."
)
