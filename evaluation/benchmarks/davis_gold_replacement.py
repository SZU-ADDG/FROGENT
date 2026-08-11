"""Build a transparent DAVIS-backed correction for one virtual-screening case."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path
from typing import Any

from rdkit import Chem


class DavisGoldSelectionError(ValueError):
    """Raised when the DAVIS-backed correction cannot be established uniquely."""


def _canonical(smiles: str, *, isomeric: bool) -> str:
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise DavisGoldSelectionError(f"RDKit could not parse SMILES: {smiles}")
    return Chem.MolToSmiles(
        molecule,
        canonical=True,
        isomericSmiles=isomeric,
    )


def _largest_organic_fragment(smiles: str) -> str:
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise DavisGoldSelectionError("RDKit could not parse the DAVIS gold molecule")
    fragments = Chem.GetMolFrags(molecule, asMols=True, sanitizeFrags=True)
    organic = [
        fragment
        for fragment in fragments
        if any(atom.GetAtomicNum() == 6 for atom in fragment.GetAtoms())
    ]
    candidates = organic or list(fragments)
    if not candidates:
        raise DavisGoldSelectionError("DAVIS gold molecule has no fragments")
    candidates.sort(
        key=lambda fragment: (
            -fragment.GetNumHeavyAtoms(),
            Chem.MolToSmiles(fragment, canonical=True, isomericSmiles=True),
        )
    )
    return Chem.MolToSmiles(
        candidates[0], canonical=True, isomericSmiles=True
    )


def _read_zip_csv(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    try:
        handle = archive.open(name)
    except KeyError as exc:
        raise DavisGoldSelectionError(f"DAVIS archive is missing {name}") from exc
    with handle, io.TextIOWrapper(handle, encoding="utf-8-sig", newline="") as text:
        return list(csv.DictReader(text))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def select_davis_gold_replacement(
    davis_zip: Path,
    virtual_screening_csv: Path,
    *,
    target_label: str = "JAK2(JH1domain-catalytic)",
    pdb_id: str = "2b7a",
) -> dict[str, Any]:
    """Return a DAVIS-grounded, stereochemistry-exact replacement cell."""

    davis_zip = davis_zip.resolve(strict=True)
    virtual_screening_csv = virtual_screening_csv.resolve(strict=True)

    with zipfile.ZipFile(davis_zip) as archive:
        drugs = _read_zip_csv(archive, "DAVIS/drugs.csv")
        proteins = _read_zip_csv(archive, "DAVIS/proteins.csv")
        affinities = _read_zip_csv(archive, "DAVIS/drug_protein_affinity.csv")

    target_rows = [row for row in proteins if row["Gene_Name"] == target_label]
    if len(target_rows) != 1:
        raise DavisGoldSelectionError(
            f"expected one exact DAVIS target {target_label!r}, got {len(target_rows)}"
        )
    target = target_rows[0]
    target_affinities = [
        row for row in affinities if row["Protein_Index"] == target["Protein_Index"]
    ]
    if not target_affinities:
        raise DavisGoldSelectionError("DAVIS target has no affinity records")
    target_affinities.sort(
        key=lambda row: (-float(row["Affinity"]), int(row["Drug_Index"]))
    )
    if len(target_affinities) < 2:
        raise DavisGoldSelectionError("DAVIS target needs at least two affinity records")
    top_affinity = float(target_affinities[0]["Affinity"])
    second_affinity = float(target_affinities[1]["Affinity"])
    if math.isclose(top_affinity, second_affinity, rel_tol=0.0, abs_tol=1e-12):
        raise DavisGoldSelectionError("DAVIS target does not have a unique top-affinity drug")

    drugs_by_index = {row["Drug_Index"]: row for row in drugs}
    gold_affinity = target_affinities[0]
    try:
        gold_drug = drugs_by_index[gold_affinity["Drug_Index"]]
    except KeyError as exc:
        raise DavisGoldSelectionError("DAVIS gold affinity has no drug record") from exc
    active_moiety = _largest_organic_fragment(gold_drug["Isomeric_SMILES"])

    with virtual_screening_csv.open(newline="", encoding="utf-8-sig") as handle:
        source_rows = list(csv.DictReader(handle))
    matching_cases = [
        (index, row)
        for index, row in enumerate(source_rows, start=1)
        if row["questions"] == target_label and row["pdb_id"].casefold() == pdb_id.casefold()
    ]
    if len(matching_cases) != 1:
        raise DavisGoldSelectionError(
            f"expected one source case for {target_label}/{pdb_id}, got {len(matching_cases)}"
        )
    row_index, source_case = matching_cases[0]
    candidates = ast.literal_eval(source_case["smiles"])
    if not isinstance(candidates, list) or len(candidates) != 11:
        raise DavisGoldSelectionError("source candidate pool must contain exactly 11 molecules")
    if not all(isinstance(candidate, str) and candidate for candidate in candidates):
        raise DavisGoldSelectionError("source candidate pool contains an invalid molecule")

    source_gold = _canonical(source_case["answer"], isomeric=True)
    if active_moiety != source_gold:
        raise DavisGoldSelectionError(
            "DAVIS top-affinity active moiety does not match the source gold"
        )
    exact_matches = [
        index
        for index, candidate in enumerate(candidates)
        if _canonical(candidate, isomeric=True) == source_gold
    ]
    source_connectivity = _canonical(source_gold, isomeric=False)
    connectivity_matches = [
        index
        for index, candidate in enumerate(candidates)
        if _canonical(candidate, isomeric=False) == source_connectivity
    ]
    if exact_matches:
        raise DavisGoldSelectionError("source case already contains the exact isomeric gold")
    if len(connectivity_matches) != 1:
        raise DavisGoldSelectionError(
            "source case must contain exactly one connectivity-only gold candidate"
        )

    replacement_index = connectivity_matches[0]
    corrected_candidates = list(candidates)
    corrected_candidates[replacement_index] = source_gold
    corrected_exact = [
        index
        for index, candidate in enumerate(corrected_candidates)
        if _canonical(candidate, isomeric=True) == source_gold
    ]
    if corrected_exact != [replacement_index]:
        raise DavisGoldSelectionError("corrected pool does not contain one unique exact gold")

    kd_nm = 10 ** (9 - top_affinity)
    return {
        "schema_version": "frogent-davis-gold-replacement-v1",
        "classification": "author-supplied_exposed-data_correction",
        "source_provenance": {
            "davis_zip_sha256": _sha256(davis_zip),
            "davis_files": [
                "DAVIS/drugs.csv",
                "DAVIS/proteins.csv",
                "DAVIS/drug_protein_affinity.csv",
            ],
            "virtual_screening_source_file": virtual_screening_csv.name,
        },
        "davis_target": {
            "protein_index": int(target["Protein_Index"]),
            "accession_number": target["Accession_Number"],
            "gene_name": target["Gene_Name"],
            "assayed_drugs": len(target_affinities),
        },
        "gold": {
            "drug_index": int(gold_drug["Drug_Index"]),
            "pubchem_cid": gold_drug["CID"],
            "affinity_field_interpretation": "pKd",
            "pkd": top_affinity,
            "kd_nm": kd_nm,
            "second_best_pkd": second_affinity,
            "unique_top_affinity": True,
            "davis_isomeric_smiles": gold_drug["Isomeric_SMILES"],
            "standardization": "largest_organic_fragment; preserve_stereochemistry",
            "active_moiety_smiles": active_moiety,
        },
        "original_case": {
            "row_index_1_based": row_index,
            "target_label": target_label,
            "pdb_id": source_case["pdb_id"],
            "candidate_count": len(candidates),
            "exact_isomeric_gold_present": False,
            "connectivity_only_match_indices_1_based": [
                index + 1 for index in connectivity_matches
            ],
            "answer": source_case["answer"],
        },
        "corrected_case": {
            "candidate_count": len(corrected_candidates),
            "replacement_index_1_based": replacement_index + 1,
            "replacement_rule": (
                "replace the sole connectivity-only candidate with the exact DAVIS "
                "isomeric active moiety"
            ),
            "candidates": corrected_candidates,
            "target_label": target_label,
            "pdb_id": source_case["pdb_id"],
            "answer": source_gold,
            "exact_isomeric_gold_count": len(corrected_exact),
        },
        "reporting": {
            "original_case_mutated": False,
            "original_attempted_denominator": 20,
            "original_exact_valid_denominator": 19,
            "corrected_cell_role": "separate_post-hoc_sensitivity_or_replacement_cell",
            "headline_score_reconstruction": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("davis_zip", type=Path)
    parser.add_argument("virtual_screening_csv", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = select_davis_gold_replacement(
        args.davis_zip,
        args.virtual_screening_csv,
    )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
