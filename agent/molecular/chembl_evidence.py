"""Target-aware known-active evidence from the official ChEMBL REST API."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from importlib import import_module
from typing import Any


BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
USER_AGENT = "FROGENT-target-evidence/1.0"
FetchJSON = Callable[[str], dict[str, Any]]


def fetch_json(url: str, attempts: int = 4) -> dict[str, Any]:
    """Fetch one official ChEMBL JSON resource with bounded transient retries."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.load(response)
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def normalize_target_query(target: str) -> str:
    """Remove mutation/domain annotations while retaining the target symbol."""
    value = re.sub(r"\([^)]*\)", "", target).strip()
    value = re.sub(r"-(?:phosphorylated|unphosphorylated)$", "", value, flags=re.I)
    if not value:
        raise ValueError("target must contain a resolvable name or symbol")
    return value


def _target_aliases(record: dict[str, Any]) -> set[str]:
    aliases = {str(record.get("pref_name") or "").casefold()}
    for component in record.get("target_components") or ():
        for synonym in component.get("target_component_synonyms") or ():
            aliases.add(str(synonym.get("component_synonym") or "").casefold())
    aliases.discard("")
    return aliases


def resolve_human_single_protein(
    target: str, *, fetcher: FetchJSON = fetch_json
) -> dict[str, Any]:
    query = normalize_target_query(target)
    url = f"{BASE_URL}/target/search.json?{urllib.parse.urlencode({'q': query, 'limit': 25})}"
    records = fetcher(url).get("targets") or []
    eligible = [
        record
        for record in records
        if record.get("organism") == "Homo sapiens"
        and record.get("target_type") == "SINGLE PROTEIN"
    ]
    if not eligible:
        raise ValueError(f"no human single-protein ChEMBL target resolved for {target!r}")
    folded = query.casefold()
    ranked = sorted(
        eligible,
        key=lambda record: (
            folded in _target_aliases(record),
            float(record.get("score") or 0.0),
            str(record.get("target_chembl_id") or ""),
        ),
        reverse=True,
    )
    selected = ranked[0]
    exact_alias = folded in _target_aliases(selected)
    if not exact_alias and len(ranked) > 1:
        first = float(ranked[0].get("score") or 0.0)
        second = float(ranked[1].get("score") or 0.0)
        if first <= second:
            raise ValueError(f"ambiguous ChEMBL target resolution for {target!r}")
    return {
        "input_target": target,
        "normalized_query": query,
        "target_chembl_id": selected["target_chembl_id"],
        "pref_name": selected.get("pref_name"),
        "organism": selected.get("organism"),
        "target_type": selected.get("target_type"),
        "exact_alias_match": exact_alias,
        "search_url": url,
    }


