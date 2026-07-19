"""Explicit, fail-closed receptor component selection for dynamic docking."""

import re
from dataclasses import dataclass
from pathlib import Path

from .docking_local import contained_file
from .docking_types import DockingInput
from .pdb_structure import parse_pdb


@dataclass(frozen=True, slots=True)
class ReceptorComponentPolicy:
    remove_waters: bool = True
    removable_components: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.remove_waters, bool):
            raise ValueError("receptor water policy must be boolean")
        if len(self.removable_components) != len(set(self.removable_components)):
            raise ValueError("removable receptor components must be unique")
        if any(not re.fullmatch(r"[A-Z0-9]{1,3}:[A-Za-z0-9]:-?\d+[A-Z]?", item)
               for item in self.removable_components):
            raise ValueError("removable receptor component identity is malformed")


def select_receptor(root: Path, value: DockingInput, policy: ReceptorComponentPolicy):
    path = contained_file(root, value.target.structure_artifact)
    raw = path.read_bytes()
    structure = parse_pdb(raw, value.target.identifier)
    chain, ligand = value.pocket.chain, value.pocket.reference_ligand
    if chain not in structure.chains or not structure.ligand_atoms(ligand):
        raise ValueError("reference ligand or chain is absent from current target coordinates")
    text = raw.decode("ascii")
    selected, removed, excluded, unknown = [], {}, {}, []
    for line in text.splitlines():
        record = line[:6].strip()
        if record == "ATOM":
            _append_polymer(line, chain, selected, excluded)
        elif record == "HETATM":
            _classify_hetero(line, ligand, chain, structure.chains, policy,
                             removed, excluded, unknown)
    if unknown:
        raise ValueError("unapproved receptor HETATM components: "
                         + ", ".join(dict.fromkeys(unknown)))
    _contiguous(selected)
    expected = sum(1 for atom in structure.atoms if atom.record == "ATOM" and atom.chain == chain)
    if len(selected) != expected:
        raise ValueError("selected receptor polymer records are incomplete")
    header = next(line for line in text.splitlines() if line.startswith("HEADER"))
    output = (header + "\n" + "\n".join(selected) + "\nTER\nEND\n").encode()
    details = _details(chain, selected, removed, excluded)
    dropped = sum(len(lines) for lines in (*removed.values(), *excluded.values()))
    return output, tuple(details), dropped


def _details(chain, selected, removed, excluded):
    values = [f"selected_chain={chain}", f"polymer_atom_records={len(selected)}"]
    water_count = sum(len(lines) for key, lines in removed.items() if key.startswith("water:"))
    other_water_count = sum(len(lines) for key, lines in excluded.items()
                            if ":HOH:" in key or ":WAT:" in key)
    values.extend(f"removed:{key}={len(lines)}" for key, lines in sorted(removed.items())
                  if not key.startswith("water:"))
    if water_count:
        values.append(f"removed:waters={water_count}")
    values.extend(f"excluded:{key}={len(lines)}" for key, lines in sorted(excluded.items())
                  if ":HOH:" not in key and ":WAT:" not in key)
    if other_water_count:
        values.append(f"excluded:unselected_chain_waters={other_water_count}")
    return tuple(values)


def _classify_hetero(line, ligand, chain, chains, policy, removed, excluded, unknown):
    identity = _component(line)
    item_chain = line[21].strip()
    if identity == ligand:
        removed.setdefault(f"reference_ligand:{identity}", []).append(line)
        return
    if item_chain != chain and item_chain in chains:
        excluded.setdefault(f"unselected_chain_component:{identity}", []).append(line)
        return
    if identity.split(":", 1)[0] in {"HOH", "WAT"} and policy.remove_waters:
        removed.setdefault(f"water:{identity}", []).append(line)
        return
    if identity in policy.removable_components:
        removed.setdefault(f"configured_component:{identity}", []).append(line)
        return
    unknown.append(identity)


def _append_polymer(line, chain, selected, excluded):
    item_chain = line[21].strip()
    if item_chain == chain:
        if line[16].strip():
            raise ValueError("selected receptor polymer alternate locations require an explicit policy")
        selected.append(line)
        return
    excluded.setdefault(f"polymer_chain:{item_chain}", []).append(line)


def _component(line):
    return f"{line[17:20].strip()}:{line[21].strip()}:{line[22:26].strip()}{line[26].strip()}"


def _contiguous(lines):
    seen, previous = set(), None
    for line in lines:
        residue = (line[21].strip(), line[22:26].strip(), line[26].strip())
        if residue != previous and residue in seen:
            raise ValueError(f"interrupted receptor residue requires lossless repair: {residue}")
        seen.add(residue)
        previous = residue
