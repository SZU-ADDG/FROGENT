"""Strict native-schema planner for evidence-bound docking requests."""

import re
from dataclasses import dataclass
from typing import Mapping, Protocol

from agent.llm.codex_schemas import docking_planner_schema
from agent.core.contracts import ArtifactRef
from agent.docking.docking_types import PocketRequest, TargetRequest


class StructuredClient(Protocol):
    def generate(self, role: str, contract: str, payload: Mapping[str, object], *, schema): ...


@dataclass(frozen=True, slots=True)
class DockingChatPlan:
    operation: str
    molecule_kind: str
    molecule_value: str
    molecule_scope: str | None
    selected_structure_smiles: str
    target: TargetRequest
    pocket: PocketRequest | None
    selected_pose_id: str
    selected_pose_rank: int | None
    pose_selection_text: str
    selected_microstate_id: str = ""
    selected_microstate_smiles: str = ""
    microstate_selection_text: str = ""
    receptor_ph: float | None = None
    receptor_state_text: str = ""


class CodexDockingPlanner:
    def __init__(self, client: StructuredClient) -> None:
        self.client = client

    def plan(self, message: str) -> DockingChatPlan:
        if not isinstance(message, str) or not message.strip():
            raise ValueError("docking message must be non-empty")
        value = self.client.generate("target-pocket docking planner", _CONTRACT,
            {"message": message}, schema=docking_planner_schema())
        return _plan(value, message)


def _plan(value, message):
    schema_fields = set(docking_planner_schema()["properties"])
    if not isinstance(value, Mapping) or set(value) != schema_fields:
        raise ValueError("docking planner output fields are invalid")
    operation = _choice(value, "operation", {"dock", "dock_and_interactions"})
    molecule_kind = _choice(value, "molecule_kind", {"name", "smiles"})
    molecule_value = _span(value, "molecule_value", message)
    scope_value = _choice(value, "molecule_scope", {"unspecified", "full", "parent_candidate"})
    selected = _text(value, "selected_structure_smiles", empty=True)
    selection = _text(value, "molecule_selection_text", empty=True)
    scope = None if scope_value == "unspecified" else scope_value
    _molecule_selection(scope, selected, selection, molecule_value, message)
    target_value = _span(value, "target_value", message)
    target_text = _span(value, "target_text", message)
    if target_value not in target_text:
        raise ValueError("target evidence must contain the exact target identity")
    target = TargetRequest(_choice(value, "target_kind", {"pdb", "uniprot", "name_candidate"}),
                           target_value, _text(value, "target_chain", empty=True))
    if target.chain and target.chain not in target_text:
        raise ValueError("target chain must be present in exact target evidence")
    _target_format(target)
    pocket = _pocket(value, message, target)
    pose, rank, pose_text = _pose_selection(value, message, operation)
    state = _state_selection(value, message)
    return DockingChatPlan(operation, molecule_kind, molecule_value, scope, selected,
                           target, pocket, pose, rank, pose_text, *state)


def _state_selection(value, message):
    state_id = _text(value, "selected_microstate_id", empty=True)
    smiles = _text(value, "selected_microstate_smiles", empty=True)
    ligand_text = _text(value, "microstate_selection_text", empty=True)
    if state_id and smiles:
        raise ValueError("select exactly one ligand microstate ID or SMILES")
    if state_id or smiles:
        selected = state_id or smiles
        if not ligand_text or ligand_text not in message or selected not in ligand_text:
            raise ValueError("ligand microstate requires exact current-message evidence")
    elif ligand_text:
        raise ValueError("unused ligand microstate evidence must be empty")
    ph = value.get("receptor_ph")
    receptor_text = _text(value, "receptor_state_text", empty=True)
    if isinstance(ph, bool) or not isinstance(ph, (int, float)) or not -1 <= ph <= 14:
        raise ValueError("receptor pH selection is invalid")
    if ph == -1:
        if receptor_text:
            raise ValueError("unused receptor state evidence must be empty")
        return state_id, smiles, ligand_text, None, ""
    if not receptor_text or receptor_text not in message or not _ph_evidence(receptor_text, ph):
        raise ValueError("receptor pH requires exact current-message evidence")
    return state_id, smiles, ligand_text, float(ph), receptor_text


def _ph_evidence(text, expected):
    number = r"(?:\d+(?:\.\d+)?)"
    patterns = (rf"(?:pH|酸碱度|酸度)\s*[:=为]?\s*({number})",
                rf"({number})\s*(?:pH|酸碱度|酸度)")
    values = [float(item) for pattern in patterns
              for item in re.findall(pattern, text, re.IGNORECASE)]
    return any(item == float(expected) for item in values)


