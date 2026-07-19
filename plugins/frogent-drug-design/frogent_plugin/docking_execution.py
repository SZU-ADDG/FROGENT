"""Fail-closed orchestration for verified docking and pose interactions."""

from typing import Protocol

from .docking_types import (
    DockingBatch, DockingConfig, DockingExecution, DockingInput, DockingWorkflowResult,
    InteractionBatch, InteractionExecution, PocketBinding, PocketRequest, TargetRequest,
    VerifiedTargetIdentity,
)
from .molecular_binding import MolecularInputBinding
from .docking_state_lineage import state_lineage
from .docking_state_types import LigandMicrostate, ReceptorStateBinding
from .docking_state_runtime import prepare_receptor_state


class TargetIdentityProvider(Protocol):
    def resolve(self, request: TargetRequest) -> VerifiedTargetIdentity: ...


class PocketProvider(Protocol):
    def resolve(self, target: VerifiedTargetIdentity, request: PocketRequest) -> PocketBinding: ...


class DockingProvider(Protocol):
    def dock(self, value: DockingInput) -> DockingBatch: ...


class InteractionProvider(Protocol):
    def analyze(self, value: DockingInput, pose) -> InteractionBatch: ...


def run_docking_workflow(molecule: MolecularInputBinding, target_request: TargetRequest,
                         pocket_request: PocketRequest | None, *, target_provider=None,
                         pocket_provider=None, docking_provider=None, interaction_provider=None,
                         config: DockingConfig | None = None, want_interactions: bool = False,
                         selected_pose_id: str = "",
                         selected_pose_rank: int | None = None,
                         ligand_state: LigandMicrostate | None = None,
                         receptor_state: ReceptorStateBinding | None = None,
                         receptor_state_provider=None,
                         receptor_ph: float | None = None) -> DockingWorkflowResult:
    gaps = []
    target = _target(target_request, target_provider, gaps)
    if target is None:
        return _blocked(None, None, gaps)
    pocket = _pocket(target, pocket_request, pocket_provider, gaps)
    if pocket is None:
        return _blocked(target, None, gaps)
    if receptor_state_provider is not None:
        receptor_state = prepare_receptor_state(target, pocket, receptor_state_provider,
                                                receptor_ph, gaps)
        if receptor_state is None:
            return _blocked(target, pocket, gaps)
    elif receptor_ph is not None:
        gaps.append("receptor pH was selected but its preparation provider is unavailable")
        return _blocked(target, pocket, gaps)
    selected_config = config or getattr(docking_provider, "default_config", DockingConfig())
    value = DockingInput(molecule, target, pocket, selected_config,
                         str(getattr(docking_provider, "provider_id", "")),
                         str(getattr(docking_provider, "provider_version", "")),
                         ligand_state, receptor_state)
    docking = _dock(value, docking_provider)
    gaps.extend(docking.coverage_gaps)
    interaction = _interactions(value, docking, interaction_provider, want_interactions,
                                selected_pose_id, selected_pose_rank)
    if interaction:
        gaps.extend(interaction.coverage_gaps)
    return DockingWorkflowResult(target, pocket, docking, interaction,
                                 tuple(dict.fromkeys(gaps)))


def _target(request, provider, gaps):
    if request.kind == "name_candidate":
        gaps.append("target name remains an unverified candidate; supply a PDB or UniProt accession")
        return None
    if provider is None:
        gaps.append("target identity provider is unavailable")
        return None
    try:
        target = provider.resolve(request)
        if not isinstance(target, VerifiedTargetIdentity):
            raise TypeError("target provider returned an invalid identity")
        if target.kind != request.kind or target.identifier.casefold() != request.value.casefold():
            raise ValueError("verified target identity does not match the requested accession")
        if request.chain and request.chain not in target.chains:
            raise ValueError("requested chain is absent from the verified target")
        return target
    except Exception as exc:
        gaps.append(f"target verification failed: {type(exc).__name__}: {exc}")
        return None


