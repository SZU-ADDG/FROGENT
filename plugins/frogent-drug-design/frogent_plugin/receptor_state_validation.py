"""Immutable receptor-state artifact validation and identity."""

import hashlib
import math
import re

from .docking_local import contained_file
from .docking_state_types import ReceptorAddedHeavyAtom, ReceptorMovedHeavyAtom


def heavy_atoms(path, chain):
    return heavy_atoms_bytes(artifact_bytes(path, "receptor state artifact"), chain)


def pdb_atoms(path, chain):
    return pdb_atoms_bytes(artifact_bytes(path, "receptor state artifact"), chain)


def validate_pqr(path, chain, expected, expected_all=None):
    return validate_pqr_bytes(artifact_bytes(path, "PDB2PQR charge artifact"), chain,
                              expected, expected_all)


def state_changes(source, prepared, chain):
    missing = set(source) - set(prepared)
    if missing:
        raise ValueError("PDB2PQR receptor state lost polymer heavy atoms")
    extras = set(prepared) - set(source)
    terminal_number, terminal_icode, _ = next(reversed(source))
    terminal_key = (terminal_number, terminal_icode, "OXT")
    backbone = {(terminal_number, terminal_icode, atom) for atom in ("C", "O", "CA")}
    if extras not in (set(), {terminal_key}) or (extras and (
            terminal_key in source or not backbone.issubset(source))):
        raise ValueError("PDB2PQR receptor state added an unsupported heavy atom")
    terminal_names = {source[key][0] for key in backbone if key in source}
    if extras and (len(terminal_names) != 1
            or prepared[terminal_key][0] not in terminal_names):
        raise ValueError("PDB2PQR terminal OXT residue identity is invalid")
    moved = []
    for key in source:
        source_name, source_xyz = source[key]
        prepared_name, prepared_xyz = prepared[key]
        if source_name != prepared_name:
            raise ValueError("PDB2PQR receptor state changed a residue identity")
        if source_xyz == prepared_xyz:
            continue
        if key[2] in {"N", "CA", "C", "O"}:
            raise ValueError("PDB2PQR receptor state moved a source backbone heavy atom")
        displacement = math.dist(source_xyz, prepared_xyz)
        moved.append(ReceptorMovedHeavyAtom(chain, key[0], key[1], source_name, key[2],
            source_xyz, prepared_xyz, displacement,
            "pdb2pqr_normal_sidechain_preparation"))
    if len(moved) > 256 or len(moved) * 10 > len(source):
        raise ValueError("PDB2PQR receptor side-chain movement exceeds its bound")
    added = tuple(ReceptorAddedHeavyAtom(chain, key[0], key[1], prepared[key][0], key[2],
                                        prepared[key][1]) for key in sorted(extras))
    moved.sort(key=lambda item: (int(item.auth_residue_number), item.insertion_code,
                                 item.residue_name, item.atom_name))
    return added, tuple(moved)


def validate_pqr_bytes(raw, chain, expected, expected_all=None):
    _validate_raw(raw, "PDB2PQR charge artifact")
    values, serials = {}, set()
    for line in raw.decode("ascii").splitlines():
        if not line.startswith("ATOM"):
            continue
        tokens = line.split()
        if len(tokens) != 11 or not tokens[1].isdigit() or tokens[4] != chain:
            raise ValueError("PDB2PQR charge artifact atom or chain is malformed")
        match = re.fullmatch(r"(-?\d+)([A-Za-z]?)", tokens[5])
        if not match:
            raise ValueError("PDB2PQR charge artifact residue identity is malformed")
        numbers = tuple(float(item) for item in tokens[6:11])
        if any(not math.isfinite(item) for item in numbers) or numbers[-1] < 0:
            raise ValueError("PDB2PQR coordinates, charge, and radius must be finite")
        serial = int(tokens[1])
        if serial in serials:
            raise ValueError("PDB2PQR atom serial is duplicated")
        serials.add(serial)
        key = (match.group(1), match.group(2), tokens[2])
        if key in values:
            raise ValueError("PDB2PQR atom identity is duplicated")
        values[key] = (tokens[3], numbers[:3], numbers[3], numbers[4])
    if expected_all is None:
        heavy = {key: value[1] for key, value in expected.items()}
        actual = {key: value[1] for key, value in values.items()
                  if not key[2].upper().startswith("H")}
        if actual != heavy:
            raise ValueError("PDB2PQR charge artifact heavy atom identity or coordinates drifted")
        return (0, 0)
    if set(values) != set(expected_all):
        raise ValueError("PDB2PQR atom identity set does not match the prepared receptor")
    hydrogen_count = zero_radius_count = 0
    for key, (residue, xyz, _, radius) in values.items():
        expected_residue, expected_xyz, is_hydrogen = expected_all[key]
        if (residue, xyz) != (expected_residue, expected_xyz):
            raise ValueError("PDB2PQR atom identity or coordinates drifted")
        if is_hydrogen:
            hydrogen_count += 1
            zero_radius_count += radius == 0
        elif radius <= 0:
            raise ValueError("PDB2PQR heavy atom radius must be positive")
    return hydrogen_count, zero_radius_count


