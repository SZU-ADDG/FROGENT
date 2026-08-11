#!/usr/bin/env python3
"""Measure generated-molecule distance to a versioned CrossDocked train split."""

from __future__ import annotations

import argparse
import csv
import json
import math
import multiprocessing as mp
import pickletools
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import lmdb
import torch
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem
from rdkit.Chem.Scaffolds import MurckoScaffold


TRAIN_FPS = []
TRAIN_ROWS = []
TRAIN_SCAFFOLDS = set()


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


def extract_smiles_without_unpickling(payload: bytes) -> str:
    markers = (b"\x8c\x06smiles", b"X\x06\x00\x00\x00smiles")
    offset = -1
    for marker in markers:
        offset = payload.find(marker)
        if offset >= 0:
            break
    if offset < 0:
        raise ValueError("smiles pickle opcode marker not found")
    saw_key = False
    for opcode, argument, _ in pickletools.genops(payload[offset:]):
        if opcode.name in {"SHORT_BINUNICODE", "BINUNICODE", "BINUNICODE8", "UNICODE"}:
            if not saw_key:
                if argument != "smiles":
                    raise ValueError("unexpected first unicode opcode after smiles marker")
                saw_key = True
            else:
                if not isinstance(argument, str) or not argument:
                    raise ValueError("empty ligand smiles")
                return argument
        elif saw_key and opcode.name not in {"MEMOIZE", "BINPUT", "LONG_BINPUT"}:
            raise ValueError(f"unexpected opcode before smiles value: {opcode.name}")
    raise ValueError("smiles value not found")


def canonicalize(smiles: str):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    canonical = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    scaffold = Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(mol), canonical=True)
    return canonical, scaffold, mol


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_train_collection(lmdb_path: Path, name2id_path: Path, split_path: Path):
    split = torch.load(split_path, map_location="cpu", weights_only=True)
    name2id = torch.load(name2id_path, map_location="cpu", weights_only=True)
    if not isinstance(split, dict) or "train" not in split:
        raise ValueError("split file has no train mapping")
    if not isinstance(name2id, dict):
        raise ValueError("name2id file is not a mapping")

    train_names = split["train"]
    mapped = []
    missing_names = []
    for name in train_names:
        key = tuple(name)
        if key in name2id:
            mapped.append((key, int(name2id[key])))
        else:
            missing_names.append(key)

    environment = lmdb.open(
        str(lmdb_path), subdir=False, readonly=True, lock=False,
        readahead=False, meminit=False, max_readers=512,
    )
    canonical_records = {}
    extraction_failures = []
    with environment.begin(buffers=False) as transaction:
        for name, index in mapped:
            payload = transaction.get(str(index).encode("utf-8"))
            if payload is None:
                extraction_failures.append({"index": index, "name": list(name), "error": "missing_lmdb_key"})
                continue
            try:
                source_smiles = extract_smiles_without_unpickling(payload)
                parsed = canonicalize(source_smiles)
                if parsed is None:
                    raise ValueError("RDKit parse failed")
                canonical, scaffold, mol = parsed
            except Exception as error:
                extraction_failures.append({"index": index, "name": list(name), "error": str(error)})
                continue
            record = canonical_records.get(canonical)
            if record is None:
                canonical_records[canonical] = {
                    "canonical_smiles": canonical,
                    "scaffold_smiles": scaffold,
                    "member_count": 1,
                    "example_lmdb_index": index,
                    "example_pocket_file": name[0],
                    "example_ligand_file": name[1],
                    "fingerprint": AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048),
                }
            else:
                record["member_count"] += 1
    environment.close()
    records = [canonical_records[key] for key in sorted(canonical_records)]
    metadata = {
        "split_keys": sorted(split),
        "split_counts": {key: len(value) for key, value in split.items()},
        "name2id_count": len(name2id),
        "train_names_declared": len(train_names),
        "train_names_mapped": len(mapped),
        "declared_name_coverage": len(mapped) / len(train_names),
        "train_names_missing": len(missing_names),
        "train_members_extracted": sum(row["member_count"] for row in records),
        "unique_canonical_train_molecules": len(records),
        "extraction_failures": len(extraction_failures),
        "missing_name_examples": [list(value) for value in missing_names[:20]],
        "extraction_failure_examples": extraction_failures[:20],
    }
    return records, metadata


def init_worker(train_rows):
    global TRAIN_ROWS, TRAIN_FPS, TRAIN_SCAFFOLDS
    TRAIN_ROWS = train_rows
    TRAIN_FPS = [row["fingerprint"] for row in train_rows]
    TRAIN_SCAFFOLDS = {row["scaffold_smiles"] for row in train_rows if row["scaffold_smiles"]}


def nearest_worker(item):
    canonical, scaffold = item
    mol = Chem.MolFromSmiles(canonical)
    fingerprint = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
    similarities = DataStructs.BulkTanimotoSimilarity(fingerprint, TRAIN_FPS)
    best_index = max(range(len(similarities)), key=similarities.__getitem__)
    best = TRAIN_ROWS[best_index]
    return canonical, {
        "nearest_train_tanimoto": similarities[best_index],
        "nearest_train_smiles": best["canonical_smiles"],
        "nearest_train_example_lmdb_index": best["example_lmdb_index"],
        "exact_train_identity": canonical == best["canonical_smiles"],
        "train_scaffold_match": bool(scaffold and scaffold in TRAIN_SCAFFOLDS),
    }