def collect_known_actives(
    target_chembl_id: str,
    *,
    max_unique: int = 1000,
    min_pchembl: float = 6.0,
    fetcher: FetchJSON = fetch_json,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chem = import_module("rdkit.Chem")
    if not 1 <= max_unique <= 5000:
        raise ValueError("max_unique must be between 1 and 5000")
    params = {
        "target_chembl_id": target_chembl_id,
        "standard_type": "IC50",
        "standard_units": "nM",
        "standard_relation": "=",
        "assay_type": "B",
        "standard_flag": 1,
        "pchembl_value__gte": min_pchembl,
        "limit": min(max_unique, 1000),
    }
    first_url = f"{BASE_URL}/activity.json?{urllib.parse.urlencode(params)}"
    url = first_url
    grouped: dict[str, dict[str, Any]] = {}
    raw_rows = 0
    excluded_rows = 0
    while url and len(grouped) < max_unique:
        payload = fetcher(url)
        activities = payload.get("activities") or []
        raw_rows += len(activities)
        for row in activities:
            if row.get("data_validity_comment") not in (None, ""):
                excluded_rows += 1
                continue
            if int(row.get("potential_duplicate") or 0):
                excluded_rows += 1
                continue
            molecule = chem.MolFromSmiles(str(row.get("canonical_smiles") or ""))
            if molecule is None:
                excluded_rows += 1
                continue
            canonical = chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
            current = grouped.get(canonical)
            pchembl = float(row["pchembl_value"])
            if current is None:
                grouped[canonical] = {
                    "canonical_smiles": canonical,
                    "molecule_chembl_ids": {str(row["molecule_chembl_id"])},
                    "max_pchembl": pchembl,
                    "activity_count": 1,
                }
            else:
                current["molecule_chembl_ids"].add(str(row["molecule_chembl_id"]))
                current["max_pchembl"] = max(float(current["max_pchembl"]), pchembl)
                current["activity_count"] += 1
            if len(grouped) >= max_unique:
                break
        next_url = (payload.get("page_meta") or {}).get("next")
        url = urllib.parse.urljoin(BASE_URL + "/", next_url) if next_url else ""
    records = []
    for canonical in sorted(grouped):
        record = grouped[canonical]
        record["molecule_chembl_ids"] = sorted(record["molecule_chembl_ids"])
        records.append(record)
    return records, {
        "query_url": first_url,
        "raw_activity_rows": raw_rows,
        "excluded_activity_rows": excluded_rows,
        "unique_known_actives": len(records),
        "min_pchembl": min_pchembl,
    }


def rank_candidates_against_target_actives(
    target: str,
    candidate_smiles: list[str] | tuple[str, ...],
    *,
    max_unique_actives: int = 1000,
    min_pchembl: float = 6.0,
    fetcher: FetchJSON = fetch_json,
) -> dict[str, Any]:
    chem = import_module("rdkit.Chem")
    data_structs = import_module("rdkit.DataStructs")
    fingerprint_module = import_module("rdkit.Chem.rdFingerprintGenerator")
    if not candidate_smiles:
        raise ValueError("candidate_smiles must not be empty")
    resolved = resolve_human_single_protein(target, fetcher=fetcher)
    actives, collection = collect_known_actives(
        resolved["target_chembl_id"],
        max_unique=max_unique_actives,
        min_pchembl=min_pchembl,
        fetcher=fetcher,
    )
    if not actives:
        raise ValueError(f"no qualifying ChEMBL actives found for {target!r}")
    generator = fingerprint_module.GetMorganGenerator(radius=2, fpSize=2048)
    active_fingerprints = [
        generator.GetFingerprint(chem.MolFromSmiles(record["canonical_smiles"]))
        for record in actives
    ]
    ranked = []
    for input_smiles in candidate_smiles:
        molecule = chem.MolFromSmiles(input_smiles)
        if molecule is None:
            raise ValueError(f"invalid candidate SMILES: {input_smiles}")
        canonical = chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
        fingerprint = generator.GetFingerprint(molecule)
        similarities = data_structs.BulkTanimotoSimilarity(fingerprint, active_fingerprints)
        order = sorted(range(len(similarities)), key=similarities.__getitem__, reverse=True)
        nearest = actives[order[0]]
        top_five = order[:5]
        ranked.append({
            "input_smiles": input_smiles,
            "canonical_smiles": canonical,
            "max_tanimoto": float(similarities[order[0]]),
            "mean_top5_tanimoto": float(
                sum(similarities[index] for index in top_five) / len(top_five)
            ),
            "nearest_active_smiles": nearest["canonical_smiles"],
            "nearest_active_chembl_ids": nearest["molecule_chembl_ids"],
            "nearest_active_max_pchembl": nearest["max_pchembl"],
        })
    ranked.sort(
        key=lambda row: (row["max_tanimoto"], row["mean_top5_tanimoto"]), reverse=True
    )
    return {
        "method": "ChEMBL curated human single-protein IC50 actives and RDKit Morgan-Tanimoto",
        "target": resolved,
        "active_collection": collection,
        "fingerprint": {"type": "Morgan", "radius": 2, "n_bits": 2048},
        "results": ranked,
    }
