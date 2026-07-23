"""Typed TrioWorkspace task contracts and multipart encoding."""

from __future__ import annotations

import math
import re
import secrets
from pathlib import Path
from typing import Any


ENGINE_FIELDS = {
    "triomol2": {
        "engine", "taskName", "targetName", "centerX", "centerY", "centerZ",
        "sizeX", "sizeY", "sizeZ", "candidateCount", "searchBudget", "seed", "notes",
    },
    "triopep": {
        "engine", "taskName", "receptorChain", "peptideChain", "peptideLength",
        "candidateCount", "searchBudget", "notes",
    },
    "trioprotac": {
        "engine", "taskName", "targetSystem", "candidateCount", "searchBudget",
        "seed", "notes",
    },
    "trioires": {
        "engine", "taskName", "family", "candidateCount", "searchBudget", "seed", "notes",
    },
    "triodna": {
        "engine", "taskName", "cellContext", "referenceSequence", "editableStart",
        "editableEnd", "candidateCount", "seed", "notes",
    },
}


def _text(arguments: dict[str, Any], name: str, maximum: int) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be a non-empty string of at most {maximum} characters")
    if name != "notes" and any(ord(character) < 32 for character in value):
        raise ValueError(f"{name} contains unsupported control characters")
    return value.strip()


def _optional_text(arguments: dict[str, Any], name: str, maximum: int) -> str:
    value = arguments.get(name, "")
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{name} must be a string of at most {maximum} characters")
    return value.strip()


def _integer(arguments: dict[str, Any], name: str, minimum: int, maximum: int) -> int:
    value = arguments.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in {minimum}..{maximum}")
    return value


def _number_triplet(arguments: dict[str, Any], name: str, *, positive: bool) -> tuple[float, ...]:
    values = arguments.get(name)
    if not isinstance(values, list) or len(values) != 3:
        raise ValueError(f"{name} must contain exactly three numbers")
    result = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must contain exactly three numbers")
        number = float(value)
        if not math.isfinite(number) or (positive and not 0 < number <= 64):
            raise ValueError(f"{name} contains an unsupported value")
        if not positive and not -10000 <= number <= 10000:
            raise ValueError(f"{name} contains an unsupported value")
        result.append(number)
    return tuple(result)


def _receptor(path_value: Any, project_root: Path) -> tuple[str, bytes]:
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError("receptor_pdb_path must be a non-empty absolute path")
    path = Path(path_value)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("receptor_pdb_path must be an absolute regular file without symlinks")
    resolved = path.resolve(strict=True)
    if project_root != resolved and project_root not in resolved.parents:
        raise ValueError("receptor_pdb_path escaped the FROGENT project")
    if not resolved.is_file() or resolved.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("receptor PDB is missing or exceeds 20 MiB")
    payload = resolved.read_bytes()
    if not payload or b"\0" in payload:
        raise ValueError("receptor PDB is empty or binary")
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("receptor PDB must use ASCII text") from error
    if not any(line.startswith(("ATOM  ", "HETATM")) for line in text.splitlines()):
        raise ValueError("receptor PDB contains no atom records")
    return resolved.name, payload