def _pocket(target, request, provider, gaps):
    if request is None:
        gaps.append("docking requires an explicit verified pocket")
        return None
    if request.chain not in target.chains:
        gaps.append("pocket chain is absent from the verified target")
        return None
    if provider is None:
        gaps.append("pocket verification provider is unavailable")
        return None
    try:
        pocket = provider.resolve(target, request)
        if not isinstance(pocket, PocketBinding):
            raise TypeError("pocket provider returned an invalid binding")
        expected = (request.pocket_id, target.identifier, request.chain,
                    request.numbering_scheme, request.source_kind)
        actual = (pocket.pocket_id, pocket.target_identifier, pocket.chain,
                  pocket.numbering_scheme, pocket.source_kind)
        lineage_mismatch = request.source_kind != "artifact" and (
            pocket.residues != request.residues
            or pocket.reference_ligand != request.reference_ligand)
        if actual != expected or lineage_mismatch:
            raise ValueError("verified pocket does not match the requested target/pocket lineage")
        if pocket.target_artifact_id and pocket.target_artifact_id != target.structure_artifact.id:
            raise ValueError("verified pocket target artifact identity does not match")
        if request.artifact and pocket.artifact.id != request.artifact.id:
            raise ValueError("verified pocket artifact identity does not match")
        return pocket
    except Exception as exc:
        gaps.append(f"pocket verification failed: {type(exc).__name__}: {exc}")
        return None


def _dock(value, provider):
    warning = ("Docking scores are computational ranking signals; score calibration, "
               "applicability domain, binding affinity, experimental correlation, and "
               "experimental evidence are not established.",)
    if value.ligand_state or value.receptor_state:
        warning += ("Enumerated protomers, tautomers, and PDB2PQR/PROPKA states are "
                    "computational candidates; dominant biological microstate, affinity, "
                    "mechanism, and experimental effect are not established.",)
    lineage = state_lineage(value)
    if not value.molecule.selection_confirmed:
        return DockingExecution("blocked", value, warnings=warning,
            coverage_gaps=("molecular structure selection is not confirmed",),
            state_lineage=lineage)
    if provider is None:
        return DockingExecution("blocked", value, warnings=warning,
            coverage_gaps=("docking provider is unavailable",), state_lineage=lineage)
    if not value.provider.strip() or not value.provider_version.strip():
        return DockingExecution("failed", value, warnings=warning,
            coverage_gaps=("docking provider identity/version is unavailable",),
            state_lineage=lineage)
    try:
        batch = provider.dock(value)
        _validate_batch(value, batch)
        return DockingExecution("completed", value, batch.poses, batch.provider,
                                batch.provider_version, warning,
                                input_artifacts=batch.input_artifacts,
                                command_argv=batch.command_argv,
                                preparation_provenance=batch.preparation_provenance,
                                state_lineage=batch.state_lineage)
    except Exception as exc:
        return DockingExecution("failed", value, warnings=warning,
            coverage_gaps=(f"docking failed: {type(exc).__name__}: {exc}",),
            state_lineage=lineage)


def _validate_batch(value, batch):
    if not isinstance(batch, DockingBatch):
        raise TypeError("docking provider returned an invalid batch")
    expected = (value.molecule.canonical_isomeric_smiles, value.molecule.inchikey,
                value.target.identifier, value.pocket.pocket_id,
                value.config.score_name, value.config.score_direction,
                value.provider, value.provider_version)
    actual = (batch.molecule_smiles, batch.molecule_inchikey, batch.target_identifier,
              batch.pocket_id, batch.score_name, batch.score_direction,
              batch.provider, batch.provider_version)
    if actual != expected:
        raise ValueError("docking output identity or score semantics do not match the input")
    if batch.state_lineage != state_lineage(value):
        raise ValueError("docking output state lineage does not match the input")
    if not batch.poses or len(batch.poses) > value.config.pose_count:
        raise ValueError("docking output pose count is invalid")
    if tuple(pose.rank for pose in batch.poses) != tuple(range(1, len(batch.poses) + 1)):
        raise ValueError("docking poses must preserve provider rank order")
    if len({pose.pose_id for pose in batch.poses}) != len(batch.poses):
        raise ValueError("docking pose IDs must be unique")