def summarize(rows: list[dict], group_fields: list[str]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in group_fields)].append(row)
    output = []
    for key, members in sorted(groups.items()):
        values = [float(row["nearest_train_tanimoto"]) for row in members]
        result = {field: value for field, value in zip(group_fields, key)}
        result.update({
            "n": len(members),
            "mean_nearest_train_tanimoto": sum(values) / len(values),
            "median_nearest_train_tanimoto": percentile(values, 0.5),
            "p90_nearest_train_tanimoto": percentile(values, 0.9),
            "max_nearest_train_tanimoto": max(values),
            "rate_tanimoto_ge_0_5": sum(value >= 0.5 for value in values) / len(values),
            "rate_tanimoto_ge_0_7": sum(value >= 0.7 for value in values) / len(values),
            "rate_tanimoto_ge_0_8": sum(value >= 0.8 for value in values) / len(values),
            "exact_train_identity_rate": sum(
                value if isinstance(value, bool) else str(value).lower() == "true"
                for value in (row["exact_train_identity"] for row in members)
            ) / len(members),
            "train_scaffold_match_rate": sum(
                value if isinstance(value, bool) else str(value).lower() == "true"
                for value in (row["train_scaffold_match"] for row in members)
            ) / len(members),
        })
        output.append(result)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-csv", required=True, type=Path)
    parser.add_argument("--lmdb", required=True, type=Path)
    parser.add_argument("--name2id", required=True, type=Path)
    parser.add_argument("--split", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "preregistration.json").write_text(args.preregistration.read_text())

    train_rows, train_metadata = load_train_collection(args.lmdb, args.name2id, args.split)
    collection_fields = [
        "canonical_smiles", "scaffold_smiles", "member_count", "example_lmdb_index",
        "example_pocket_file", "example_ligand_file",
    ]
    write_csv(args.output_dir / "training-proxy-collection.csv", train_rows, collection_fields)

    generated_rows = []
    unique_generated = {}
    with args.generated_csv.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["parse_success"].lower() != "true":
                continue
            parsed = canonicalize(row["canonical_smiles"])
            if parsed is None:
                raise ValueError(f"generated canonical SMILES failed to parse: {row['canonical_smiles']}")
            canonical, scaffold, _ = parsed
            row["canonical_smiles"] = canonical
            generated_rows.append(row)
            unique_generated[canonical] = scaffold

    context = mp.get_context("fork")
    with context.Pool(args.workers, initializer=init_worker, initargs=(train_rows,)) as pool:
        nearest_pairs = pool.map(nearest_worker, sorted(unique_generated.items()), chunksize=16)
    nearest = dict(nearest_pairs)

    output_rows = []
    for row in generated_rows:
        output_rows.append({
            "model": row["model"], "pocket": row["pocket"].upper(), "seed": row["seed"],
            "job_tag": row["job_tag"], "sample_file": row["sample_file"],
            "canonical_smiles": row["canonical_smiles"], **nearest[row["canonical_smiles"]],
        })
    neighbor_fields = [
        "model", "pocket", "seed", "job_tag", "sample_file", "canonical_smiles",
        "nearest_train_tanimoto", "nearest_train_smiles", "nearest_train_example_lmdb_index",
        "exact_train_identity", "train_scaffold_match",
    ]
    write_csv(args.output_dir / "molecule-training-neighbors.csv", output_rows, neighbor_fields)
    pocket_summary = summarize(output_rows, ["model", "pocket"])
    write_csv(args.output_dir / "model-pocket-summary.csv", pocket_summary, list(pocket_summary[0]))
    model_summary = summarize(output_rows, ["model"])

    created_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "schema_version": "frogent-cbgbench-crossdocked-training-proxy-summary-v1",
        "created_at": created_at,
        "training_proxy_metadata": train_metadata,
        "generated_rows_analyzed": len(output_rows),
        "generated_unique_canonical_smiles": len(unique_generated),
        "model_summaries": model_summary,
        "scope": {
            "supports": "distance to the exact versioned public CrossDocked train split declared by CBGBench configs",
            "does_not_measure": "exact checkpoint training-file membership or any undisclosed pretraining and fine-tuning corpora",
        },
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    manifest = {
        "schema_version": "frogent-cbgbench-crossdocked-training-proxy-manifest-v1",
        "created_at": created_at,
        "status": "complete",
        "generated_rows_expected": 9767,
        "generated_rows_analyzed": len(output_rows),
        "train_names_declared": train_metadata["train_names_declared"],
        "train_names_mapped": train_metadata["train_names_mapped"],
        "train_names_unmapped": train_metadata["train_names_missing"],
        "declared_name_coverage": train_metadata["declared_name_coverage"],
        "train_members_extracted": train_metadata["train_members_extracted"],
        "training_extraction_failures": train_metadata["extraction_failures"],
        "outputs": [
            "preregistration.json", "training-proxy-collection.csv",
            "molecule-training-neighbors.csv", "model-pocket-summary.csv", "summary.json",
        ],
    }
    if (
        len(output_rows) != 9767
        or train_metadata["extraction_failures"]
        or train_metadata["train_names_mapped"] != train_metadata["train_members_extracted"]
    ):
        manifest["status"] = "incomplete"
    (args.output_dir / "final-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if manifest["status"] != "complete":
        raise RuntimeError("analysis did not meet frozen completeness criteria")


if __name__ == "__main__":
    main()
