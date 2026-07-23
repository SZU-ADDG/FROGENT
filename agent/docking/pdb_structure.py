"""Strict, small parser for auth-numbered PDB coordinate evidence."""

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PDBAtom:
    record: str
    atom_name: str
    residue_name: str
    chain: str
    residue_number: str
    alternate_location: str
    xyz: tuple[float, float, float]

    @property
    def residue_id(self) -> str:
        return self.residue_name + self.residue_number

    @property
    def ligand_id(self) -> str:
        return f"{self.residue_name}:{self.chain}:{self.residue_number}"


@dataclass(frozen=True, slots=True)
class ParsedPDB:
    entry_id: str
    chains: tuple[str, ...]
    atoms: tuple[PDBAtom, ...]

    def residue_atoms(self, chain: str, residue_id: str) -> tuple[PDBAtom, ...]:
        return tuple(item for item in self.atoms if item.record == "ATOM"
                     and item.chain == chain and item.residue_id == residue_id)

    def ligand_atoms(self, ligand_id: str) -> tuple[PDBAtom, ...]:
        return tuple(item for item in self.atoms if item.record == "HETATM"
                     and item.ligand_id == ligand_id)

    def ligand_ids(self, component: str, chain: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.ligand_id for item in self.atoms
                     if item.record == "HETATM" and item.residue_name == component
                     and item.chain == chain))


def parse_pdb(raw: bytes, expected_entry: str) -> ParsedPDB:
    if not raw or len(raw) > 10 * 1024 * 1024 or b"\x00" in raw:
        raise ValueError("PDB coordinate payload is empty, binary, or oversized")
    text = raw.decode("ascii", errors="strict")
    if text.lstrip().casefold().startswith(("<html", "<!doctype")):
        raise ValueError("PDB coordinate endpoint returned HTML")
    lines = text.splitlines()
    if sum(line.startswith("MODEL ") for line in lines) > 1:
        raise ValueError("multi-model PDB coordinates are ambiguous for docking")
    header = next((line for line in lines if line.startswith("HEADER")), "")
    entry_id = header[62:66].strip().upper() if len(header) >= 66 else ""
    expected = expected_entry.upper()
    if not re.fullmatch(r"[0-9][A-Z0-9]{3}", entry_id) or entry_id != expected:
        raise ValueError("PDB coordinate identity does not match the requested entry")
    atoms = tuple(_atom(line) for line in lines if line.startswith(("ATOM  ", "HETATM")))
    if not atoms or not any(item.record == "ATOM" for item in atoms):
        raise ValueError("PDB coordinate payload contains no polymer atoms")
    chains = tuple(dict.fromkeys(item.chain for item in atoms if item.record == "ATOM"))
    if not chains:
        raise ValueError("PDB coordinate payload contains no auth chains")
    return ParsedPDB(entry_id, chains, atoms)


def _atom(line: str) -> PDBAtom:
    if len(line) < 54:
        raise ValueError("PDB coordinate record is truncated")
    record, atom_name = line[:6].strip(), line[12:16].strip()
    alternate_location = line[16].strip()
    residue_name, chain = line[17:20].strip(), line[21].strip()
    residue_number = line[22:26].strip() + line[26].strip()
    if (record not in {"ATOM", "HETATM"} or not atom_name or not residue_name
            or not residue_number or (record == "ATOM" and not chain)):
        raise ValueError("PDB coordinate record identity is malformed")
    try:
        xyz = tuple(float(line[start:end]) for start, end in ((30, 38), (38, 46), (46, 54)))
    except ValueError as exc:
        raise ValueError("PDB atom coordinates are malformed") from exc
    if any(not math.isfinite(value) for value in xyz):
        raise ValueError("PDB atom coordinates must be finite")
    return PDBAtom(record, atom_name, residue_name, chain, residue_number,
                   alternate_location, xyz)
