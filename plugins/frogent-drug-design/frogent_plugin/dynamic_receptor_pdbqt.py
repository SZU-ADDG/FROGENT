"""Strict Meeko receptor PDBQT identity validation and terminal-name repair."""

import math


def repair_and_validate_receptor(path, source_path, chain):
    text = _output(path, "receptor PDBQT").decode("ascii")
    source_text = _output(source_path, "selected receptor PDB").decode("ascii")
    source, prepared = _heavy_atom_map(source_text, chain), _heavy_atom_map(text, chain)
    details = _repair_terminal_oxygen_names(path, text, source, prepared, chain)
    text = _output(path, "receptor PDBQT").decode("ascii")
    atoms = [line for line in text.splitlines() if line.startswith("ATOM")]
    if not atoms or any(len(line) < 54 or line[21].strip() != chain for line in atoms):
        raise ValueError("Meeko receptor output chain is missing or mismatched")
    _finite_pdbqt(text)
    if source != _heavy_atom_map(text, chain):
        raise ValueError("Meeko receptor output did not preserve selected polymer heavy atoms")
    return details


def _repair_terminal_oxygen_names(path, text, source, prepared, chain):
    if source == prepared:
        return ()
    mismatches = tuple(key for key in source if prepared.get(key) != source[key])
    if len(mismatches) != 2:
        return ()
    first, second = mismatches
    if (first[:3] != second[:3] or {first[3], second[3]} != {"O", "OXT"}
            or prepared.get(first) != source[second] or prepared.get(second) != source[first]):
        return ()
    lines = text.splitlines()
    indices = [index for index, line in enumerate(lines) if line.startswith("ATOM")
               and (line[17:20].strip(), line[22:26].strip(), line[26].strip()) == first[:3]
               and line[12:16].strip() in {"O", "OXT"}]
    if len(indices) != 2 or len({tuple(lines[index].split()[-2:]) for index in indices}) != 1:
        return ()
    by_xyz = {source[first]: first[3], source[second]: second[3]}
    for index in indices:
        xyz = tuple(float(lines[index][start:end])
                    for start, end in ((30, 38), (38, 46), (46, 54)))
        if xyz not in by_xyz:
            return ()
        lines[index] = lines[index][:12] + f"{by_xyz[xyz]:^4}" + lines[index][16:]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return (f"normalized:meeko_terminal_O_OXT_name_permutation="
            f"{chain}:{first[0]}{first[1]}",)


def _heavy_atom_map(text, chain):
    values = {}
    for line in text.splitlines():
        if not line.startswith("ATOM") or _is_hydrogen(line):
            continue
        if len(line) < 54 or line[21].strip() != chain:
            raise ValueError("prepared receptor atom identity is malformed")
        identity = (line[17:20].strip(), line[22:26].strip(), line[26].strip(),
                    line[12:16].strip())
        if identity in values:
            raise ValueError("prepared receptor heavy atom identity is duplicated")
        values[identity] = tuple(float(line[start:end])
                                 for start, end in ((30, 38), (38, 46), (46, 54)))
    if not values:
        raise ValueError("prepared receptor contains no polymer heavy atoms")
    return values


def _is_hydrogen(line):
    element = line[76:78].strip().upper() if len(line) >= 78 else ""
    return element == "H" or line[12:16].strip().upper().startswith("H")


def _output(path, label):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} is missing")
    raw = path.read_bytes()
    if not raw or len(raw) > 20 * 1024 * 1024 or b"\x00" in raw:
        raise ValueError(f"{label} is empty, binary, or oversized")
    return raw


def _finite_pdbqt(text):
    atoms = [line for line in text.splitlines() if line.startswith(("ATOM", "HETATM"))]
    try:
        coordinates = [float(line[start:end]) for line in atoms
                       for start, end in ((30, 38), (38, 46), (46, 54))]
    except ValueError as exc:
        raise ValueError("prepared PDBQT coordinates are malformed") from exc
    if not atoms or any(not math.isfinite(value) for value in coordinates):
        raise ValueError("prepared PDBQT coordinates must be finite")
