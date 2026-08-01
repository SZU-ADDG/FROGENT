#!/usr/bin/env python3
"""Compare generated CBGBench molecules with versioned ChEMBL known actives."""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem
from rdkit.Chem.Scaffolds import MurckoScaffold


BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
TARGETS = {
    "ABL1": {"chembl_id": "CHEMBL1862", "uniprot": "P00519"},
    "EGFR": {"chembl_id": "CHEMBL203", "uniprot": "P00533"},
}
POCKET_TARGET = {
    "1IEP": "ABL1",
    "2HYY": "ABL1",
    "3CS9": "ABL1",
    "4WA9": "ABL1",
    "1M17": "EGFR",
}
FIELDS = [
    "activity_id",
    "assay_chembl_id",
    "assay_type",
    "canonical_smiles",
    "molecule_chembl_id",
    "pchembl_value",
    "standard_relation",
    "standard_type",
    "standard_units",
    "standard_value",
    "target_chembl_id",
]


def fetch_json(url: str, attempts: int = 5) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "FROGENT-revision-evaluation/1.0"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.load(response)
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def canonicalize(smiles: str) -> tuple[str, Chem.Mol] | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True), mol


def collect_target(target_name: str, output: Path) -> tuple[list[dict], dict]:
    target = TARGETS[target_name]
    params = {
        "target_chembl_id": target["chembl_id"],
        "standard_type": "IC50",
        "standard_units": "nM",
        "standard_relation": "=",
        "assay_type": "B",
        "standard_flag": 1,
        "pchembl_value__gte": 6,
        "limit": 1000,
    }
    url = f"{BASE_URL}/activity.json?{urllib.parse.urlencode(params)}"
    raw_rows: list[dict] = []
    pages: list[dict] = []
    while url:
        payload = fetch_json(url)
        activities = payload.get("activities", [])
        raw_rows.extend(activities)
        page_meta = payload["page_meta"]
        pages.append({
            "offset": page_meta.get("offset"),
            "returned": len(activities),
            "total_count": page_meta.get("total_count"),
        })
        next_url = page_meta.get("next")
        url = urllib.parse.urljoin(BASE_URL + "/", next_url) if next_url else ""

    raw_path = output / f"chembl-{target_name.lower()}-activity-rows.jsonl"
    with raw_path.open("w") as handle:
        for row in raw_rows:
            handle.write(json.dumps({key: row.get(key) for key in FIELDS}, sort_keys=True) + "\n")

    grouped: dict[str, dict] = {}
    invalid = 0
    for row in raw_rows:
        parsed = canonicalize(row.get("canonical_smiles") or "")
        if parsed is None:
            invalid += 1
            continue
        canonical, mol = parsed
        pchembl = float(row["pchembl_value"])
        current = grouped.get(canonical)
        if current is None:
            grouped[canonical] = {
                "target_name": target_name,
                "target_chembl_id": target["chembl_id"],
                "uniprot": target["uniprot"],
                "canonical_smiles": canonical,
                "scaffold_smiles": Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(mol), canonical=True),
                "max_pchembl_value": pchembl,
                "activity_count": 1,
                "molecule_chembl_ids": {row["molecule_chembl_id"]},
            }
        else:
            current["max_pchembl_value"] = max(current["max_pchembl_value"], pchembl)
            current["activity_count"] += 1
            current["molecule_chembl_ids"].add(row["molecule_chembl_id"])

    records = []
    for canonical in sorted(grouped):
        row = grouped[canonical]
        row["molecule_chembl_ids"] = ";".join(sorted(row["molecule_chembl_ids"]))
        records.append(row)
    meta = {
        "target_name": target_name,
        "target_chembl_id": target["chembl_id"],
        "uniprot": target["uniprot"],
        "query_parameters": params,
        "raw_activity_rows": len(raw_rows),
        "invalid_smiles_rows": invalid,
        "unique_canonical_actives": len(records),
        "pages": pages,
    }
    return records, meta


