"""Safe local command and prepared-artifact contracts for docking tools."""

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .contracts import ArtifactRef
from .docking_preparation import PreparationProvenance
from .docking_types import DockingInput, DockingPose


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, argv: tuple[str, ...], cwd: Path) -> CommandResult: ...


class SubprocessCommandRunner:
    def __init__(self, timeout: float | None = None) -> None:
        if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("tool timeout must be a positive finite number or None")
        self.timeout = timeout

    def run(self, argv: tuple[str, ...], cwd: Path) -> CommandResult:
        completed = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                   timeout=self.timeout, check=False)
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


@dataclass(frozen=True, slots=True)
class VinaPreparedInput:
    receptor: ArtifactRef
    ligand: ArtifactRef
    output_directory: Path
    run_id: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    molecule_inchikey: str
    target_artifact_id: str
    pocket_artifact_id: str
    preparation_provenance: tuple[PreparationProvenance, ...] = ()

    def __post_init__(self) -> None:
        if (not self.run_id.strip() or not self.output_directory.is_absolute()
                or any(not item.strip() for item in (self.molecule_inchikey,
                       self.target_artifact_id, self.pocket_artifact_id))):
            raise ValueError("prepared docking output identity is invalid")
        if any(isinstance(item, bool) or not math.isfinite(item) for item in (*self.center, *self.size)):
            raise ValueError("docking box values must be finite")
        if any(item <= 0 for item in self.size):
            raise ValueError("docking box size must be positive")


class VinaInputPreparer(Protocol):
    def prepare(self, value: DockingInput) -> VinaPreparedInput: ...


@dataclass(frozen=True, slots=True)
class BoundVinaPreparer:
    prepared: VinaPreparedInput
    molecule_inchikey: str
    target_identifier: str
    pocket_id: str

    def prepare(self, value: DockingInput) -> VinaPreparedInput:
        actual = (value.molecule.inchikey, value.target.identifier, value.pocket.pocket_id)
        if actual != (self.molecule_inchikey, self.target_identifier, self.pocket_id):
            raise ValueError("prepared Vina input request lineage mismatch")
        return self.prepared


@dataclass(frozen=True, slots=True)
class MeekoPreparationConfig:
    ligand_executable: Path
    receptor_executable: Path
    meeko_version: str
    gemmi_version: str

    def __post_init__(self) -> None:
        if not self.ligand_executable.is_absolute() or not self.receptor_executable.is_absolute():
            raise ValueError("Meeko executable paths must be absolute")
        if not self.meeko_version.strip() or not self.gemmi_version.strip():
            raise ValueError("Meeko and Gemmi versions must be explicit")


class MeekoPreparedVinaPreparer:
    """Bind externally prepared Meeko artifacts without re-running or rewriting them."""

    def __init__(self, root: Path, config: MeekoPreparationConfig,
                 prepared: VinaPreparedInput, *, molecule_inchikey: str,
                 target_identifier: str, pocket_id: str) -> None:
        self.root, self.config, self.prepared = root.resolve(strict=True), config, prepared
        contained_executable(self.root, config.ligand_executable)
        contained_executable(self.root, config.receptor_executable)
        self.expected = (molecule_inchikey, target_identifier, pocket_id)
        _validate_meeko_provenance(config, prepared)
        for item in prepared.preparation_provenance:
            for artifact in (*item.source_artifacts, *item.output_artifacts):
                contained_file(self.root, artifact)

    def prepare(self, value: DockingInput) -> VinaPreparedInput:
        actual = (value.molecule.inchikey, value.target.identifier, value.pocket.pocket_id)
        if actual != self.expected:
            raise ValueError("Meeko prepared input request lineage mismatch")
        contained_file(self.root, self.prepared.receptor)
        contained_file(self.root, self.prepared.ligand)
        return self.prepared


