"""Project-contained selected-pose complex assembly for PLIP."""

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agent.core.contracts import ArtifactRef
from agent.docking.docking_local import PLIPConfig, PLIPPreparedInput, contained_file
from agent.docking.docking_pose_complex import PoseLigandBuilder, RDKitPoseLigandBuilder
from agent.docking.docking_preparation import PreparationProvenance
from agent.docking.docking_types import DockingInput, DockingPose, PocketRequest
from agent.docking.docking_state_runtime import selected_receptor
from agent.docking.dynamic_receptor import ReceptorComponentPolicy
from agent.docking.rcsb_target import _make_contained_directory
from agent.docking.rcsb_pocket import RCSBPocketProvider


@dataclass(frozen=True, slots=True)
class DynamicPLIPConfig:
    executable: Path
    run_root: Path
    version: str
    ligand_residue_name: str = "LIG"
    ligand_chain: str = "Z"
    ligand_residue_number: int = 1
    plip_config: PLIPConfig = PLIPConfig()
    component_policy: ReceptorComponentPolicy = ReceptorComponentPolicy()

    def __post_init__(self) -> None:
        if not self.executable.is_absolute() or not self.run_root.is_absolute():
            raise ValueError("dynamic PLIP paths must be absolute")
        if not self.version.strip() or not re.fullmatch(r"[A-Z0-9]{1,3}", self.ligand_residue_name):
            raise ValueError("dynamic PLIP tool or ligand identity is invalid")
        if not re.fullmatch(r"[A-Za-z0-9]", self.ligand_chain):
            raise ValueError("dynamic PLIP ligand chain is invalid")
        if isinstance(self.ligand_residue_number, bool) or self.ligand_residue_number <= 0:
            raise ValueError("dynamic PLIP ligand residue number is invalid")


class DynamicPLIPInputPreparer:
    def __init__(self, root: Path, config: DynamicPLIPConfig, *,
                 ligand_builder: PoseLigandBuilder | None = None,
                 run_id_factory: Callable[[], str] | None = None) -> None:
        self.root, self.config = root.resolve(strict=True), config
        config.run_root.relative_to(self.root)
        self.builder = ligand_builder or RDKitPoseLigandBuilder()
        self.run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)

    def prepare(self, value: DockingInput, pose: DockingPose) -> PLIPPreparedInput:
        _validate_lineage(self.root, value, pose, self.config)
        run_id = self.run_id_factory()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{7,63}", run_id):
            raise ValueError("dynamic PLIP run identity is invalid")
        run_dir = _new_directory(self.root, self.config.run_root / run_id)
        receptor = selected_receptor(self.root, value, self.config.component_policy)
        receptor_lines = receptor.pdb.decode("ascii").splitlines()
        serial_start = _ligand_serial_start(receptor_lines)
        pose_path = contained_file(self.root, pose.artifact)
        ligand = self.builder.build(pose_path, value.molecule, pose_rank=pose.rank,
            serial_start=serial_start, residue_name=self.config.ligand_residue_name,
            chain=self.config.ligand_chain, residue_number=self.config.ligand_residue_number)
        if (ligand.canonical_isomeric_smiles, ligand.inchikey) != (
                value.molecule.canonical_isomeric_smiles, value.molecule.inchikey):
            raise ValueError("reconstructed pose ligand identity mismatch")
        complex_path = _write_complex(run_dir / "selected-pose-complex.pdb",
                                      receptor_lines, ligand)
        output = _new_directory(self.root, run_dir / "plip")
        complex_ref = ArtifactRef(f"{run_id}-complex", complex_path.name,
                                  "chemical/x-pdb", str(complex_path))
        provenance = (_provenance(value, pose, complex_ref, ligand, self.builder,
                                  receptor.details, receptor.dropped_records),)
        identity = f"{self.config.ligand_residue_name}:{self.config.ligand_chain}:" \
                   f"{self.config.ligand_residue_number}"
        return PLIPPreparedInput(complex_ref, output, run_id, pose.artifact.id,
            value.target.structure_artifact.id, identity, value.molecule.inchikey,
            value.pocket.artifact.id, pose.pose_id, pose.rank, provenance)


