"""Exact Vina-pose molecule reconstruction for a PLIP PDB complex."""

import math
import re
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Protocol

from .molecular_binding import MolecularInputBinding


@dataclass(frozen=True, slots=True)
class PoseLigand:
    pdb_records: tuple[str, ...]
    conect_records: tuple[str, ...]
    canonical_isomeric_smiles: str
    inchikey: str
    heavy_atom_count: int

    def __post_init__(self) -> None:
        if (not self.pdb_records or not self.canonical_isomeric_smiles.strip()
                or not self.inchikey.strip() or self.heavy_atom_count <= 0):
            raise ValueError("pose ligand reconstruction is incomplete")


class PoseLigandBuilder(Protocol):
    tool: str
    version: str

    def build(self, path: Path, binding: MolecularInputBinding, *, pose_rank: int,
              serial_start: int, residue_name: str, chain: str,
              residue_number: int) -> PoseLigand: ...


class RDKitPoseLigandBuilder:
    tool = "rdkit-pdbqt-pose-reconstructor"

    def __init__(self) -> None:
        self.version = ""

    def build(self, path, binding, *, pose_rank, serial_start, residue_name, chain,
              residue_number):
        text = path.read_text(encoding="ascii")
        _one_model(text, pose_rank)
        smiles = _one_match(text, r"^REMARK SMILES (\S+)\s*$", "pose SMILES")
        mapping = _smiles_index(text)
        atoms = _pdbqt_atoms(text)
        chem, version = _rdkit()
        self.version = version
        molecule = chem.MolFromSmiles(smiles, sanitize=True)
        if molecule is None or len(chem.GetMolFrags(molecule)) != 1:
            raise ValueError("pose SMILES is invalid or disconnected")
        canonical = chem.MolToSmiles(molecule, isomericSmiles=True, canonical=True)
        inchikey = chem.MolToInchiKey(molecule)
        if (canonical, inchikey) != (binding.canonical_isomeric_smiles, binding.inchikey):
            raise ValueError("pose SMILES or InChIKey does not match the selected molecule")
        _mapping_identity(mapping, atoms, molecule.GetNumAtoms())
        heavy = tuple(_atom_record(serial_start + index, atom, atoms[mapping[index + 1]],
                      residue_name, chain, residue_number)
                      for index, atom in enumerate(molecule.GetAtoms()))
        hydrogen_pairs = _hydrogen_pairs(text, atoms, mapping)
        hydrogen_start = serial_start + molecule.GetNumAtoms()
        hydrogens = tuple(_hydrogen_record(hydrogen_start + index, source,
                          residue_name, chain, residue_number, index + 1)
                          for index, (_, source) in enumerate(hydrogen_pairs))
        bonds = (*_conect(molecule, serial_start),
                 *tuple(f"CONECT{serial_start + parent - 1:5d}{hydrogen_start + index:5d}"
                        for index, (parent, _) in enumerate(hydrogen_pairs)))
        return PoseLigand((*heavy, *hydrogens), bonds, canonical, inchikey,
                          molecule.GetNumHeavyAtoms())


def _one_model(text, pose_rank):
    models = re.findall(r"^MODEL\s+(\d+)\s*$", text, re.MULTILINE)
    ends = re.findall(r"^ENDMDL\s*$", text, re.MULTILINE)
    if models != [str(pose_rank)] or len(ends) != 1:
        raise ValueError("selected pose artifact must contain exactly its resolved model")


def _one_match(text, pattern, label):
    values = re.findall(pattern, text, re.MULTILINE)
    if len(values) != 1:
        raise ValueError(f"{label} is missing or ambiguous")
    return values[0]


def _smiles_index(text):
    tokens = []
    for line in text.splitlines():
        if line.startswith("REMARK SMILES IDX "):
            tokens.extend(line.removeprefix("REMARK SMILES IDX ").split())
    if not tokens or len(tokens) % 2 or any(not item.isdigit() for item in tokens):
        raise ValueError("pose SMILES IDX mapping is malformed")
    pairs = tuple(zip(map(int, tokens[::2]), map(int, tokens[1::2])))
    if len({item[0] for item in pairs}) != len(pairs) \
            or len({item[1] for item in pairs}) != len(pairs):
        raise ValueError("pose SMILES IDX mapping contains duplicates")
    return dict(pairs)