def summarize(rows: list[dict], group_fields: list[str]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in group_fields)].append(row)
    output = []
    for key, members in sorted(groups.items()):
        similarities = [float(row["nearest_active_tanimoto"]) for row in members]
        scaffold_hits = [
            value if isinstance(value, bool) else str(value).lower() == "true"
            for value in (row["active_scaffold_match"] for row in members)
        ]
        summary = {field: value for field, value in zip(group_fields, key)}
        summary.update({
            "n": len(members),
            "mean_nearest_active_tanimoto": sum(similarities) / len(similarities),
            "median_nearest_active_tanimoto": percentile(similarities, 0.5),
            "p90_nearest_active_tanimoto": percentile(similarities, 0.9),
            "max_nearest_active_tanimoto": max(similarities),
            "rate_tanimoto_ge_0_5": sum(value >= 0.5 for value in similarities) / len(similarities),
            "rate_tanimoto_ge_0_7": sum(value >= 0.7 for value in similarities) / len(similarities),
            "rate_tanimoto_ge_0_8": sum(value >= 0.8 for value in similarities) / len(similarities),
            "active_scaffold_match_rate": sum(scaffold_hits) / len(scaffold_hits),
        })
        output.append(summary)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    status = fetch_json(f"{BASE_URL}/status.json")
    (args.output_dir / "chembl-status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    (args.output_dir / "preregistration.json").write_text(args.preregistration.read_text())

    active_records: list[dict] = []
    collection_meta: list[dict] = []
    for target_name in TARGETS:
        records, meta = collect_target(target_name, args.output_dir)
        active_records.extend(records)
        collection_meta.append(meta)
    active_fields = [
        "target_name", "target_chembl_id", "uniprot", "canonical_smiles",
        "scaffold_smiles", "max_pchembl_value", "activity_count", "molecule_chembl_ids",
    ]
    write_csv(args.output_dir / "known-active-collection.csv", active_records, active_fields)

    by_target: dict[str, list[dict]] = defaultdict(list)
    for row in active_records:
        mol = Chem.MolFromSmiles(row["canonical_smiles"])
        row["fingerprint"] = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
        by_target[row["target_name"]].append(row)

    generated_rows = []
    with args.input_csv.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["parse_success"].lower() == "true":
                generated_rows.append(row)

    cache: dict[tuple[str, str], dict] = {}
    output_rows: list[dict] = []
    for row in generated_rows:
        target_name = POCKET_TARGET[row["pocket"].upper()]
        canonical = row["canonical_smiles"]
        cache_key = (target_name, canonical)
        nearest = cache.get(cache_key)
        if nearest is None:
            mol = Chem.MolFromSmiles(canonical)
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
            actives = by_target[target_name]
            similarities = DataStructs.BulkTanimotoSimilarity(fp, [active["fingerprint"] for active in actives])
            best_index = max(range(len(similarities)), key=similarities.__getitem__)
            best = actives[best_index]
            scaffold = Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(mol), canonical=True)
            active_scaffolds = {active["scaffold_smiles"] for active in actives if active["scaffold_smiles"]}
            nearest = {
                "target_name": target_name,
                "target_chembl_id": TARGETS[target_name]["chembl_id"],
                "nearest_active_tanimoto": similarities[best_index],
                "nearest_active_smiles": best["canonical_smiles"],
                "nearest_active_molecule_chembl_ids": best["molecule_chembl_ids"],
                "nearest_active_max_pchembl_value": best["max_pchembl_value"],
                "active_scaffold_match": bool(scaffold and scaffold in active_scaffolds),
            }
            cache[cache_key] = nearest
        output_rows.append({
            "model": row["model"],
            "pocket": row["pocket"].upper(),
            "seed": row["seed"],
            "job_tag": row["job_tag"],
            "sample_file": row["sample_file"],
            "canonical_smiles": canonical,
            **nearest,
        })

    neighbor_fields = [
        "model", "pocket", "seed", "job_tag", "sample_file", "canonical_smiles",
        "target_name", "target_chembl_id", "nearest_active_tanimoto",
        "nearest_active_smiles", "nearest_active_molecule_chembl_ids",
        "nearest_active_max_pchembl_value", "active_scaffold_match",
    ]
    write_csv(args.output_dir / "molecule-neighbors.csv", output_rows, neighbor_fields)
    summaries = summarize(output_rows, ["model", "pocket", "target_name"])
    summary_fields = list(summaries[0])
    write_csv(args.output_dir / "model-pocket-summary.csv", summaries, summary_fields)
    model_summaries = summarize(output_rows, ["model"])

    summary = {
        "schema_version": "frogent-cbgbench-known-active-neighbors-summary-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chembl_status": status,
        "collection_metadata": collection_meta,
        "generated_parsed_rows": len(output_rows),
        "generated_unique_target_smiles": len(cache),
        "model_summaries": model_summaries,
        "scope": {
            "supports": "distance from a versioned ChEMBL known-active collection under the preregistered filters",
            "does_not_measure": "distance from the generator training set or exhaustiveness across all known-active databases and assay types",
        },
    }
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    manifest = {
        "schema_version": "frogent-cbgbench-known-active-neighbors-manifest-v1",
        "created_at": summary["created_at"],
        "status": "complete",
        "input_csv": str(args.input_csv),
        "generated_rows_expected": 9767,
        "generated_rows_analyzed": len(output_rows),
        "collection_targets_expected": 2,
        "collection_targets_completed": len(collection_meta),
        "chembl_db_version": status.get("chembl_db_version"),
        "outputs": [
            "chembl-status.json", "known-active-collection.csv", "molecule-neighbors.csv",
            "model-pocket-summary.csv", "summary.json", "preregistration.json",
            "chembl-abl1-activity-rows.jsonl", "chembl-egfr-activity-rows.jsonl",
        ],
    }
    if len(output_rows) != manifest["generated_rows_expected"]:
        manifest["status"] = "incomplete"
        raise RuntimeError(f"expected 9767 parsed rows, observed {len(output_rows)}")
    (args.output_dir / "final-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