def heavy_atoms_bytes(raw, chain):
    return {key: (value[0], value[1]) for key, value in
            pdb_atoms_bytes(raw, chain).items() if not value[2]}


def pdb_atoms_bytes(raw, chain):
    _validate_raw(raw, "source receptor state bytes")
    values, serials = {}, set()
    for line in raw.decode("ascii").splitlines():
        if not line.startswith("ATOM"):
            continue
        if len(line) < 54 or line[21].strip() != chain or line[16].strip():
            raise ValueError("receptor state chain, atom, or alternate location is invalid")
        try:
            serial = int(line[6:11])
        except ValueError as exc:
            raise ValueError("receptor state atom serial is malformed") from exc
        key = (line[22:26].strip(), line[26].strip(), line[12:16].strip())
        xyz = tuple(float(line[a:b]) for a, b in ((30, 38), (38, 46), (46, 54)))
        if serial <= 0 or serial in serials or key in values \
                or any(not math.isfinite(item) for item in xyz):
            raise ValueError("receptor state atoms are duplicate or nonfinite")
        serials.add(serial)
        values[key] = (line[17:20].strip(), xyz, _hydrogen(line))
    if not values:
        raise ValueError("receptor state contains no polymer atoms")
    return values


def receptor_state_id(target, chain, ph, force_field, version, propka_version,
                      propka_executable, pdb, pqr):
    payload = b"|".join((pdb, pqr, target.encode(), chain.encode(), str(ph).encode(),
        force_field.encode(), version.encode(), propka_version.encode(),
        propka_executable.encode()))
    digest = hashlib.sha256(payload).hexdigest()[:16]
    return f"receptor-{target}-{chain}-ph{ph:g}-{digest}"


def revalidate_receptor_state(root, state, source_pdb):
    pdb_path = contained_file(root, state.artifact)
    pqr_path = contained_file(root, state.charge_artifact)
    pdb_raw = artifact_bytes(pdb_path, "receptor state artifact")
    pqr_raw = artifact_bytes(pqr_path, "PDB2PQR charge artifact")
    source_atoms = heavy_atoms_bytes(source_pdb, state.chain)
    prepared_all = pdb_atoms_bytes(pdb_raw, state.chain)
    prepared_atoms = {key: (value[0], value[1]) for key, value in prepared_all.items()
                      if not value[2]}
    added, moved = state_changes(source_atoms, prepared_atoms, state.chain)
    if (added, moved) != (state.added_heavy_atoms, state.moved_heavy_atoms):
        raise ValueError("selected receptor state atom changes do not match bound provenance")
    if (len(prepared_atoms), len(source_atoms)) != (state.polymer_heavy_atom_count,
                                                    state.source_polymer_heavy_atom_count):
        raise ValueError("selected receptor state heavy atom counts do not match provenance")
    hydrogen_counts = validate_pqr_bytes(pqr_raw, state.chain, prepared_atoms, prepared_all)
    if hydrogen_counts != (state.hydrogen_atom_count,
                           state.zero_radius_hydrogen_count):
        raise ValueError("selected receptor state hydrogen counts do not match provenance")
    actual = receptor_state_id(state.target_identifier, state.chain, state.ph,
        state.force_field, state.provider_version, state.propka_version,
        state.propka_executable, pdb_raw, pqr_raw)
    if actual != state.state_id:
        raise ValueError("selected receptor state identity does not match current artifacts")
    return pdb_raw, pqr_path


def artifact_bytes(path, label):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} is missing or a symlink")
    raw = path.read_bytes()
    _validate_raw(raw, label)
    return raw


def text_artifact(path, label):
    return artifact_bytes(path, label).decode("ascii")


def _validate_raw(raw, label):
    if not raw or len(raw) > 20 * 1024 * 1024 or b"\x00" in raw:
        raise ValueError(f"{label} is empty, binary, or oversized")


def _hydrogen(line):
    element = line[76:78].strip().upper() if len(line) >= 78 else ""
    return element == "H" or line[12:16].strip().upper().startswith("H")