def _pdbqt_atoms(text):
    values = {}
    for line in text.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        try:
            serial = int(line[6:11])
            xyz = tuple(float(line[start:end])
                        for start, end in ((30, 38), (38, 46), (46, 54)))
        except ValueError as exc:
            raise ValueError("pose atom identity or coordinates are malformed") from exc
        if serial in values:
            raise ValueError("pose atom serial is duplicated")
        if any(not math.isfinite(item) for item in xyz):
            raise ValueError("pose atom coordinates must be finite")
        values[serial] = (line[12:16].strip(), xyz)
    if not values:
        raise ValueError("pose artifact contains no atoms")
    return values


def _mapping_identity(mapping, atoms, atom_count):
    if set(mapping) != set(range(1, atom_count + 1)):
        raise ValueError("pose SMILES IDX does not cover every molecular atom")
    if any(serial not in atoms for serial in mapping.values()):
        raise ValueError("pose SMILES IDX references a missing atom")
    heavy_serials = {serial for serial, (name, _) in atoms.items()
                     if not name.upper().startswith("H")}
    if set(mapping.values()) != heavy_serials:
        raise ValueError("pose heavy atoms are missing, duplicated, or unmapped")


def _hydrogen_pairs(text, atoms, mapping):
    tokens = []
    for line in text.splitlines():
        if line.startswith("REMARK H PARENT "):
            tokens.extend(line.removeprefix("REMARK H PARENT ").split())
    hydrogen_serials = {serial for serial, (name, _) in atoms.items()
                        if name.upper().startswith("H")}
    if not tokens:
        if hydrogen_serials:
            raise ValueError("pose hydrogens lack parent lineage")
        return ()
    if len(tokens) % 2 or any(not item.isdigit() for item in tokens):
        raise ValueError("pose hydrogen-parent mapping is malformed")
    pairs = tuple(zip(map(int, tokens[::2]), map(int, tokens[1::2])))
    parents = {serial: index for index, serial in mapping.items()}
    if (len({item[1] for item in pairs}) != len(pairs)
            or {item[1] for item in pairs} != hydrogen_serials
            or any(parent not in parents for parent, _ in pairs)):
        raise ValueError("pose hydrogen-parent mapping does not match pose atoms")
    return tuple((parents[parent], atoms[hydrogen]) for parent, hydrogen in pairs)


def _atom_record(serial, atom, source, residue, chain, number):
    name = _pdb_atom_identity(serial, atom.GetSymbol(), atom.GetIdx() + 1)
    symbol, (_, xyz) = atom.GetSymbol(), source
    charge = atom.GetFormalCharge()
    charge_text = "  " if not charge else f"{abs(charge)}{'+' if charge > 0 else '-'}"
    return (f"HETATM{serial:5d} {name:^4} {residue:>3} {chain}{number:4d}    "
            f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00  0.00          "
            f"{symbol:>2}{charge_text:>2}")


def _hydrogen_record(serial, source, residue, chain, number, index):
    name = _pdb_atom_identity(serial, "H", index)
    _, xyz = source
    return (f"HETATM{serial:5d} {name:^4} {residue:>3} {chain}{number:4d}    "
            f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00  0.00"
            "           H  ")


def _pdb_atom_identity(serial, symbol, index):
    if isinstance(serial, bool) or not 1 <= serial <= 99999:
        raise ValueError("pose complex atom serial exceeds PDB bounds")
    name = f"{symbol}{index}"
    if len(name) > 4 or not re.fullmatch(r"[A-Za-z0-9]{1,4}", name):
        raise ValueError("pose complex atom name exceeds PDB bounds")
    return name


def _conect(molecule, start):
    values = []
    for bond in molecule.GetBonds():
        left, right = start + bond.GetBeginAtomIdx(), start + bond.GetEndAtomIdx()
        order = 1 if bond.GetIsAromatic() else max(1, int(bond.GetBondTypeAsDouble()))
        values.append(f"CONECT{left:5d}" + f"{right:5d}" * order)
    return tuple(values)


def _rdkit():
    try:
        chem, base = import_module("rdkit.Chem"), import_module("rdkit.rdBase")
    except ModuleNotFoundError as exc:
        raise RuntimeError("RDKit is unavailable for pose reconstruction") from exc
    return chem, base.rdkitVersion
