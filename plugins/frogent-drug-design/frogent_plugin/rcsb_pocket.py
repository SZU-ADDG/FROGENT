"""Verified auth-residue or reference-ligand pocket binding for RCSB PDB artifacts."""

import json
import math
import re
from pathlib import Path
from typing import Mapping

from .docking_local import contained_file
from .docking_types import PocketBinding, PocketRequest, VerifiedTargetIdentity
from .pdb_structure import PDBAtom, parse_pdb
from .pocket_geometry import PocketGeometry
from .rcsb_target import _json_object, _lexically_contained, _store


class RCSBPocketProvider:
    provider_id = "rcsb-pdb-pocket"
    provider_version = "pdb-auth-v1"

    def __init__(self, plugin_root: Path, artifact_root: Path | None = None,
                 margin: float = 5.0) -> None:
        self.plugin_root = plugin_root.resolve(strict=True)
        self.artifact_root = artifact_root or (self.plugin_root / ".runtime/app-v4/targets")
        _lexically_contained(self.plugin_root, self.artifact_root)
        if (isinstance(margin, bool) or not isinstance(margin, (int, float))
                or not math.isfinite(margin) or margin <= 0):
            raise ValueError("pocket margin must be positive and finite")
        self.margin = float(margin)

    def resolve(self, target: VerifiedTargetIdentity, request: PocketRequest) -> PocketBinding:
        if target.kind != "pdb" or target.provider != "rcsb-pdb" or not target.coordinate_url:
            raise ValueError("pocket derivation requires an exact RCSB PDB target artifact")
        path = contained_file(self.plugin_root, target.structure_artifact)
        structure = parse_pdb(path.read_bytes(), target.identifier)
        if request.chain not in target.chains or request.chain not in structure.chains:
            raise ValueError("pocket chain does not match the verified target")
        if request.source_kind == "artifact":
            return self._artifact(target, request, structure)
        if request.numbering_scheme not in {"pdb_auth", "pdb_author"}:
            raise ValueError("RCSB pocket requires auth-numbered residues or ligand identity")
        atoms = self._selected_atoms(structure, request)
        _unambiguous(atoms)
        box = _box(atoms, self.margin, request.source_kind)
        artifact = self._manifest(target, request, box)
        return PocketBinding(request.pocket_id, target.identifier, request.chain,
            request.numbering_scheme, request.source_kind, request.residues, artifact,
            self.provider_id, self.provider_version, target.structure_artifact.id,
            request.reference_ligand, box)

    def _selected_atoms(self, structure, request) -> tuple[PDBAtom, ...]:
        if request.source_kind == "residues":
            selected = []
            for residue in request.residues:
                if not re.fullmatch(r"[A-Z0-9]{1,3}-?\d+[A-Z]?", residue):
                    raise ValueError("auth-numbered pocket residue is malformed")
                atoms = structure.residue_atoms(request.chain, residue)
                if not atoms:
                    raise ValueError(f"pocket residue is absent from target chain: {residue}")
                selected.extend(atoms)
            return tuple(selected)
        if request.source_kind != "reference_ligand":
            raise ValueError("unsupported RCSB pocket source")
        match = re.fullmatch(r"([A-Z0-9]{1,3}):([A-Za-z0-9]):(-?\d+[A-Z]?)",
                             request.reference_ligand)
        if not match or match.group(2) != request.chain:
            raise ValueError("reference ligand identity must explicitly match the target chain")
        atoms = structure.ligand_atoms(request.reference_ligand)
        if not atoms:
            candidates = structure.ligand_ids(match.group(1), match.group(2))
            detail = "; exact candidates: " + ", ".join(candidates) if candidates else ""
            raise ValueError("reference ligand is absent from the verified target" + detail)
        return atoms

    def _manifest(self, target, request, box):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", request.pocket_id):
            raise ValueError("pocket ID is unsafe for artifact storage")
        payload = _manifest_payload(target, request, box)
        raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
        path = self.artifact_root / target.identifier / "pockets" / f"{request.pocket_id}.json"
        stored = _store(self.plugin_root, path, raw)
        return _artifact_ref(request.pocket_id, stored)

    def _artifact(self, target, request, structure):
        path = contained_file(self.plugin_root, request.artifact)
        value = _json_object(path.read_bytes(), "pocket manifest")
        expected = {"schema_version", "pocket_id", "target_identifier", "target_artifact_id",
                    "chain", "numbering_scheme", "source_kind", "residues",
                    "reference_ligand", "center", "size", "units", "method", "margin"}
        if set(value) != expected:
            raise ValueError("pocket manifest fields are invalid")
        if value["schema_version"] != "pocket-v1":
            raise ValueError("pocket manifest schema version is invalid")
        identity = (value["pocket_id"], value["target_identifier"],
                    value["target_artifact_id"], value["chain"])
        if identity != (request.pocket_id, target.identifier,
                        target.structure_artifact.id, request.chain):
            raise ValueError("pocket artifact identity mismatch")
        lineage = _lineage_request(value)
        if (lineage.pocket_id != request.pocket_id or lineage.chain != request.chain
                or lineage.numbering_scheme != request.numbering_scheme):
            raise ValueError("pocket artifact source identity mismatch")
        atoms = self._selected_atoms(structure, lineage)
        _unambiguous(atoms)
        box = _geometry(value)
        recomputed = _box(atoms, box.margin, lineage.source_kind)
        if box != recomputed:
            raise ValueError("pocket artifact geometry does not match current target coordinates")
        return PocketBinding(request.pocket_id, target.identifier, request.chain,
            lineage.numbering_scheme, "artifact", lineage.residues, request.artifact,
            self.provider_id, self.provider_version, target.structure_artifact.id,
            lineage.reference_ligand, box)