def _validate_lineage(root, value, pose, config):
    if not value.molecule.selection_confirmed or value.molecule.canonical_isomeric_smiles.count("."):
        raise ValueError("dynamic PLIP requires one confirmed connected molecular identity")
    if (value.target.kind != "pdb" or value.target.provider != "rcsb-pdb"
            or config.ligand_chain in value.target.chains):
        raise ValueError("dynamic PLIP requires an RCSB PDB target and noncolliding ligand chain")
    if (not value.pocket.box or value.pocket.target_identifier != value.target.identifier
            or value.pocket.target_artifact_id != value.target.structure_artifact.id):
        raise ValueError("dynamic PLIP target and pocket lineage mismatch")
    if not value.pocket.reference_ligand:
        raise ValueError("dynamic PLIP currently requires an exact reference-ligand pocket")
    contained_file(root, value.target.structure_artifact)
    contained_file(root, value.pocket.artifact)
    contained_file(root, pose.artifact)
    request = PocketRequest(value.pocket.pocket_id, value.pocket.chain,
                            value.pocket.numbering_scheme, "artifact",
                            artifact=value.pocket.artifact)
    verified = RCSBPocketProvider(root).resolve(value.target, request)
    expected = (value.pocket.box, value.pocket.reference_ligand,
                value.pocket.residues, value.pocket.target_artifact_id)
    actual = (verified.box, verified.reference_ligand,
              verified.residues, verified.target_artifact_id)
    if actual != expected:
        raise ValueError("dynamic PLIP pocket artifact lineage mismatch")


def _write_complex(path, receptor_lines, ligand):
    if path.exists() or path.is_symlink():
        raise FileExistsError("dynamic PLIP complex already exists")
    body = [line for line in receptor_lines if line != "END"]
    body.extend(ligand.pdb_records)
    body.extend(ligand.conect_records)
    path.write_text("\n".join((*body, "END")) + "\n", encoding="ascii")
    return path.resolve(strict=True)


def _ligand_serial_start(lines):
    serials = []
    try:
        for line in lines:
            if line.startswith("ATOM"):
                serials.append(int(line[6:11]))
    except ValueError as exc:
        raise ValueError("selected receptor atom serial is malformed") from exc
    if not serials or len(serials) != len(set(serials)) or any(item <= 0 for item in serials):
        raise ValueError("selected receptor atom serials must be positive and unique")
    if max(serials) >= 99999:
        raise ValueError("selected receptor leaves no PDB serial range for the ligand")
    return max(serials) + 1


def _provenance(value, pose, complex_ref, ligand, builder, decisions, dropped):
    details = (f"pose_id={pose.pose_id}", f"pose_rank={pose.rank}",
        f"molecule_inchikey={value.molecule.inchikey}",
        f"pocket_artifact_id={value.pocket.artifact.id}",
        f"ligand_state_id={value.ligand_state.state_id if value.ligand_state else ''}",
        f"receptor_state_id={value.receptor_state.state_id if value.receptor_state else ''}",
        f"receptor_ph={value.receptor_state.ph if value.receptor_state else ''}",
        f"ligand_heavy_atoms={ligand.heavy_atom_count}", *decisions)
    version = getattr(builder, "version", "")
    tool = getattr(builder, "tool", "")
    if not isinstance(version, str) or not version.strip() or not isinstance(tool, str) \
            or not tool.strip():
        raise ValueError("pose reconstruction tool provenance is unavailable")
    state_sources = (() if value.receptor_state is None else
                     (value.receptor_state.artifact, value.receptor_state.charge_artifact))
    return PreparationProvenance(tool, version,
        (value.target.structure_artifact, value.pocket.artifact, pose.artifact, *state_sources),
        (complex_ref,), ("assemble-selected-pose-complex",), "dynamic_plip_complex",
        dropped == 0, dropped_record_count=dropped, details=details)


def _new_directory(root, path):
    _make_contained_directory(root, path.parent)
    if path.exists() or path.is_symlink():
        raise FileExistsError("dynamic PLIP output directory already exists")
    path.mkdir()
    resolved = path.resolve(strict=True)
    resolved.relative_to(root)
    return resolved
