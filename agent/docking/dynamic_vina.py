"""Dynamic exact-identity RDKit and Meeko preparation for AutoDock Vina."""

import json
import math
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agent.core.contracts import ArtifactRef
from agent.docking.docking_conformer import ConformerBuilder, ConformerSettings, RDKitConformerBuilder
from agent.docking.docking_local import (CommandRunner, SubprocessCommandRunner, VinaPreparedInput,
                            contained_executable, contained_file)
from agent.docking.docking_preparation import PreparationProvenance
from agent.docking.docking_types import DockingConfig, DockingInput
from agent.docking.docking_state_runtime import selected_receptor
from agent.docking.dynamic_receptor import ReceptorComponentPolicy
from agent.docking.dynamic_receptor_pdbqt import repair_and_validate_receptor
from agent.docking.rcsb_target import _make_contained_directory


@dataclass(frozen=True, slots=True)
class DynamicVinaConfig:
    vina_executable: Path
    ligand_executable: Path
    receptor_executable: Path
    run_root: Path
    vina_version: str
    meeko_version: str
    docking_config: DockingConfig = DockingConfig(
        pose_count=9, score_name="vina_affinity_kcal_per_mol",
        score_direction="lower_is_better", exhaustiveness=8, cpu=4,
        seed=20260719, energy_range=10.0)
    component_policy: ReceptorComponentPolicy = ReceptorComponentPolicy()

    def __post_init__(self) -> None:
        if not all(path.is_absolute() for path in (
                self.vina_executable, self.ligand_executable,
                self.receptor_executable, self.run_root)):
            raise ValueError("dynamic Vina tool paths must be absolute")
        if not self.vina_version.strip() or not self.meeko_version.strip():
            raise ValueError("Vina and Meeko versions must be explicit")


class DynamicVinaInputPreparer:
    def __init__(self, root: Path, config: DynamicVinaConfig, *,
                 conformer: ConformerBuilder | None = None,
                 runner: CommandRunner | None = None,
                 run_id_factory: Callable[[], str] | None = None) -> None:
        self.root = root.resolve(strict=True)
        self.config, self.conformer = config, conformer or RDKitConformerBuilder()
        if not isinstance(getattr(self.conformer, "settings", None), ConformerSettings):
            raise ValueError("conformer builder settings cannot be attested")
        self.runner = runner or SubprocessCommandRunner()
        self.ligand_tool = contained_executable(self.root, config.ligand_executable)
        self.receptor_tool = contained_executable(self.root, config.receptor_executable)
        config.run_root.relative_to(self.root)
        self.run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)

    def prepare(self, value: DockingInput) -> VinaPreparedInput:
        _validate_input(value)
        run_id = self.run_id_factory()
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{7,63}", run_id):
            raise ValueError("dynamic Vina run identity is invalid")
        run_dir = _new_directory(self.root, self.config.run_root / run_id)
        identity = _identity_artifact(run_dir, run_id, value)
        conformer = self.conformer.build(value.molecule)
        if (conformer.canonical_isomeric_smiles, conformer.inchikey) != (
                value.molecule.canonical_isomeric_smiles, value.molecule.inchikey):
            raise ValueError("generated conformer identity does not match the selected molecule")
        sdf = _write(run_dir / "ligand.sdf", conformer.sdf)
        receptor = selected_receptor(self.root, value, self.config.component_policy)
        receptor_pdb = _write(run_dir / "receptor-selected.pdb", receptor.pdb)
        ligand_pdbqt = run_dir / "ligand.pdbqt"
        receptor_pdbqt = run_dir / "receptor.pdbqt"
        ligand_argv = (str(self.ligand_tool), "-i", str(sdf), "-o", str(ligand_pdbqt))
        receptor_argv = _receptor_argv(self.receptor_tool, receptor_pdb,
                                       receptor.pqr, run_dir, receptor_pdbqt)
        _run(self.runner, ligand_argv, run_dir, "Meeko ligand")
        _validate_ligand(ligand_pdbqt, value, self.conformer)
        _run(self.runner, receptor_argv, run_dir, "Meeko receptor")
        receptor_repairs = repair_and_validate_receptor(
            receptor_pdbqt, receptor_pdb, value.pocket.chain)
        refs = _refs(run_id, identity, sdf, receptor_pdb, ligand_pdbqt, receptor_pdbqt)
        provenance = _provenance(self.config, refs, ligand_argv, receptor_argv,
                                 conformer.heavy_atom_count,
                                 (*receptor.details, *receptor_repairs),
                                 receptor.dropped_records,
                                 getattr(self.conformer, "version", "unknown"),
                                 self.conformer.settings,
                                 value.target.structure_artifact, value.receptor_state)
        box = value.pocket.box
        return VinaPreparedInput(refs[4], refs[3], run_dir, run_id, box.center, box.size,
            value.molecule.inchikey, value.target.structure_artifact.id,
            value.pocket.artifact.id, provenance)


def _validate_input(value):
    if not value.molecule.selection_confirmed:
        raise ValueError("dynamic Vina preparation requires confirmed molecular identity")
    if value.molecule.canonical_isomeric_smiles.count("."):
        raise ValueError("dynamic Vina preparation does not support disconnected molecules")
    if value.target.kind != "pdb" or not value.target.structure_artifact.id:
        raise ValueError("dynamic Vina preparation requires a verified PDB target")
    if not value.pocket.box or not value.pocket.target_artifact_id:
        raise ValueError("dynamic Vina preparation requires verified pocket geometry")
    if value.pocket.target_artifact_id != value.target.structure_artifact.id:
        raise ValueError("dynamic Vina target and pocket artifacts do not match")
    if not value.pocket.reference_ligand:
        raise ValueError("dynamic receptor preparation requires an exact reference ligand pocket")