def _interactions(value, docking, provider, wanted, pose_id, pose_rank):
    if not wanted:
        return None
    lineage = state_lineage(value)
    if docking.status != "completed":
        return InteractionExecution("blocked", coverage_gaps=(
            "interaction analysis requires completed docking",), state_lineage=lineage)
    if bool(pose_id) == bool(pose_rank):
        return InteractionExecution("blocked", coverage_gaps=(
            "interaction analysis requires exactly one explicit pose ID or pose rank",),
            state_lineage=lineage)
    pose = (next((item for item in docking.poses if item.pose_id == pose_id), None)
            if pose_id else next((item for item in docking.poses
                                  if item.rank == pose_rank), None))
    if pose is None:
        return InteractionExecution("blocked", pose_id, requested_pose_rank=pose_rank,
            coverage_gaps=("selected pose is absent from the docking result",),
            state_lineage=lineage)
    if provider is None:
        return InteractionExecution("blocked", pose.pose_id, pose.rank, pose_rank,
            coverage_gaps=(
            "PLIP interaction provider is unavailable",), state_lineage=lineage)
    provider_id = str(getattr(provider, "provider_id", ""))
    provider_version = str(getattr(provider, "provider_version", ""))
    if not provider_id.strip() or not provider_version.strip():
        return InteractionExecution("failed", pose.pose_id, pose.rank, pose_rank, coverage_gaps=(
            "PLIP provider identity/version is unavailable",), state_lineage=lineage)
    try:
        batch = provider.analyze(value, pose)
        _validate_interactions(value, pose, batch, provider_id, provider_version)
        warning = ("Pose interactions are computational observations for the selected artifact; "
                   "a binding mechanism is not established.",)
        if value.ligand_state or value.receptor_state:
            warning += ("The selected ligand/receptor pH states are computational candidates; "
                        "biological dominance and experimental effect are not established.",)
        return InteractionExecution("completed", pose.pose_id, pose.rank, pose_rank,
                                    batch.interactions, batch.provider, batch.provider_version, warning,
                                    complex_artifact_id=batch.complex_artifact_id,
                                    command_argv=batch.command_argv,
                                    ligand_residue_identity=batch.ligand_residue_identity,
                                    preparation_provenance=batch.preparation_provenance,
                                    state_lineage=batch.state_lineage)
    except Exception as exc:
        return InteractionExecution("failed", pose.pose_id, pose.rank, pose_rank, coverage_gaps=(
            f"PLIP interaction analysis failed: {type(exc).__name__}: {exc}",),
            state_lineage=lineage)


def _validate_interactions(value, pose, batch, provider_id, provider_version):
    if not isinstance(batch, InteractionBatch):
        raise TypeError("interaction provider returned an invalid batch")
    actual = (batch.pose_id, batch.pose_artifact_id, batch.molecule_inchikey,
              batch.target_identifier, batch.provider, batch.provider_version)
    expected = (pose.pose_id, pose.artifact.id, value.molecule.inchikey,
                value.target.identifier, provider_id, provider_version)
    if actual != expected:
        raise ValueError("interaction evidence is not bound to the selected pose")
    if batch.state_lineage != state_lineage(value):
        raise ValueError("interaction output state lineage does not match the selected pose")
    if any(item.protein_chain != value.pocket.chain for item in batch.interactions):
        raise ValueError("interaction chain does not match the verified pocket")


def _blocked(target, pocket, gaps):
    docking = DockingExecution("blocked", None, coverage_gaps=tuple(gaps))
    return DockingWorkflowResult(target, pocket, docking, None, tuple(gaps))