def _box(atoms: tuple[PDBAtom, ...], margin: float, source_kind: str) -> PocketGeometry:
    axes = tuple(tuple(atom.xyz[index] for atom in atoms) for index in range(3))
    center = tuple(round((min(axis) + max(axis)) / 2, 3) for axis in axes)
    size = tuple(round(max(axis) - min(axis) + 2 * margin, 3) for axis in axes)
    return PocketGeometry(center, size, "angstrom",
                          f"verified_{source_kind}_bounding_box", margin)


def _unambiguous(atoms: tuple[PDBAtom, ...]) -> None:
    locations = {}
    for atom in atoms:
        key = (atom.record, atom.chain, atom.residue_id, atom.atom_name)
        locations.setdefault(key, set()).add(atom.alternate_location)
    if any(len(values) > 1 or values not in ({""}, {"A"}) for values in locations.values()):
        raise ValueError("selected pocket atoms contain ambiguous alternate locations")


def _manifest_payload(target, request, box):
    return {"schema_version": "pocket-v1", "pocket_id": request.pocket_id,
        "target_identifier": target.identifier, "target_artifact_id": target.structure_artifact.id,
        "chain": request.chain, "numbering_scheme": request.numbering_scheme,
        "source_kind": request.source_kind, "residues": list(request.residues),
        "reference_ligand": request.reference_ligand, "center": list(box.center),
        "size": list(box.size), "units": box.units, "method": box.method,
        "margin": box.margin}


def _geometry(value: Mapping[str, object]) -> PocketGeometry:
    center, size = value.get("center"), value.get("size")
    if (not isinstance(center, list) or len(center) != 3
            or not isinstance(size, list) or len(size) != 3):
        raise ValueError("pocket manifest geometry is invalid")
    return PocketGeometry(tuple(center), tuple(size), str(value.get("units", "")),
                          str(value.get("method", "")), value.get("margin"))


def _lineage_request(value: Mapping[str, object]) -> PocketRequest:
    source = value.get("source_kind")
    numbering = value.get("numbering_scheme")
    residues = value.get("residues")
    reference = value.get("reference_ligand")
    if source not in {"residues", "reference_ligand"}:
        raise ValueError("pocket manifest source kind is invalid")
    if numbering not in {"pdb_auth", "pdb_author"}:
        raise ValueError("pocket manifest numbering scheme is invalid")
    if (not isinstance(residues, list) or any(not isinstance(item, str) for item in residues)
            or not isinstance(reference, str)):
        raise ValueError("pocket manifest source identity is invalid")
    return PocketRequest(str(value.get("pocket_id", "")), str(value.get("chain", "")),
                         numbering, source, tuple(residues),
                         reference_ligand=reference)


def _artifact_ref(pocket_id: str, path: Path):
    from .contracts import ArtifactRef
    return ArtifactRef(f"rcsb-pocket-{pocket_id}", path.name, "application/json", str(path))