def task_form(tool: str, arguments: dict[str, Any], project_root: Path) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
    title = _text(arguments, "task_name", 120)
    notes = _optional_text(arguments, "notes", 2000)
    files: dict[str, tuple[str, bytes]] = {}
    if tool == "trio_submit_mol2":
        center = _number_triplet(arguments, "center", positive=False)
        size = _number_triplet(arguments, "size", positive=True)
        files["receptor"] = _receptor(arguments.get("receptor_pdb_path"), project_root)
        fields = {
            "engine": "triomol2", "taskName": title,
            "targetName": _text(arguments, "target_name", 120),
            "centerX": str(center[0]), "centerY": str(center[1]), "centerZ": str(center[2]),
            "sizeX": str(size[0]), "sizeY": str(size[1]), "sizeZ": str(size[2]),
            "candidateCount": str(_integer(arguments, "candidate_count", 1, 10)),
            "searchBudget": str(_integer(arguments, "search_budget", 100, 500)),
            "seed": str(_integer(arguments, "seed", 0, 2_147_483_647)), "notes": notes,
        }
        if int(fields["searchBudget"]) not in {100, 200, 500}:
            raise ValueError("search_budget must be one of 100, 200, or 500")
    elif tool == "trio_submit_peptide":
        files["receptor"] = _receptor(arguments.get("receptor_pdb_path"), project_root)
        receptor_chain = _text(arguments, "receptor_chain", 1).upper()
        peptide_chain = _text(arguments, "peptide_chain", 1).upper()
        if not receptor_chain.isalnum() or not peptide_chain.isalnum() or receptor_chain == peptide_chain:
            raise ValueError("receptor_chain and peptide_chain must be distinct alphanumeric characters")
        budget = _integer(arguments, "search_budget", 4, 16)
        if budget not in {4, 8, 16}:
            raise ValueError("search_budget must be one of 4, 8, or 16")
        fields = {
            "engine": "triopep", "taskName": title, "receptorChain": receptor_chain,
            "peptideChain": peptide_chain,
            "peptideLength": str(_integer(arguments, "peptide_length", 4, 20)),
            "candidateCount": "1", "searchBudget": str(budget), "notes": notes,
        }
    else:
        fields = _non_file_form(tool, arguments, title, notes)
    if set(fields) != ENGINE_FIELDS[fields["engine"]]:
        raise RuntimeError("internal task form does not match the engine contract")
    return fields, files


def _non_file_form(tool: str, arguments: dict[str, Any], title: str, notes: str) -> dict[str, str]:
    seed = str(_integer(arguments, "seed", 0, 2_147_483_647))
    if tool == "trio_submit_protac":
        budget = _integer(arguments, "search_budget", 8, 32)
        if budget not in {8, 16, 32} or arguments.get("target_system") != "brd4-8g46":
            raise ValueError("unsupported TrioPROTAC target or search budget")
        return {"engine": "trioprotac", "taskName": title, "targetSystem": "brd4-8g46",
                "candidateCount": "1", "searchBudget": str(budget), "seed": seed, "notes": notes}
    if tool == "trio_submit_ires":
        budget = _integer(arguments, "search_budget", 1, 4)
        family = arguments.get("family")
        if budget not in {1, 2, 4} or family not in {"CrPV", "PSIV"}:
            raise ValueError("unsupported TrioIRES family or search budget")
        return {"engine": "trioires", "taskName": title, "family": str(family),
                "candidateCount": "1", "searchBudget": str(budget), "seed": seed, "notes": notes}
    if tool == "trio_submit_dna":
        count = str(_integer(arguments, "candidate_count", 1, 10))
        sequence = re.sub(r"\s+", "", _text(arguments, "reference_sequence", 400)).upper()
        if len(sequence) != 200 or not re.fullmatch(r"[ACGT]{200}", sequence):
            raise ValueError("reference_sequence must contain exactly 200 A, C, G, and T bases")
        start = _integer(arguments, "editable_start", 1, 200)
        end = _integer(arguments, "editable_end", 1, 200)
        if end < start or arguments.get("cell_context") not in {"HepG2", "K562", "SK-N-SH"}:
            raise ValueError("unsupported TrioDNA cell context or editable interval")
        return {"engine": "triodna", "taskName": title, "cellContext": str(arguments["cell_context"]),
                "referenceSequence": sequence, "editableStart": str(start), "editableEnd": str(end),
                "candidateCount": count, "seed": seed, "notes": notes}
    raise ValueError(f"unsupported submission tool: {tool}")


def multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes]]) -> tuple[str, bytes]:
    content = b"".join(value.encode("utf-8") for value in fields.values())
    content += b"".join(payload for _, payload in files.values())
    while True:
        boundary = "frogent-trio-" + secrets.token_hex(16)
        if boundary.encode() not in content:
            break
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode(),
            value.encode("utf-8"), b"\r\n",
        ])
    for name, (filename, payload) in files.items():
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)[:160]
        chunks.extend([
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{safe}\"\r\n".encode(),
            b"Content-Type: chemical/x-pdb\r\n\r\n", payload, b"\r\n",
        ])
    chunks.append(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", b"".join(chunks)