@dataclass(frozen=True, slots=True)
class PLIPPreparedInput:
    complex_artifact: ArtifactRef
    output_directory: Path
    run_id: str
    source_pose_artifact_id: str
    target_artifact_id: str
    ligand_residue_identity: str
    molecule_inchikey: str = ""
    pocket_artifact_id: str = ""
    resolved_pose_id: str = ""
    resolved_pose_rank: int = 0
    preparation_provenance: tuple[PreparationProvenance, ...] = ()

    def __post_init__(self) -> None:
        if (not self.run_id.strip() or not self.output_directory.is_absolute()
                or not self.source_pose_artifact_id.strip() or not self.target_artifact_id.strip()):
            raise ValueError("prepared PLIP output identity is invalid")
        if not self.ligand_residue_identity.strip():
            raise ValueError("prepared PLIP ligand residue identity is invalid")
        if self.resolved_pose_rank < 0 or isinstance(self.resolved_pose_rank, bool):
            raise ValueError("prepared PLIP pose rank is invalid")


class PLIPInputPreparer(Protocol):
    def prepare(self, value: DockingInput, pose: DockingPose) -> PLIPPreparedInput: ...


@dataclass(frozen=True, slots=True)
class PLIPConfig:
    add_polar_hydrogens: bool = False
    maxthreads: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.add_polar_hydrogens, bool):
            raise ValueError("PLIP hydrogen policy must be boolean")
        if isinstance(self.maxthreads, bool) or not isinstance(self.maxthreads, int) \
                or self.maxthreads <= 0:
            raise ValueError("PLIP maxthreads must be a positive integer")


@dataclass(frozen=True, slots=True)
class BoundPLIPPreparer:
    prepared: PLIPPreparedInput
    molecule_inchikey: str
    target_identifier: str
    pose_id: str

    def prepare(self, value: DockingInput, pose: DockingPose) -> PLIPPreparedInput:
        actual = (value.molecule.inchikey, value.target.identifier, pose.pose_id)
        if actual != (self.molecule_inchikey, self.target_identifier, self.pose_id):
            raise ValueError("prepared PLIP input request lineage mismatch")
        return self.prepared


def contained_file(root: Path, artifact: ArtifactRef) -> Path:
    if artifact.uri.startswith("file://"):
        raw = artifact.uri[7:]
    else:
        raw = artifact.uri
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("tool artifact must be an absolute non-symlink local file")
    resolved = path.resolve(strict=True)
    resolved.relative_to(root)
    if not resolved.is_file():
        raise ValueError("tool artifact must resolve to a file")
    return resolved


def contained_directory(root: Path, path: Path) -> Path:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("tool output directory must be absolute and non-symlink")
    resolved = path.resolve(strict=True)
    resolved.relative_to(root)
    if not resolved.is_dir():
        raise ValueError("tool output directory must resolve to a directory")
    return resolved


def contained_executable(root: Path, path: Path) -> Path:
    value = contained_file(root, ArtifactRef("executable", path.name,
                           "application/x-executable", str(path)))
    if not value.stat().st_mode & 0o111:
        raise ValueError("tool executable is not executable")
    return value


def _validate_meeko_provenance(config, prepared):
    values = prepared.preparation_provenance
    operations = {item.operation for item in values}
    required = {"lossless_receptor_normalization", "meeko_ligand_preparation",
                "meeko_receptor_preparation"}
    if len(values) != 3 or operations != required:
        raise ValueError("Meeko provenance must contain exactly three preparation operations")
    normalization = next(item for item in values
                         if item.operation == "lossless_receptor_normalization")
    if not normalization.lossless or normalization.dropped_record_count:
        raise ValueError("receptor normalization must preserve every record")
    if normalization.version != config.gemmi_version:
        raise ValueError("Gemmi normalization version mismatch")
    meeko_steps = tuple(item for item in values if item.operation.startswith("meeko_"))
    if any(item.version != config.meeko_version for item in meeko_steps):
        raise ValueError("Meeko preparation version mismatch")
    output_ids = {artifact.id for item in meeko_steps for artifact in item.output_artifacts}
    if prepared.receptor.id not in output_ids or prepared.ligand.id not in output_ids:
        raise ValueError("Meeko provenance does not produce the bound PDBQT artifacts")
    receptor_step = next(item for item in values
                         if item.operation == "meeko_receptor_preparation")
    normalized_ids = {artifact.id for artifact in normalization.output_artifacts}
    receptor_source_ids = {artifact.id for artifact in receptor_step.source_artifacts}
    if normalized_ids.isdisjoint(receptor_source_ids):
        raise ValueError("Meeko receptor preparation must consume the normalized receptor")
