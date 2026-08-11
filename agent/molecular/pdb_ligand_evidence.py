"""Structure-matched ligand evidence from the official RCSB PDB Data API."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from importlib import import_module
from typing import Any


BASE_URL = "https://data.rcsb.org/rest/v1/core"
FetchJSON = Callable[[str], dict[str, Any]]


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "FROGENT-pdb-evidence/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def rank_candidates_against_pdb_ligands(
    pdb_id: str,
    candidate_smiles: list[str] | tuple[str, ...],
    *,
    fetcher: FetchJSON = fetch_json,
) -> dict[str, Any]:
    normalized = pdb_id.strip().upper()
    if len(normalized) != 4 or not normalized.isalnum():
        raise ValueError("pdb_id must be a four-character PDB identifier")
    if not candidate_smiles:
        raise ValueError("candidate_smiles must not be empty")
    chem = import_module("rdkit.Chem")
    data_structs = import_module("rdkit.DataStructs")
    fingerprint_module = import_module("rdkit.Chem.rdFingerprintGenerator")
    entry_url = f"{BASE_URL}/entry/{normalized}"
    entry = fetcher(entry_url)
    entity_ids = (
        entry.get("rcsb_entry_container_identifiers", {}).get("non_polymer_entity_ids") or []
    )
    ligands = []
    provenance_urls = [entry_url]
    for entity_id in entity_ids:
        entity_url = f"{BASE_URL}/nonpolymer_entity/{normalized}/{entity_id}"
        entity = fetcher(entity_url)
        provenance_urls.append(entity_url)
        component_id = str(entity.get("pdbx_entity_nonpoly", {}).get("comp_id") or "")
        if not component_id:
            continue
        component_url = f"{BASE_URL}/chemcomp/{component_id}"
        component = fetcher(component_url)
        provenance_urls.append(component_url)
        descriptor = component.get("rcsb_chem_comp_descriptor", {})
        smiles = descriptor.get("SMILES_stereo") or descriptor.get("SMILES")
        molecule = chem.MolFromSmiles(str(smiles or ""))
        if molecule is None or molecule.GetNumHeavyAtoms() < 6:
            continue
        ligands.append({
            "component_id": component_id,
            "name": entity.get("pdbx_entity_nonpoly", {}).get("name"),
            "canonical_smiles": chem.MolToSmiles(
                molecule, canonical=True, isomericSmiles=True
            ),
        })
    if not ligands:
        return {
            "method": "RCSB PDB non-polymer ligand structure matching",
            "pdb_id": normalized,
            "status": "no_structured_ligand",
            "ligands": [],
            "results": [],
            "provenance_urls": provenance_urls,
        }
    generator = fingerprint_module.GetMorganGenerator(radius=2, fpSize=2048)
    ligand_fingerprints = [
        generator.GetFingerprint(chem.MolFromSmiles(row["canonical_smiles"]))
        for row in ligands
    ]
    results = []
    for input_smiles in candidate_smiles:
        molecule = chem.MolFromSmiles(input_smiles)
        if molecule is None:
            raise ValueError(f"invalid candidate SMILES: {input_smiles}")
        fingerprint = generator.GetFingerprint(molecule)
        similarities = data_structs.BulkTanimotoSimilarity(
            fingerprint, ligand_fingerprints
        )
        best_index = max(range(len(similarities)), key=similarities.__getitem__)
        results.append({
            "input_smiles": input_smiles,
            "canonical_smiles": chem.MolToSmiles(
                molecule, canonical=True, isomericSmiles=True
            ),
            "max_tanimoto": float(similarities[best_index]),
            "matched_component_id": ligands[best_index]["component_id"],
            "matched_ligand_name": ligands[best_index]["name"],
            "matched_ligand_smiles": ligands[best_index]["canonical_smiles"],
        })
    results.sort(key=lambda row: row["max_tanimoto"], reverse=True)
    return {
        "method": "RCSB PDB non-polymer ligand structure matching",
        "pdb_id": normalized,
        "status": "resolved",
        "fingerprint": {"type": "Morgan", "radius": 2, "n_bits": 2048},
        "ligands": ligands,
        "results": results,
        "provenance_urls": provenance_urls,
    }