def _receptor_argv(tool, pdb, pqr, run_dir, output):
    if pqr is not None:
        return (str(tool), "--read_pqr", str(pqr), "--charge_model", "read",
                "-o", str(run_dir / "receptor"), "-p", str(output))
    return (str(tool), "--read_pdb", str(pdb),
            "-o", str(run_dir / "receptor"), "-p", str(output))


def _identity_artifact(run_dir, run_id, value):
    payload = {"schema_version": "dynamic-vina-input-v1", "run_id": run_id,
        "molecule_scope": value.molecule.scope, "smiles": value.molecule.canonical_isomeric_smiles,
        "inchikey": value.molecule.inchikey, "removed_fragments": list(value.molecule.removed_fragments),
        "target": value.target.identifier, "target_artifact_id": value.target.structure_artifact.id,
        "pocket": value.pocket.pocket_id, "pocket_artifact_id": value.pocket.artifact.id,
        "center": list(value.pocket.box.center), "size": list(value.pocket.box.size),
        "ligand_state_id": value.ligand_state.state_id if value.ligand_state else "",
        "receptor_state_id": value.receptor_state.state_id if value.receptor_state else "",
        "receptor_ph": value.receptor_state.ph if value.receptor_state else None}
    return _write(run_dir / "input-identity.json",
                  (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode())


def _run(runner, argv, cwd, label):
    result = runner.run(argv, cwd)
    if result.returncode:
        raise RuntimeError(f"{label} preparation exited {result.returncode}")


def _validate_ligand(path, value, conformer):
    raw = _output(path, "ligand PDBQT")
    text = raw.decode("ascii")
    if text.count("\nROOT\n") != 1 or text.count("TORSDOF") != 1:
        raise ValueError("Meeko ligand output must contain one prepared record")
    match = re.search(r"^REMARK SMILES (\S+)\s*$", text, re.MULTILINE)
    if not match or conformer.identify_smiles(match.group(1)) != (
            value.molecule.canonical_isomeric_smiles, value.molecule.inchikey):
        raise ValueError("Meeko ligand output identity mismatch")
    _finite_pdbqt(text)


def _output(path, label):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} is missing")
    raw = path.read_bytes()
    if not raw or len(raw) > 20 * 1024 * 1024 or b"\x00" in raw:
        raise ValueError(f"{label} is empty, binary, or oversized")
    return raw


def _finite_pdbqt(text):
    atoms = [line for line in text.splitlines() if line.startswith(("ATOM", "HETATM"))]
    if not atoms:
        raise ValueError("prepared PDBQT contains no atoms")
    try:
        coordinates = [float(line[start:end]) for line in atoms
                       for start, end in ((30, 38), (38, 46), (46, 54))]
    except ValueError as exc:
        raise ValueError("prepared PDBQT coordinates are malformed") from exc
    if any(not math.isfinite(value) for value in coordinates):
        raise ValueError("prepared PDBQT coordinates must be finite")


def _provenance(config, refs, ligand_argv, receptor_argv, atoms, decisions, dropped, rdkit,
                settings, target_artifact, receptor_state):
    identity, sdf, receptor_pdb, ligand_pdbqt, receptor_pdbqt = refs
    return (
        PreparationProvenance("rdkit", rdkit, (identity,), (sdf,),
            settings.command_argv,
            "rdkit_ligand_conformer", True, details=(f"heavy_atoms={atoms}",)),
        PreparationProvenance("frogent-receptor-selector", "pdb-auth-v1",
            (target_artifact,),
            (receptor_pdb,), ("select-auth-chain-and-components",),
            "receptor_component_selection", False, dropped_record_count=dropped,
            details=decisions),
        PreparationProvenance("meeko-ligand", config.meeko_version, (sdf,), (ligand_pdbqt,),
            ligand_argv, "meeko_ligand_preparation", True),
        PreparationProvenance("meeko-receptor", config.meeko_version,
            ((receptor_pdb, receptor_state.charge_artifact) if receptor_state else
             (receptor_pdb,)),
            (receptor_pdbqt,), receptor_argv, "meeko_receptor_preparation", True))


def _refs(run_id, identity, sdf, receptor, ligand, receptor_pdbqt):
    return (_ref(f"{run_id}-identity", identity, "application/json"),
            _ref(f"{run_id}-ligand-sdf", sdf, "chemical/x-mdl-sdfile"),
            _ref(f"{run_id}-receptor-selected", receptor, "chemical/x-pdb"),
            _ref(f"{run_id}-ligand-pdbqt", ligand, "chemical/x-pdbqt"),
            _ref(f"{run_id}-receptor-pdbqt", receptor_pdbqt, "chemical/x-pdbqt"))


def _ref(identity, path, media):
    return ArtifactRef(identity, path.name, media, str(path.resolve(strict=True)))


def _write(path, raw):
    if path.is_symlink() or path.exists():
        raise FileExistsError("dynamic preparation artifact already exists")
    with path.open("xb") as handle:
        handle.write(raw)
    return path.resolve(strict=True)


def _new_directory(root, path):
    _make_contained_directory(root, path.parent)
    if path.is_symlink() or path.exists():
        raise FileExistsError("dynamic Vina run directory already exists")
    path.mkdir()
    resolved = path.resolve(strict=True)
    resolved.relative_to(root)
    return resolved
