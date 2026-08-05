#!/usr/bin/env python3
"""Run the preregistered clean ten-model exposed eight-task panel."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = (
    ROOT
    / "runtime/evaluation/revision-20260805/clean-ten-model-panel-r01"
)
SOURCE_ROOT = (
    ROOT
    / "runtime/evaluation/revision-20260804/source-material/"
    "eight-task-benchmark-r01/extracted"
)
CODEX_EXECUTABLE = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
WRITE_LOCK = threading.Lock()

TASK_FILES = {
    "foundational_biomedical_knowledge": "test_data1.csv",
    "retrieve_known_drugs": "test_data2.csv",
    "retrieve_known_targets": "test_data3.csv",
    "molecular_property_prediction": "test_data4.csv",
    "virtual_screening": "test_data5.csv",
    "binding_mechanism": "test_data6.csv",
    "molecular_design": "test_data7",
    "retrosynthesis_planning": "test_data8.csv",
}


def _slug(model_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model_id.casefold()).strip("-")


def _read_csv(name: str) -> list[dict[str, str]]:
    with (SOURCE_ROOT / name).open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 20:
        raise ValueError(f"{name} must contain 20 cases")
    return rows


def _pdb_excerpt(path: Path, radius: float = 6.0) -> str:
    """Return non-water HETATM records plus nearby protein atoms."""

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    hetero: list[tuple[float, float, float]] = []
    kept_hetero: list[str] = []
    atom_rows: list[tuple[str, float, float, float]] = []
    for line in lines:
        if not line.startswith(("ATOM  ", "HETATM")) or len(line) < 54:
            continue
        try:
            xyz = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        except ValueError:
            continue
        if line.startswith("HETATM") and line[17:20].strip() not in {"HOH", "WAT"}:
            hetero.append(xyz)
            kept_hetero.append(line)
        elif line.startswith("ATOM  "):
            atom_rows.append((line, *xyz))
    if not hetero:
        return "\n".join(line for line in lines if line.startswith(("ATOM  ", "HETATM")))
    radius_sq = radius * radius
    nearby = [
        line
        for line, x, y, z in atom_rows
        if any((x - hx) ** 2 + (y - hy) ** 2 + (z - hz) ** 2 <= radius_sq
               for hx, hy, hz in hetero)
    ]
    return "\n".join(nearby + kept_hetero)


def _task_payload(task: str) -> tuple[str, list[dict[str, Any]]]:
    if task == "foundational_biomedical_knowledge":
        rows = _read_csv(TASK_FILES[task])
        cases = [
            {
                "case_index": int(row["index"]),
                "question": row["question"],
                "answer_type": row["answer_type"],
            }
            for row in rows
        ]
        instruction = (
            "Answer each biomedical-knowledge case independently. For multiple choice, return "
            "only the option label or slash-separated labels. For exact match, return the "
            "shortest exact answer."
        )
    elif task == "retrieve_known_drugs":
        rows = _read_csv(TASK_FILES[task])
        cases = [
            {"case_index": index, "protein": row["question"]}
            for index, row in enumerate(rows, 1)
        ]
        instruction = (
            "For each protein, return up to five known targeting drugs as DrugBank IDs and the "
            "corresponding canonical or isomeric SMILES when known. Use internal knowledge only."
        )
    elif task == "retrieve_known_targets":
        rows = _read_csv(TASK_FILES[task])
        cases = [
            {"case_index": index, "disease": row["question"]}
            for index, row in enumerate(rows, 1)
        ]
        instruction = (
            "For each disease, return the three most strongly associated human gene symbols. "
            "Use internal knowledge only."
        )
    elif task == "molecular_property_prediction":
        rows = _read_csv(TASK_FILES[task])
        cases = [
            {
                "case_index": index,
                "smiles": row["smiles"],
                "endpoints": row["question"].split(";"),
            }
            for index, row in enumerate(rows, 1)
        ]
        instruction = (
            "Predict QED in [0,1], Caco-2 permeability on the supplied dataset's log scale, and "
            "binary BBBP, CYP2D6-substrate and SR-p53 labels for each SMILES."
        )
    elif task == "virtual_screening":
        rows = _read_csv(TASK_FILES[task])
        cases = [
            {
                "case_index": index,
                "target": row["questions"],
                "pdb_id": row["pdb_id"],
                "candidate_smiles": ast.literal_eval(row["smiles"]),
            }
            for index, row in enumerate(rows, 1)
        ]
        instruction = (
            "Select exactly one candidate SMILES per case as the most likely highest-affinity "
            "ligand for the named target. Return the selected string exactly as supplied."
        )
    elif task == "binding_mechanism":
        rows = _read_csv(TASK_FILES[task])
        cases = []
        for index, row in enumerate(rows, 1):
            pdb_path = SOURCE_ROOT / "test_data6PDB" / f"{row['protein']}.pdb"
            cases.append({
                "case_index": index,
                "ligand_smiles": row["smiles"],
                "pdb_id": row["protein"],
                "interaction_fields": row["question"].split(";"),
                "pdb_binding_site_excerpt": _pdb_excerpt(pdb_path),
            })
        instruction = (
            "Inspect each supplied protein-ligand PDB binding-site excerpt and ligand SMILES. "
            "Return nonnegative integer counts for hydrophobic contacts, hydrogen bonds, "
            "pi-stacking, salt bridges and water bridges."
        )
    elif task == "molecular_design":
        paths = sorted((SOURCE_ROOT / TASK_FILES[task]).glob("*.pdb"))
        if len(paths) != 20:
            raise ValueError("molecular design requires 20 pocket PDB files")
        cases = [
            {
                "case_index": index,
                "pocket_id": path.stem,
                "pocket_pdb": path.read_text(encoding="utf-8", errors="replace"),
            }
            for index, path in enumerate(paths, 1)
        ]
        instruction = (
            "Generate exactly five distinct, neutral or reasonably ionized, synthetically "
            "plausible small-molecule SMILES for each protein pocket. Favor valid drug-like "
            "structures and avoid peroxides, unstable motifs and duplicate scaffolds."
        )
    elif task == "retrosynthesis_planning":
        rows = _read_csv(TASK_FILES[task])
        cases = [
            {"case_index": index, "target_smiles": row["smiles"]}
            for index, row in enumerate(rows, 1)
        ]
        instruction = (
            "Return one concise target-rooted retrosynthesis route per target. Encode steps as "
            "'reactant1.reactant2 -> product' and separate multiple steps with ' | '. Use valid "
            "SMILES and place the target product in the first step."
        )
    else:
        raise ValueError(f"unknown task: {task}")
    return instruction, cases


def _item_schema(task: str) -> dict[str, Any]:
    base = {"case_index": {"type": "integer", "minimum": 1, "maximum": 20}}
    if task == "foundational_biomedical_knowledge":
        properties = {**base, "answer": {"type": "string"}}
    elif task == "retrieve_known_drugs":
        properties = {
            **base,
            "drugbank_ids": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 5,
            },
            "smiles": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 5,
            },
        }
    elif task == "retrieve_known_targets":
        properties = {
            **base,
            "targets": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 3,
            },
        }
    elif task == "molecular_property_prediction":
        properties = {
            **base,
            "qed": {"type": "number"},
            "caco2": {"type": "number"},
            "bbbp": {"type": "integer", "enum": [0, 1]},
            "cyp2d6_sub": {"type": "integer", "enum": [0, 1]},
            "sr_p53": {"type": "integer", "enum": [0, 1]},
        }
    elif task == "virtual_screening":
        properties = {**base, "selected_smiles": {"type": "string"}}
    elif task == "binding_mechanism":
        count = {"type": "integer", "minimum": 0}
        properties = {
            **base,
            "hydrophobic_contacts": count,
            "hydrogen_bonds": count,
            "pi_stacking": count,
            "salt_bridges": count,
            "water_bridges": count,
        }
    elif task == "molecular_design":
        properties = {
            **base,
            "smiles": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 5,
                "maxItems": 5,
            },
        }
    elif task == "retrosynthesis_planning":
        properties = {**base, "route": {"type": "string"}}
    else:
        raise ValueError(f"unknown task: {task}")
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _schema(task: str, case_count: int = 20) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": _item_schema(task),
                "minItems": case_count,
                "maxItems": case_count,
            }
        },
        "required": ["results"],
        "additionalProperties": False,
    }


def _prompt(task: str, case_indices: set[int] | None = None) -> str:
    instruction, cases = _task_payload(task)
    if case_indices is not None:
        cases = [case for case in cases if int(case["case_index"]) in case_indices]
    payload = {"task": task, "instruction": instruction, "cases": cases}
    return (
        "Complete this benchmark cell independently. Do not use tools, web search, files, "
        "persistent memory, hidden answers or prior FROGENT instructions. Return exactly the "
        "JSON object required by the supplied schema. Preserve every case_index exactly.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


def _validate_result(
    task: str, value: Any, expected_indices: list[int] | None = None
) -> None:
    expected_indices = expected_indices or list(range(1, 21))
    if not isinstance(value, dict) or set(value) != {"results"}:
        raise ValueError("response must contain only results")
    results = value["results"]
    if not isinstance(results, list) or len(results) != len(expected_indices):
        raise ValueError(f"response must contain {len(expected_indices)} results")
    indices = [item.get("case_index") for item in results if isinstance(item, dict)]
    if sorted(indices) != sorted(expected_indices):
        raise ValueError(f"response case indices must be exactly {sorted(expected_indices)}")
    required = set(_item_schema(task)["required"])
    if any(not isinstance(item, dict) or set(item) != required for item in results):
        raise ValueError("response items do not match the frozen field set")


def _codex_call(model: dict[str, Any], task: str, prompt: str, schema: dict[str, Any],
                cell_root: Path) -> dict[str, Any]:
    schema_path = cell_root / "schema.json"
    last_path = cell_root / "last-message.json"
    events_path = cell_root / "events.jsonl"
    workdir = cell_root / "clean-workdir"
    workdir.mkdir(parents=True, exist_ok=False)
    subprocess.run(["git", "init", "--quiet", str(workdir)], check=True, capture_output=True)
    schema_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args = [
        str(CODEX_EXECUTABLE),
        "exec",
        "--model",
        model["model_id"],
        "-c",
        f'model_reasoning_effort="{model["reasoning_effort"]}"',
        "-c",
        'approval_policy="never"',
        "-c",
        "project_doc_max_bytes=0",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--strict-config",
        "--sandbox",
        "read-only",
        "--disable",
        "web_search",
        "--skip-git-repo-check",
        "--cd",
        str(workdir),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(last_path),
        "--json",
        "-",
    ]
    started = time.monotonic()
    completed = subprocess.run(
        args,
        input=prompt,
        text=True,
        capture_output=True,
        cwd=workdir,
        check=False,
    )
    wall = time.monotonic() - started
    events_path.write_text(completed.stdout, encoding="utf-8")
    (cell_root / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(
            f"Codex exit {completed.returncode}: {completed.stderr.strip()[-1200:]}"
        )
    value = json.loads(last_path.read_text(encoding="utf-8"))
    tool_events = [
        line
        for line in completed.stdout.splitlines()
        if any(token in line for token in ('"command_execution"', '"mcp_tool_call"', '"web_search"'))
    ]
    if tool_events:
        raise RuntimeError("Codex emitted a prohibited tool event")
    return {
        "response": value,
        "wall_seconds": wall,
        "transport_metadata": {
            "returncode": completed.returncode,
            "event_lines": len(completed.stdout.splitlines()),
            "prohibited_tool_events": 0,
        },
    }


def _openrouter_call(model: dict[str, Any], task: str, prompt: str, schema: dict[str, Any],
                     cell_root: Path) -> dict[str, Any]:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    provider = {
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
    }
    if model.get("provider_order"):
        provider["order"] = list(model["provider_order"])
    request_body = {
        "model": model["model_id"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": int(model.get("max_tokens", 12000)),
        "reasoning": model.get("reasoning", {"effort": "low"}),
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": f"frogent_{task}",
                "strict": True,
                "schema": schema,
            },
        },
        "provider": provider,
    }
    if model.get("include_seed", True):
        request_body["seed"] = 20260805
    (cell_root / "request.json").write_text(
        json.dumps(request_body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    request = urllib.request.Request(
        OPENROUTER_ENDPOINT,
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/FROGENT",
            "X-Title": "FROGENT clean ten-model benchmark",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=1800) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {body[-1600:]}") from exc
    wall = time.monotonic() - started
    (cell_root / "response.json").write_text(raw + ("" if raw.endswith("\n") else "\n"),
                                             encoding="utf-8")
    envelope = json.loads(raw)
    message = envelope["choices"][0]["message"]
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("OpenRouter response content is not a string")
    value = json.loads(content)
    return {
        "response": value,
        "wall_seconds": wall,
        "transport_metadata": {
            "response_id": envelope.get("id"),
            "returned_model": envelope.get("model"),
            "provider": envelope.get("provider"),
            "usage": envelope.get("usage"),
            "finish_reason": envelope["choices"][0].get("finish_reason"),
        },
    }


def _openrouter_batched_call(
    model: dict[str, Any], task: str, cell_root: Path
) -> dict[str, Any]:
    batch_size = int(model["batch_size"])
    if batch_size < 1 or batch_size > 20:
        raise ValueError("batch_size must be in 1..20")
    combined: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    wall_seconds = 0.0
    for start in range(1, 21, batch_size):
        indices = list(range(start, min(start + batch_size, 21)))
        batch_root = cell_root / f"batch-{indices[0]:02d}-{indices[-1]:02d}"
        batch_root.mkdir(parents=True, exist_ok=False)
        outcome = _openrouter_call(
            model,
            task,
            _prompt(task, set(indices)),
            _schema(task, len(indices)),
            batch_root,
        )
        _validate_result(task, outcome["response"], indices)
        combined.extend(outcome["response"]["results"])
        wall_seconds += float(outcome["wall_seconds"])
        metadata.append({
            "case_indices": indices,
            **outcome["transport_metadata"],
        })
    combined.sort(key=lambda item: int(item["case_index"]))
    return {
        "response": {"results": combined},
        "wall_seconds": wall_seconds,
        "transport_metadata": {
            "batch_size": batch_size,
            "batches": metadata,
        },
    }


def _codex_batched_call(
    model: dict[str, Any], task: str, cell_root: Path
) -> dict[str, Any]:
    batch_size = int(model["batch_size"])
    if batch_size < 1 or batch_size > 20:
        raise ValueError("batch_size must be in 1..20")
    combined: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    wall_seconds = 0.0
    for start in range(1, 21, batch_size):
        indices = list(range(start, min(start + batch_size, 21)))
        batch_root = cell_root / f"batch-{indices[0]:02d}-{indices[-1]:02d}"
        batch_root.mkdir(parents=True, exist_ok=False)
        outcome = _codex_call(
            model,
            task,
            _prompt(task, set(indices)),
            _schema(task, len(indices)),
            batch_root,
        )
        _validate_result(task, outcome["response"], indices)
        combined.extend(outcome["response"]["results"])
        wall_seconds += float(outcome["wall_seconds"])
        metadata.append({
            "case_indices": indices,
            **outcome["transport_metadata"],
        })
    combined.sort(key=lambda item: int(item["case_index"]))
    return {
        "response": {"results": combined},
        "wall_seconds": wall_seconds,
        "transport_metadata": {
            "batch_size": batch_size,
            "batches": metadata,
            "prohibited_tool_events": 0,
        },
    }


def _run_cell(run_root: Path, model: dict[str, Any], task: str) -> dict[str, Any]:
    model_slug = _slug(model["model_id"])
    cell_root = run_root / "raw" / model_slug / task
    terminal_path = cell_root / "terminal.json"
    with WRITE_LOCK:
        if terminal_path.exists():
            existing = json.loads(terminal_path.read_text(encoding="utf-8"))
            return {"model_id": model["model_id"], "task": task, "status": existing["status"],
                    "existing": True}
        cell_root.mkdir(parents=True, exist_ok=False)
    prompt = _prompt(task)
    schema = _schema(task)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    schema_hash = hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    record: dict[str, Any] = {
        "schema_version": "frogent-clean-model-cell-v1",
        "model_id": model["model_id"],
        "display_name": model["display_name"],
        "transport": model["transport"],
        "task": task,
        "prompt_sha256": prompt_hash,
        "schema_sha256": schema_hash,
        "status": "failed",
    }
    try:
        if model["transport"] == "codex" and model.get("batch_size"):
            outcome = _codex_batched_call(model, task, cell_root)
        elif model["transport"] == "codex":
            outcome = _codex_call(model, task, prompt, schema, cell_root)
        elif model.get("batch_size"):
            outcome = _openrouter_batched_call(model, task, cell_root)
        else:
            outcome = _openrouter_call(model, task, prompt, schema, cell_root)
        _validate_result(task, outcome["response"])
        record.update(outcome)
        record["status"] = "succeeded"
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    terminal_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"model_id": model["model_id"], "task": task, "status": record["status"],
            "existing": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="*", help="Exact model IDs; default is all frozen models")
    parser.add_argument("--tasks", nargs="*", choices=sorted(TASK_FILES),
                        help="Task names; default is all frozen tasks")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    try:
        run_root.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("run root must stay inside the FROGENT project") from exc
    protocol_path = run_root / "protocol/protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    models = protocol["models"]
    if args.models:
        requested = set(args.models)
        models = [model for model in models if model["model_id"] in requested]
        missing = requested - {model["model_id"] for model in models}
        if missing:
            raise ValueError(f"models are not in frozen protocol: {sorted(missing)}")
    tasks = args.tasks or protocol["tasks"]
    jobs = [(model, task) for model in models for task in tasks]
    if args.workers < 1 or args.workers > 10:
        raise ValueError("workers must be in 1..10")
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_run_cell, run_root, model, task): (model, task)
                   for model, task in jobs}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    failed = sum(result["status"] != "succeeded" for result in results)
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
