#!/usr/bin/env python3
"""Build a frozen, gold-blind tool-evidence cache for the paired model panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski, QED, rdMolDescriptors

from run_clean_ten_model_panel import ROOT, SOURCE_ROOT, TASK_FILES, _task_payload

PROPERTY_SOURCE = (
    ROOT
    / "runtime/evaluation/revision-20260804/"
    "eight-task-property-exposed-r01/output/per-case.json"
)
RETRO_SOURCE = (
    ROOT
    / "runtime/evaluation/revision-20260804/"
    "eight-task-retrosynthesis-exposed-r01/raw"
)
PLIP = ROOT / "runtime/app/venv/bin/plip"
DEFAULT_ROOT = (
    ROOT
    / "runtime/evaluation/revision-20260805/"
    "paired-twelve-model-frogent-r20/evidence"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _descriptor(smiles: str) -> dict[str, Any]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"smiles": smiles, "parseable": False}
    return {
        "smiles": smiles,
        "parseable": True,
        "qed": QED.qed(mol),
        "mw": Descriptors.MolWt(mol),
        "logp": Crippen.MolLogP(mol),
        "tpsa": rdMolDescriptors.CalcTPSA(mol),
        "hbd": Lipinski.NumHDonors(mol),
        "hba": Lipinski.NumHAcceptors(mol),
        "rotatable_bonds": Lipinski.NumRotatableBonds(mol),
    }


def _europe_pmc(query: str) -> dict[str, Any]:
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode({
        "query": query,
        "format": "json",
        "pageSize": 3,
        "resultType": "core",
    })
    request = urllib.request.Request(url, headers={"User-Agent": "FROGENT/paired-panel"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
        rows = body.get("resultList", {}).get("result", [])
        records = [
            {
                "title": row.get("title", ""),
                "abstract": row.get("abstractText", "")[:1800],
                "pmid": row.get("pmid", ""),
                "doi": row.get("doi", ""),
            }
            for row in rows[:3]
        ]
        return {"query": query, "records": records, "error": ""}
    except Exception as exc:
        return {"query": query, "records": [], "error": f"{type(exc).__name__}: {exc}"}


def _retrieval_queries() -> dict[str, list[str]]:
    _, foundational = _task_payload("foundational_biomedical_knowledge")
    _, drugs = _task_payload("retrieve_known_drugs")
    _, targets = _task_payload("retrieve_known_targets")
    return {
        "foundational_biomedical_knowledge": [
            re.sub(r"\s+", " ", case["question"]).strip()[:420] for case in foundational
        ],
        "retrieve_known_drugs": [
            f"{case['protein']} inhibitor drug target" for case in drugs
        ],
        "retrieve_known_targets": [
            f"{case['disease']} therapeutic target gene" for case in targets
        ],
    }


def _build_retrieval() -> dict[str, list[dict[str, Any]]]:
    queries = _retrieval_queries()
    output: dict[str, list[dict[str, Any]]] = {
        task: [{} for _ in task_queries] for task, task_queries in queries.items()
    }
    futures = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for task, task_queries in queries.items():
            for index, query in enumerate(task_queries):
                futures[pool.submit(_europe_pmc, query)] = (task, index)
        for future in as_completed(futures):
            task, index = futures[future]
            output[task][index] = {
                "case_index": index + 1,
                "europe_pmc": future.result(),
            }
    return output


def _build_property() -> list[dict[str, Any]]:
    source = json.loads(PROPERTY_SOURCE.read_text(encoding="utf-8"))
    _, cases = _task_payload("molecular_property_prediction")
    by_index = {int(row["row_index"]): row["prediction"] for row in source}
    return [
        {
            "case_index": int(case["case_index"]),
            "admet_ai_2_0_1": by_index[int(case["case_index"])],
            "rdkit": _descriptor(case["smiles"]),
        }
        for case in cases
    ]


def _build_screening() -> list[dict[str, Any]]:
    _, cases = _task_payload("virtual_screening")
    return [
        {
            "case_index": int(case["case_index"]),
            "candidate_rdkit_descriptors": [
                _descriptor(smiles) for smiles in case["candidate_smiles"]
            ],
            "limitation": "Descriptors are triage signals, not docking affinity.",
        }
        for case in cases
    ]


def _plip_counts(pdb_path: Path, output_root: Path) -> dict[str, Any]:
    case_root = output_root / pdb_path.stem
    case_root.mkdir(parents=True, exist_ok=False)
    completed = subprocess.run(
        [
            str(PLIP), "-f", str(pdb_path), "-o", str(case_root),
            "-x", "-q", "--nofixfile", "--maxthreads", "1",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    reports = sorted(case_root.glob("*_report.xml"))
    if completed.returncode != 0 or not reports:
        return {
            "tool": "PLIP 3.0.0",
            "error": completed.stderr[-1000:],
            "exit_code": completed.returncode,
        }
    root = ET.parse(reports[0]).getroot()
    tags = {
        "hydrophobic_contacts": "hydrophobic_interaction",
        "hydrogen_bonds": "hydrogen_bond",
        "pi_stacking": "pi_stack",
        "salt_bridges": "salt_bridge",
        "water_bridges": "water_bridge",
    }
    return {
        "tool": "PLIP 3.0.0",
        "counts": {name: len(root.findall(f".//{tag}")) for name, tag in tags.items()},
        "report_sha256": _sha256(reports[0]),
        "exit_code": completed.returncode,
        "error": "",
    }


def _build_binding(output_root: Path) -> list[dict[str, Any]]:
    _, cases = _task_payload("binding_mechanism")
    rows = []
    for case in cases:
        pdb_path = SOURCE_ROOT / "test_data6PDB" / f"{case['pdb_id']}.pdb"
        rows.append({
            "case_index": int(case["case_index"]),
            "pdb_id": case["pdb_id"],
            "plip": _plip_counts(pdb_path, output_root),
        })
    return rows


def _pocket_summary(path: Path) -> dict[str, Any]:
    residues: set[tuple[str, str, str]] = set()
    atom_count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("ATOM  "):
            continue
        atom_count += 1
        residues.add((line[21:22].strip(), line[22:26].strip(), line[17:20].strip()))
    names: dict[str, int] = {}
    for _, _, name in residues:
        names[name] = names.get(name, 0) + 1
    return {
        "protein_atom_count": atom_count,
        "residue_count": len(residues),
        "residue_composition": dict(sorted(names.items())),
    }


def _build_design() -> list[dict[str, Any]]:
    paths = sorted((SOURCE_ROOT / TASK_FILES["molecular_design"]).glob("*.pdb"))
    return [
        {"case_index": index, "pocket_id": path.stem, "pocket_summary": _pocket_summary(path)}
        for index, path in enumerate(paths, 1)
    ]


def _retro_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(r'"text":"(.*?)"}', text)
    if not matches:
        return text[-6000:]
    return bytes(matches[-1], "utf-8").decode("unicode_escape")[:6000]


def _build_retro() -> list[dict[str, Any]]:
    rows = []
    for index in range(1, 21):
        case_root = RETRO_SOURCE / f"case-{index:02d}"
        rows.append({
            "case_index": index,
            "directmultistep_flash": _retro_text(case_root / "generate_routes_flash.sse"),
            "directmultistep_explorer": _retro_text(case_root / "generate_routes_explorer.sse"),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.output_root.resolve()
    root.relative_to(ROOT.resolve())
    if root.exists():
        raise FileExistsError(f"evidence root already exists: {root}")
    root.mkdir(parents=True)
    retrieval = _build_retrieval()
    evidence = {
        **retrieval,
        "molecular_property_prediction": _build_property(),
        "virtual_screening": _build_screening(),
        "binding_mechanism": _build_binding(root / "plip"),
        "molecular_design": _build_design(),
        "retrosynthesis_planning": _build_retro(),
    }
    for task, rows in evidence.items():
        path = root / f"{task}.json"
        path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    manifest = {
        "schema_version": "frogent-paired-tool-evidence-v1",
        "gold_visibility": "withheld",
        "tasks": {
            task: {"cases": len(rows), "sha256": _sha256(root / f"{task}.json")}
            for task, rows in evidence.items()
        },
        "tools": {
            "literature": "Europe PMC REST",
            "properties": "ADMET-AI 2.0.1 plus RDKit",
            "interaction": "PLIP 3.0.0",
            "screening": "RDKit descriptors",
            "pocket": "deterministic PDB residue summarizer",
            "retrosynthesis": "DirectMultiStep flash and explorer",
        },
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
