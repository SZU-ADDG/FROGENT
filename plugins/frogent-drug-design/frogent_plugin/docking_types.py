"""Typed identities and evidence for target-pocket docking workflows."""

import math
from dataclasses import dataclass

from .contracts import ArtifactRef
from .docking_preparation import PreparationProvenance
from .molecular_binding import MolecularInputBinding
from .pocket_geometry import PocketGeometry
@dataclass(frozen=True, slots=True)
class TargetRequest:
    kind: str
    value: str
    chain: str = ""

    def __post_init__(self) -> None:
        if self.kind not in {"pdb", "uniprot", "name_candidate"} or not self.value.strip():
            raise ValueError("target request is invalid")


@dataclass(frozen=True, slots=True)
class VerifiedTargetIdentity:
    kind: str
    identifier: str
    chains: tuple[str, ...]
    structure_artifact: ArtifactRef
    provider: str
    provider_version: str
    requested_value: str
    metadata_url: str = ""
    coordinate_url: str = ""

    def __post_init__(self) -> None:
        if self.kind not in {"pdb", "uniprot"} or not self.identifier.strip():
            raise ValueError("verified target identity is invalid")
        _texts(self.chains, "target chains")
        _texts((self.provider, self.provider_version, self.requested_value), "target provenance")
        if bool(self.metadata_url) != bool(self.coordinate_url):
            raise ValueError("target remote provenance must be complete")
        if self.metadata_url: _texts((self.metadata_url, self.coordinate_url),
                                    "target remote provenance")


@dataclass(frozen=True, slots=True)
class PocketRequest:
    pocket_id: str
    chain: str
    numbering_scheme: str
    source_kind: str
    residues: tuple[str, ...] = ()
    artifact: ArtifactRef | None = None
    reference_ligand: str = ""

    def __post_init__(self) -> None:
        _texts((self.pocket_id, self.chain, self.numbering_scheme), "pocket request")
        if self.source_kind not in {"residues", "artifact", "reference_ligand"}:
            raise ValueError("pocket source kind is invalid")
        if self.source_kind == "residues" and (not self.residues or self.artifact
                                                or self.reference_ligand):
            raise ValueError("residue pocket requires only explicit residues")
        if self.source_kind == "artifact" and (self.artifact is None or self.residues
                                                or self.reference_ligand):
            raise ValueError("artifact pocket requires only an explicit artifact")
        if self.source_kind == "reference_ligand" and (not self.reference_ligand
                or self.residues or self.artifact):
            raise ValueError("reference-ligand pocket requires one explicit ligand identity")
        if self.reference_ligand:
            _texts((self.reference_ligand,), "reference ligand")
        _unique(self.residues, "pocket residues")


@dataclass(frozen=True, slots=True)
class PocketBinding:
    pocket_id: str
    target_identifier: str
    chain: str
    numbering_scheme: str
    source_kind: str
    residues: tuple[str, ...]
    artifact: ArtifactRef
    provider: str
    provider_version: str
    target_artifact_id: str = ""
    reference_ligand: str = ""
    box: PocketGeometry | None = None

    def __post_init__(self) -> None:
        _texts((self.pocket_id, self.target_identifier, self.chain, self.numbering_scheme,
                self.provider, self.provider_version), "pocket binding")
        if self.source_kind not in {"residues", "artifact", "reference_ligand"}:
            raise ValueError("pocket binding source kind is invalid")
        _unique(self.residues, "pocket binding residues")
        if self.source_kind == "reference_ligand" and not self.reference_ligand:
            raise ValueError("reference-ligand pocket binding is missing its identity")
        if self.reference_ligand:
            _texts((self.reference_ligand,), "reference ligand binding")


@dataclass(frozen=True, slots=True)
class DockingConfig:
    pose_count: int = 3
    score_name: str = "provider_score"
    score_direction: str = "lower_is_better"
    capability_id: str = "docking.generate-conformation"
    exhaustiveness: int = 8
    cpu: int = 1
    seed: int | None = None
    energy_range: float = 3.0

    def __post_init__(self) -> None:
        if isinstance(self.pose_count, bool) or not 1 <= self.pose_count <= 20:
            raise ValueError("docking pose count must be between 1 and 20")
        if self.score_direction not in {"lower_is_better", "higher_is_better"}:
            raise ValueError("docking score direction is invalid")
        if self.capability_id not in {"docking.generate-conformation", "docking.score"}:
            raise ValueError("docking capability is invalid")
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
               for value in (self.exhaustiveness, self.cpu)):
            raise ValueError("docking exhaustiveness and cpu must be positive integers")
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int)):
            raise ValueError("docking seed must be an integer or None")
        if isinstance(self.energy_range, bool) or not isinstance(self.energy_range, (int, float)) \
                or not math.isfinite(self.energy_range) or self.energy_range <= 0:
            raise ValueError("docking energy range must be positive and finite")
        _texts((self.score_name,), "docking score name")


