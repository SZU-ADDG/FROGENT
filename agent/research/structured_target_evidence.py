"""Structured disease-target and protein-drug evidence from public providers."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any


OPEN_TARGETS_URL = "https://api.platform.opentargets.org/api/v4/graphql"
UNIPROT_URL = "https://rest.uniprot.org/uniprotkb/search"
USER_AGENT = "FROGENT-structured-retrieval/1.0"
FetchJSON = Callable[[str, dict[str, Any] | None], dict[str, Any]]


def fetch_json(url: str, payload: dict[str, Any] | None = None,
               attempts: int = 3) -> dict[str, Any]:
    """Fetch an official JSON resource with bounded transient retries."""
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = json.load(response)
            if not isinstance(body, dict):
                raise TypeError("provider response must be an object")
            return body
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def _graphql(query: str, variables: dict[str, Any], fetcher: FetchJSON) -> dict[str, Any]:
    body = fetcher(OPEN_TARGETS_URL, {"query": query, "variables": variables})
    if body.get("errors"):
        raise ValueError(f"Open Targets GraphQL errors: {body['errors']}")
    data = body.get("data")
    if not isinstance(data, dict):
        raise ValueError("Open Targets response has no data object")
    return data


def rank_disease_targets(disease: str, *, max_results: int = 10,
                         fetcher: FetchJSON = fetch_json) -> dict[str, Any]:
    """Resolve a disease and return provider-ranked associated human targets."""
    query = disease.strip()
    if not query:
        raise ValueError("disease must be non-empty text")
    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be between 1 and 100")
    search = _graphql(
        "query Search($q:String!){search(queryString:$q,entityNames:[\"disease\"],"
        "page:{index:0,size:10}){hits{id name entity}}}",
        {"q": query}, fetcher,
    ).get("search", {}).get("hits", [])
    diseases = [row for row in search if row.get("entity") == "disease"]
    if not diseases:
        raise ValueError(f"no Open Targets disease resolved for {disease!r}")
    exact = [row for row in diseases if str(row.get("name", "")).casefold() == query.casefold()]
    selected = (exact or diseases)[0]
    disease_id = str(selected["id"])
    data = _graphql(
        "query Targets($id:String!,$size:Int!){disease(efoId:$id){id name "
        "associatedTargets(page:{index:0,size:$size}){count rows{score target{id "
        "approvedSymbol approvedName}}}}}",
        {"id": disease_id, "size": max_results}, fetcher,
    ).get("disease")
    if not isinstance(data, dict):
        raise ValueError(f"Open Targets disease record absent for {disease_id}")
    rows = []
    for rank, item in enumerate(data.get("associatedTargets", {}).get("rows", []), 1):
        target = item.get("target") or {}
        symbol = str(target.get("approvedSymbol") or "").strip()
        identifier = str(target.get("id") or "").strip()
        score = item.get("score")
        if symbol and identifier and isinstance(score, (int, float)):
            rows.append({"rank": rank, "symbol": symbol,
                         "name": str(target.get("approvedName") or ""),
                         "ensembl_id": identifier, "association_score": float(score)})
    return {
        "method": "Open Targets Platform disease associatedTargets provider ranking",
        "input_disease": disease,
        "resolved_disease": {"id": data.get("id"), "name": data.get("name"),
                             "exact_name_match": bool(exact)},
        "association_count": data.get("associatedTargets", {}).get("count"),
        "results": rows,
        "provenance": {"provider": "Open Targets Platform", "endpoint": OPEN_TARGETS_URL},
        "interpretation": "Association scores rank aggregated evidence and are not causal confidence.",
    }


def _text_values(record: dict[str, Any]) -> set[str]:
    values = {str(record.get("uniProtkbId") or "").partition("_")[0].casefold()}
    description = record.get("proteinDescription") or {}
    names = [description.get("recommendedName"), *(description.get("alternativeNames") or [])]
    for item in names:
        value = ((item or {}).get("fullName") or {}).get("value")
        if value:
            values.add(str(value).casefold())
    for gene in record.get("genes") or []:
        for item in [gene.get("geneName"), *(gene.get("synonyms") or [])]:
            if (item or {}).get("value"):
                values.add(str(item["value"]).casefold())
    return values


def _property(item: dict[str, Any], key: str) -> str:
    for prop in item.get("properties") or []:
        if prop.get("key") == key:
            return str(prop.get("value") or "").strip()
    return ""


def list_target_drugbank_links(target: str, *, max_results: int = 100,
                               fetcher: FetchJSON = fetch_json) -> dict[str, Any]:
    """Resolve a reviewed human UniProt record and list its DrugBank cross-references."""
    query = re.sub(r"\([^)]*\)", "", target).strip()
    if not query:
        raise ValueError("target must be non-empty text")
    if not 1 <= max_results <= 250:
        raise ValueError("max_results must be between 1 and 250")
    params = {
        "query": f"({query}) AND (organism_id:9606) AND (reviewed:true)",
        "format": "json", "fields": "accession,id,protein_name,gene_names,xref_drugbank",
        "size": 10,
    }
    url = f"{UNIPROT_URL}?{urllib.parse.urlencode(params)}"
    records = fetcher(url, None).get("results") or []
    if not records:
        raise ValueError(f"no reviewed human UniProt target resolved for {target!r}")
    folded = query.casefold()
    exact = [record for record in records if folded in _text_values(record)]
    selected = (exact or records)[0]
    links = []
    for item in selected.get("uniProtKBCrossReferences") or []:
        identifier = str(item.get("id") or "").strip()
        if item.get("database") == "DrugBank" and re.fullmatch(r"DB\d{5}", identifier):
            links.append({"drugbank_id": identifier,
                          "name": _property(item, "GenericName")})
    return {
        "method": "reviewed human UniProtKB DrugBank cross-references",
        "input_target": target,
        "resolved_target": {
            "uniprot_accession": selected.get("primaryAccession"),
            "uniprot_id": selected.get("uniProtkbId"),
            "exact_alias_match": bool(exact),
        },
        "results": links[:max_results],
        "total_drugbank_links": len(links),
        "provenance": {"provider": "UniProtKB", "query_url": url},
        "interpretation": "Cross-references are provider annotations, not direct DrugBank execution.",
    }
