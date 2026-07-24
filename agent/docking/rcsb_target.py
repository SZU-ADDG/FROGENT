"""No-key RCSB target acquisition with exact entry and auth-chain verification."""

import json
import re
from pathlib import Path
from typing import Mapping

from agent.research.biomedical_providers import HttpTransport, UrllibTransport
from agent.core.contracts import ArtifactRef
from agent.docking.docking_types import TargetRequest, VerifiedTargetIdentity
from agent.docking.pdb_structure import parse_pdb


class RCSBTargetProvider:
    provider_id = "rcsb-pdb"
    provider_version = "data-api-v1+pdb-v3.3"
    DATA_BASE = "https://data.rcsb.org/rest/v1/core"
    FILE_BASE = "https://files.rcsb.org/download"

    def __init__(self, project_root: Path, artifact_root: Path | None = None,
                 transport: HttpTransport | None = None) -> None:
        self.project_root = project_root.resolve(strict=True)
        self.artifact_root = artifact_root or (self.project_root / "runtime/app/targets")
        _lexically_contained(self.project_root, self.artifact_root)
        self.transport = transport or UrllibTransport()

    def resolve(self, request: TargetRequest) -> VerifiedTargetIdentity:
        if request.kind != "pdb":
            raise ValueError("RCSB executable target resolution requires an explicit PDB accession")
        entry_id = request.value.upper()
        if not re.fullmatch(r"[0-9][A-Z0-9]{3}", entry_id):
            raise ValueError("PDB accession is malformed")
        metadata_url = f"{self.DATA_BASE}/entry/{entry_id}"
        metadata = _json_object(self.transport.get(metadata_url, {}), "RCSB entry metadata")
        entity_ids = _entry(metadata, entry_id)
        chains = self._auth_chains(entry_id, entity_ids)
        if request.chain and chains.count(request.chain) != 1:
            raise ValueError("requested auth chain is absent or ambiguous in RCSB metadata")
        coordinate_url = f"{self.FILE_BASE}/{entry_id}.pdb"
        raw = self.transport.get(coordinate_url, {})
        structure = parse_pdb(raw, entry_id)
        if any(chain not in structure.chains for chain in chains):
            raise ValueError("RCSB metadata chains do not match the coordinate artifact")
        if request.chain and request.chain not in structure.chains:
            raise ValueError("requested auth chain is absent from the coordinate artifact")
        path = _store(self.project_root, self.artifact_root / entry_id / f"{entry_id}.pdb", raw)
        artifact = ArtifactRef(f"rcsb-pdb-{entry_id}", f"{entry_id}.pdb", "chemical/x-pdb",
                               str(path))
        return VerifiedTargetIdentity("pdb", entry_id, tuple(chains), artifact,
            self.provider_id, self.provider_version, request.value, metadata_url, coordinate_url)

    def _auth_chains(self, entry_id: str, entity_ids: tuple[str, ...]) -> list[str]:
        chains = []
        for entity_id in entity_ids:
            url = f"{self.DATA_BASE}/polymer_entity/{entry_id}/{entity_id}"
            value = _json_object(self.transport.get(url, {}), "RCSB polymer metadata")
            identifiers = value.get("rcsb_polymer_entity_container_identifiers")
            if not isinstance(identifiers, Mapping):
                raise ValueError("RCSB polymer metadata identifiers are missing")
            if str(identifiers.get("entry_id", "")).upper() != entry_id:
                raise ValueError("RCSB polymer metadata entry identity mismatch")
            items = identifiers.get("auth_asym_ids")
            if not isinstance(items, list) or not items:
                raise ValueError("RCSB polymer metadata auth chains are missing")
            if any(not isinstance(item, str) or not item.strip() for item in items):
                raise ValueError("RCSB polymer metadata auth chain is malformed")
            chains.extend(items)
        if not chains or len(chains) != len(set(chains)):
            raise ValueError("RCSB auth-chain identity is missing or ambiguous")
        return chains


def _entry(value: Mapping[str, object], entry_id: str) -> tuple[str, ...]:
    identifiers = value.get("rcsb_entry_container_identifiers")
    if not isinstance(identifiers, Mapping):
        raise ValueError("RCSB entry identifiers are missing")
    identities = (str(value.get("rcsb_id", "")).upper(),
                  str(identifiers.get("entry_id", "")).upper())
    if identities != (entry_id, entry_id):
        raise ValueError("RCSB entry metadata identity mismatch")
    entity_ids = identifiers.get("polymer_entity_ids")
    if (not isinstance(entity_ids, list) or not 1 <= len(entity_ids) <= 64
            or any(not isinstance(item, str) or not item.strip() for item in entity_ids)
            or len(entity_ids) != len(set(entity_ids))):
        raise ValueError("RCSB polymer entity identities are malformed")
    return tuple(entity_ids)


def _json_object(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is malformed") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _store(root: Path, path: Path, raw: bytes) -> Path:
    _make_contained_directory(root, path.parent)
    if path.is_symlink():
        raise ValueError("RCSB artifact path cannot be a symlink")
    if path.exists():
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
        if not resolved.is_file() or resolved.read_bytes() != raw:
            raise ValueError("existing RCSB artifact conflicts with the verified payload")
        return resolved
    with path.open("xb") as handle:
        handle.write(raw)
    resolved = path.resolve(strict=True)
    resolved.relative_to(root)
    return resolved


def _make_contained_directory(root: Path, path: Path) -> Path:
    _lexically_contained(root, path)
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("RCSB artifact directory cannot contain symlinks")
        current.mkdir(exist_ok=True)
    resolved = path.resolve(strict=True)
    resolved.relative_to(root)
    return resolved


def _lexically_contained(root: Path, path: Path) -> None:
    if not path.is_absolute():
        raise ValueError("RCSB artifact root must be absolute")
    path.relative_to(root)
