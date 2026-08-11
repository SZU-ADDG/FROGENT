"""Typed implementations behind the local chemistry MCP server."""

from __future__ import annotations

from typing import Any

from agent.molecular.chembl_evidence import rank_candidates_against_target_actives
from agent.molecular.pdb_ligand_evidence import rank_candidates_against_pdb_ligands
from agent.molecular.physchem import describe_many, rank_similarity


class ChemistryTools:
    def call(self, name: str, arguments: Any) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        if name == "describe_molecules":
            return self.describe(arguments)
        if name == "rank_molecular_similarity":
            return self.similarity(arguments)
        if name == "rank_target_active_similarity":
            return self.target_active_similarity(arguments)
        if name == "rank_pdb_ligand_similarity":
            return self.pdb_ligand_similarity(arguments)
        raise ValueError("unknown chemistry tool")

    def describe(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if set(arguments) != {"smiles"}:
            raise ValueError("describe_molecules accepts only smiles")
        values = _smiles(arguments.get("smiles"), "smiles")
        return {
            "method": "RDKit deterministic 2D descriptors",
            "results": [record.as_dict() for record in describe_many(values)],
        }

    def similarity(self, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed = {"query_smiles", "candidate_smiles", "radius", "n_bits"}
        if set(arguments) - allowed:
            raise ValueError("rank_molecular_similarity arguments are invalid")
        query = arguments.get("query_smiles")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query_smiles must be non-empty text")
        candidates = _smiles(arguments.get("candidate_smiles"), "candidate_smiles")
        radius = arguments.get("radius", 2)
        n_bits = arguments.get("n_bits", 2048)
        return {
            "method": "RDKit Morgan fingerprint with Tanimoto similarity",
            "radius": radius,
            "n_bits": n_bits,
            "results": [
                record.as_dict()
                for record in rank_similarity(
                    query, candidates, radius=radius, n_bits=n_bits
                )
            ],
        }

    def target_active_similarity(self, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed = {"target", "candidate_smiles", "max_unique_actives", "min_pchembl"}
        if set(arguments) - allowed:
            raise ValueError("rank_target_active_similarity arguments are invalid")
        target = arguments.get("target")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("target must be non-empty text")
        candidates = _smiles(arguments.get("candidate_smiles"), "candidate_smiles")
        return rank_candidates_against_target_actives(
            target,
            candidates,
            max_unique_actives=arguments.get("max_unique_actives", 1000),
            min_pchembl=arguments.get("min_pchembl", 6.0),
        )

    def pdb_ligand_similarity(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if set(arguments) != {"pdb_id", "candidate_smiles"}:
            raise ValueError("rank_pdb_ligand_similarity accepts pdb_id and candidate_smiles")
        pdb_id = arguments.get("pdb_id")
        if not isinstance(pdb_id, str) or not pdb_id.strip():
            raise ValueError("pdb_id must be non-empty text")
        candidates = _smiles(arguments.get("candidate_smiles"), "candidate_smiles")
        return rank_candidates_against_pdb_ligands(pdb_id, candidates)


def _smiles(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= 256:
        raise ValueError(f"{field} must contain 1 to 256 SMILES")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} entries must be non-empty text")
    return tuple(value)