def _pose_selection(value, message, operation):
    pose = _text(value, "selected_pose_id", empty=True)
    rank = value.get("selected_pose_rank")
    evidence = _text(value, "pose_selection_text", empty=True)
    if isinstance(rank, bool) or not isinstance(rank, int) or rank < 0:
        raise ValueError("selected pose rank must be a non-negative integer")
    if operation == "dock":
        if pose or rank or evidence:
            raise ValueError("pose selection is only valid for interaction analysis")
        return "", None, ""
    if bool(pose) == bool(rank):
        raise ValueError("interaction analysis requires exactly one pose ID or pose rank")
    if not evidence or evidence not in message:
        raise ValueError("pose selection requires an exact current-message evidence span")
    if pose:
        if pose not in evidence:
            raise ValueError("selected pose ID must occur in exact pose evidence")
        return pose, None, evidence
    pattern = rf"(?:pose\s+rank|rank|姿势排名|构象排名)\s*[:#-]?\s*{rank}(?!\d)"
    if not re.search(pattern, evidence, re.IGNORECASE):
        raise ValueError("selected pose rank must occur in exact pose evidence")
    return "", rank, evidence


def _pocket(value, message, target):
    kind = _choice(value, "pocket_kind", {"none", "residues", "reference_ligand", "artifact"})
    fields = ("pocket_id", "pocket_chain", "numbering_scheme", "pocket_artifact_id",
              "pocket_artifact_name", "pocket_artifact_media_type", "pocket_artifact_uri",
              "pocket_text", "reference_ligand")
    texts = {key: _text(value, key, empty=True) for key in fields}
    residues = value.get("residue_ids")
    if not isinstance(residues, list) or any(not isinstance(item, str) or not item.strip()
                                             for item in residues):
        raise ValueError("pocket residues must be a text list")
    if kind == "none":
        if any(texts.values()) or residues:
            raise ValueError("unused pocket fields must be empty")
        return None
    evidence = texts["pocket_text"]
    if not evidence or evidence not in message or texts["pocket_id"] not in evidence:
        raise ValueError("pocket identity requires exact user-text evidence")
    if texts["pocket_chain"] != target.chain or not texts["numbering_scheme"]:
        raise ValueError("pocket chain/numbering must bind the target chain")
    artifact = None
    if kind == "artifact":
        required = tuple(texts[key] for key in ("pocket_artifact_id", "pocket_artifact_name",
                         "pocket_artifact_media_type", "pocket_artifact_uri"))
        if any(not item for item in required) or any(item not in evidence for item in required):
            raise ValueError("pocket artifact fields require exact evidence")
        artifact = ArtifactRef(*required)
    elif any(texts[key] for key in ("pocket_artifact_id", "pocket_artifact_name",
                                    "pocket_artifact_media_type", "pocket_artifact_uri")):
        raise ValueError("residue pocket cannot contain artifact fields")
    if kind == "residues" and (not residues or any(item not in evidence for item in residues)):
        raise ValueError("pocket residues must be exact user-text spans")
    if kind == "reference_ligand" and (residues or not texts["reference_ligand"]
            or texts["reference_ligand"] not in evidence):
        raise ValueError("reference ligand must be an exact user-text span")
    return PocketRequest(texts["pocket_id"], texts["pocket_chain"],
        texts["numbering_scheme"], kind, tuple(residues), artifact,
        texts["reference_ligand"])


def _target_format(target):
    if target.kind == "pdb" and not re.fullmatch(r"[0-9][A-Za-z0-9]{3}", target.value):
        raise ValueError("PDB accession is malformed")
    if target.kind == "uniprot" and not re.fullmatch(r"[A-Z0-9]{6,10}", target.value):
        raise ValueError("UniProt accession is malformed")


def _molecule_selection(scope, selected, evidence, molecule, message):
    if scope is None and (selected or evidence):
        raise ValueError("molecular selection requires an explicit scope")
    if scope is None:
        return
    if not evidence or evidence not in message or molecule not in evidence:
        raise ValueError("molecular scope requires exact user-text evidence")
    if selected and (selected not in message or selected not in evidence):
        raise ValueError("selected molecular structure must be an exact user-text span")


def _choice(value, key, allowed):
    item = value.get(key)
    if not isinstance(item, str) or item not in allowed:
        raise ValueError(f"docking planner field is invalid: {key}")
    return item


def _text(value, key, empty=False):
    item = value.get(key)
    if not isinstance(item, str) or not empty and not item.strip():
        raise ValueError(f"docking planner field is invalid: {key}")
    return item


def _span(value, key, message):
    item = _text(value, key)
    if item not in message:
        raise ValueError(f"{key} must be an exact user-text span")
    return item


_CONTRACT = (
    "Extract only explicit target-pocket docking requests. Copy molecule, target, pocket, chain, "
    "residues/artifact and selected pose IDs as exact case-sensitive spans from the message. "
    "Use PDB or UniProt only for explicit accessions; protein names are unverified name_candidate. "
    "A reference ligand must include exact component, chain, and auth residue identity such as "
    "STI:A:999. Never invent a pocket, chain, residue, ligand, artifact, molecular scope, structure, "
    "or pose. Use none for a missing pocket. For interaction analysis copy exactly one current-"
    "message pose ID or explicit pose-rank policy and its complete evidence span. Keep both pose "
    "fields empty for docking-only requests; never infer a best-scoring pose."
    " Copy an explicit ligand microstate ID or exact microstate SMILES and receptor pH only from "
    "their current-message evidence spans. Use empty microstate fields and receptor_ph=-1 when "
    "the user has not selected them; never infer a biological protonation or tautomer state."
)