@dataclass(frozen=True, slots=True)
class DockingInput:
    molecule: MolecularInputBinding
    target: VerifiedTargetIdentity
    pocket: PocketBinding
    config: DockingConfig
    provider: str = ""
    provider_version: str = ""


@dataclass(frozen=True, slots=True)
class DockingPose:
    pose_id: str
    rank: int
    score: float
    artifact: ArtifactRef

    def __post_init__(self) -> None:
        if not self.pose_id.strip() or isinstance(self.rank, bool) or self.rank <= 0:
            raise ValueError("docking pose identity is invalid")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)) \
                or not math.isfinite(self.score):
            raise ValueError("docking pose score must be finite")


@dataclass(frozen=True, slots=True)
class DockingBatch:
    molecule_smiles: str
    molecule_inchikey: str
    target_identifier: str
    pocket_id: str
    provider: str
    provider_version: str
    score_name: str
    score_direction: str
    poses: tuple[DockingPose, ...]
    input_artifacts: tuple[ArtifactRef, ...] = ()
    command_argv: tuple[str, ...] = ()
    preparation_provenance: tuple[PreparationProvenance, ...] = ()

    def __post_init__(self) -> None:
        _texts((self.molecule_smiles, self.molecule_inchikey, self.target_identifier,
                self.pocket_id, self.provider, self.provider_version, self.score_name),
               "docking batch")
        if self.score_direction not in {"lower_is_better", "higher_is_better"}:
            raise ValueError("docking batch score direction is invalid")


@dataclass(frozen=True, slots=True)
class DockingExecution:
    status: str
    docking_input: DockingInput | None
    poses: tuple[DockingPose, ...] = ()
    provider: str = ""
    provider_version: str = ""
    warnings: tuple[str, ...] = ()
    coverage_gaps: tuple[str, ...] = ()
    input_artifacts: tuple[ArtifactRef, ...] = ()
    command_argv: tuple[str, ...] = ()
    preparation_provenance: tuple[PreparationProvenance, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"completed", "blocked", "failed"}:
            raise ValueError("docking execution status is invalid")


@dataclass(frozen=True, slots=True)
class InteractionEvidence:
    interaction_type: str
    protein_chain: str
    protein_residue: str
    ligand_feature: str
    distance: float | None = None
    angle: float | None = None

    def __post_init__(self) -> None:
        _texts((self.interaction_type, self.protein_chain, self.protein_residue,
                self.ligand_feature), "interaction evidence")
        for value in (self.distance, self.angle):
            if value is not None and (isinstance(value, bool) or not math.isfinite(value)):
                raise ValueError("interaction geometry must be finite")


@dataclass(frozen=True, slots=True)
class InteractionBatch:
    pose_id: str
    pose_artifact_id: str
    molecule_inchikey: str
    target_identifier: str
    provider: str
    provider_version: str
    interactions: tuple[InteractionEvidence, ...]
    complex_artifact_id: str = ""
    command_argv: tuple[str, ...] = ()
    ligand_residue_identity: str = ""


@dataclass(frozen=True, slots=True)
class InteractionExecution:
    status: str
    pose_id: str = ""
    interactions: tuple[InteractionEvidence, ...] = ()
    provider: str = ""
    provider_version: str = ""
    warnings: tuple[str, ...] = ()
    coverage_gaps: tuple[str, ...] = ()
    complex_artifact_id: str = ""
    command_argv: tuple[str, ...] = ()
    ligand_residue_identity: str = ""

    def __post_init__(self) -> None:
        if self.status not in {"completed", "blocked", "failed"}:
            raise ValueError("interaction execution status is invalid")


@dataclass(frozen=True, slots=True)
class DockingWorkflowResult:
    target: VerifiedTargetIdentity | None
    pocket: PocketBinding | None
    docking: DockingExecution
    interaction: InteractionExecution | None
    coverage_gaps: tuple[str, ...]


def _texts(values, label):
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{label} must contain non-empty text")


def _unique(values, label):
    _texts(values, label)
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")
