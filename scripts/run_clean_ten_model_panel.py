#!/usr/bin/env python3
"""Run the preregistered clean ten-model exposed eight-task panel."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import random
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


def _task_payload(
    task: str, *, allow_public_web: bool = False
) -> tuple[str, list[dict[str, Any]]]:
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
            "corresponding canonical or isomeric SMILES when known. "
            + (
                "You may verify candidates with general public web search."
                if allow_public_web
                else "Use internal knowledge only."
            )
        )
    elif task == "retrieve_known_targets":
        rows = _read_csv(TASK_FILES[task])
        cases = [
            {"case_index": index, "disease": row["question"]}
            for index, row in enumerate(rows, 1)
        ]
        instruction = (
            "For each disease, return the three most strongly associated human gene symbols. "
            + (
                "You may verify candidates with general public web search."
                if allow_public_web
                else "Use internal knowledge only."
            )
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


def _prompt(
    task: str,
    case_indices: set[int] | None = None,
    *,
    allow_public_web: bool = False,
    case_order_seed: int | None = None,
) -> str:
    instruction, cases = _task_payload(task, allow_public_web=allow_public_web)
    if case_indices is not None:
        cases = [case for case in cases if int(case["case_index"]) in case_indices]
    if case_order_seed is not None:
        task_offset = int(hashlib.sha256(task.encode("utf-8")).hexdigest()[:8], 16)
        random.Random(case_order_seed + task_offset).shuffle(cases)
    payload = {"task": task, "instruction": instruction, "cases": cases}
    resource_contract = (
        "General public live web search is available and may be used. Do not use local files, "
        "shell, MCP, skills, plugins, persistent memory, prior benchmark outputs, hidden "
        "answers, FROGENT initialization, or FROGENT/user tools."
        if allow_public_web
        else "Do not use tools, web search, files, persistent memory, hidden answers or prior "
        "FROGENT instructions."
    )
    return (
        "Complete this benchmark cell independently. " + resource_contract + " Return exactly the "
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


def _json_candidates(content: str) -> list[Any]:
    """Decode every complete JSON value without trusting provider prose/fence order."""
    candidates: list[Any] = []
    stripped = content.strip()
    try:
        candidates.append(json.loads(stripped))
    except json.JSONDecodeError:
        pass
    for match in re.finditer(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL | re.I):
        try:
            candidates.append(json.loads(match.group(1).strip()))
        except json.JSONDecodeError:
            continue
    decoder = json.JSONDecoder()
    for position, character in enumerate(content):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(content[position:])
        except json.JSONDecodeError:
            continue
        candidates.append(value)
    return candidates


def _normalized_item(task: str, item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    case_index = item.get("case_index", item.get("caseIndex"))
    try:
        case_index = int(case_index)
    except (TypeError, ValueError):
        return None
    out: dict[str, Any] = {"case_index": case_index}
    if task == "molecular_property_prediction":
        aliases = {
            "qed": ("qed", "QED"),
            "caco2": ("caco2", "Caco-2 Permeability", "caco_2"),
            "bbbp": ("bbbp", "BBBP"),
            "cyp2d6_sub": ("cyp2d6_sub", "CYP2D6-sub", "CYP2D6_sub"),
            "sr_p53": ("sr_p53", "SR-p53", "SR_p53"),
        }
        for target, names in aliases.items():
            value = next((item[name] for name in names if name in item), None)
            if value is None:
                return None
            out[target] = value
    elif task == "retrieve_known_targets":
        targets = next(
            (item[name] for name in ("targets", "genes", "gene_symbols") if name in item),
            None,
        )
        if not isinstance(targets, list):
            return None
        out["targets"] = targets[:3]
    elif task == "retrieve_known_drugs":
        ids = item.get("drugbank_ids")
        smiles = item.get("smiles")
        if (not isinstance(ids, list) or not isinstance(smiles, list)) and isinstance(
            item.get("drugs"), list
        ):
            pairs = [
                (drug.get("drugbank_id") or drug.get("drugbankId"), drug.get("smiles"))
                for drug in item["drugs"]
                if isinstance(drug, dict)
            ]
            ids = [drug_id for drug_id, _ in pairs if isinstance(drug_id, str)][:5]
            smiles = [value for _, value in pairs if isinstance(value, str) and value][:5]
        if not isinstance(ids, list) or not isinstance(smiles, list):
            return None
        out["drugbank_ids"] = ids[:5]
        out["smiles"] = smiles[:5]
    elif task == "molecular_design":
        smiles = next(
            (item[name] for name in ("smiles", "smiles_list", "molecules") if name in item),
            None,
        )
        if not isinstance(smiles, list) or len(smiles) < 5:
            return None
        out["smiles"] = smiles[:5]
    else:
        required = set(_item_schema(task)["required"]) - {"case_index"}
        if not required.issubset(item):
            return None
        out.update({name: item[name] for name in required})
    return out


def _normalize_provider_value(task: str, value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict) and "case_index" in value:
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = value
    elif isinstance(value, dict):
        raw_items = next(
            (
                value[name]
                for name in ("results", "predictions", "cases", "answers", "data")
                if isinstance(value.get(name), list)
            ),
            None,
        )
    else:
        raw_items = None
    if not isinstance(raw_items, list):
        return None
    items = [_normalized_item(task, item) for item in raw_items]
    return {"results": [item for item in items if item is not None]}


def _decode_provider_content(
    task: str, content: str, expected_indices: list[int]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize provider packaging only; semantic answer values remain unchanged."""
    candidates = _json_candidates(content)
    normalized = [
        value for candidate in candidates
        if (value := _normalize_provider_value(task, candidate)) is not None
    ]
    for value in reversed(normalized):
        try:
            _validate_result(task, value, expected_indices)
        except ValueError:
            continue
        return value, {
            "json_candidates": len(candidates),
            "provider_format_normalized": value not in candidates,
        }
    by_index: dict[int, dict[str, Any]] = {}
    for value in normalized:
        for item in value["results"]:
            if item["case_index"] in expected_indices:
                by_index[item["case_index"]] = item
    combined = {"results": [by_index[index] for index in expected_indices if index in by_index]}
    _validate_result(task, combined, expected_indices)
    return combined, {
        "json_candidates": len(candidates),
        "provider_format_normalized": True,
        "combined_json_fragments": True,
    }


def _collapse_single_case_repetitions(
    value: Any,
    expected_indices: list[int],
) -> tuple[Any, int, bool, int]:
    """Keep the first matching result when a one-case provider response expands."""
    if len(expected_indices) != 1 or not isinstance(value, dict):
        return value, 0, True, 0
    results = value.get("results")
    if not isinstance(results, list) or len(results) <= 1:
        return value, 0, True, 0
    matches = [
        item
        for item in results
        if isinstance(item, dict) and item.get("case_index") == expected_indices[0]
    ]
    if not matches:
        return value, 0, True, 0
    first = matches[0]
    identical = all(item == first for item in matches[1:])
    out_of_scope = len(results) - len(matches)
    normalized = dict(value)
    normalized["results"] = [first]
    return normalized, len(results) - 1, identical, out_of_scope


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
    allow_public_web = bool(model.get("allow_public_web", False))
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
    if allow_public_web:
        isolation_args = [
            "-c", 'web_search="live"',
            "-c", "skills.include_instructions=false",
            "-c", "skills.bundled.enabled=false",
        ]
        disabled_features = [
            "plugins", "apps", "memories", "multi_agent", "computer_use",
            "in_app_browser", "browser_use", "browser_use_external", "shell_tool",
            "shell_zsh_fork", "shell_snapshot", "unified_exec", "skill_search",
            "skill_mcp_dependency_install",
        ]
        for feature in disabled_features:
            isolation_args.extend(("--disable", feature))
        args[args.index("--skip-git-repo-check"):args.index("--skip-git-repo-check")] = isolation_args
    else:
        args[args.index("--skip-git-repo-check"):args.index("--skip-git-repo-check")] = [
            "--disable", "web_search"
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
    event_objects = []
    for line in completed.stdout.splitlines():
        try:
            event_objects.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    event_types = [
        str(event.get("item", {}).get("type", ""))
        for event in event_objects
        if isinstance(event, dict) and isinstance(event.get("item"), dict)
    ]
    prohibited = [
        event_type for event_type in event_types
        if event_type in {"command_execution", "mcp_tool_call", "file_change"}
        or (event_type == "web_search" and not allow_public_web)
    ]
    if prohibited:
        raise RuntimeError(f"Codex emitted prohibited tool events: {sorted(set(prohibited))}")
    web_events = sum(event_type == "web_search" for event_type in event_types)
    skill_instruction_events = sum(
        "Skill descriptions" in str(event.get("message", ""))
        or "<skills_instructions>" in str(event)
        for event in event_objects
        if isinstance(event, dict)
    )
    if allow_public_web and skill_instruction_events:
        raise RuntimeError("Codex clean Direct context contained skill instructions")
    return {
        "response": value,
        "wall_seconds": wall,
        "transport_metadata": {
            "returncode": completed.returncode,
            "event_lines": len(completed.stdout.splitlines()),
            "prohibited_tool_events": 0,
            "web_search_events": web_events,
            "skill_instruction_events": skill_instruction_events,
            "global_skill_scan_warning": "failed to load skill" in completed.stderr,
            "provider_sampling_seed_supported": False,
            "replicate_seed": model.get("seed"),
        },
    }


def _openrouter_call(model: dict[str, Any], task: str, prompt: str, schema: dict[str, Any],
                     cell_root: Path, expected_indices: list[int] | None = None) -> dict[str, Any]:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    provider = {
        "allow_fallbacks": bool(model.get("allow_provider_fallbacks", False)),
        "require_parameters": bool(model.get("require_parameters", True)),
        "data_collection": "deny",
    }
    if model.get("provider_order"):
        provider["order"] = list(model["provider_order"])
    request_body = {
        "model": model["model_id"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": int(model.get("max_tokens", 12000)),
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
    if not model.get("omit_reasoning", False):
        request_body["reasoning"] = model.get("reasoning", {"effort": "low"})
    if model.get("omit_response_format", False):
        request_body.pop("response_format")
    if model.get("include_seed", True):
        request_body["seed"] = int(model.get("seed", 20260805))
    if model.get("allow_public_web", False):
        request_body["tools"] = [{"type": "openrouter:web_search"}]
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
    if expected_indices is None:
        case_count = int(schema["properties"]["results"]["minItems"])
        expected_indices = list(range(1, case_count + 1))
    value, format_metadata = _decode_provider_content(task, content, expected_indices)
    return {
        "response": value,
        "wall_seconds": wall,
        "transport_metadata": {
            "response_id": envelope.get("id"),
            "returned_model": envelope.get("model"),
            "provider": envelope.get("provider"),
            "usage": envelope.get("usage"),
            "finish_reason": envelope["choices"][0].get("finish_reason"),
            "web_annotations": message.get("annotations", []),
            "web_search_requests": (
                envelope.get("usage", {})
                .get("server_tool_use", {})
                .get("web_search_requests", 0)
            ),
            "replicate_seed": request_body.get("seed"),
            **format_metadata,
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
    max_attempts = int(model.get("max_attempts", 1))
    if max_attempts < 1 or max_attempts > 6:
        raise ValueError("max_attempts must be in 1..6")
    batch_workers = int(model.get("batch_workers", 1))
    if batch_workers < 1 or batch_workers > 5:
        raise ValueError("batch_workers must be in 1..5")

    def run_batch(indices: list[int]) -> tuple[list[int], dict[str, Any]]:
        batch_root = cell_root / f"batch-{indices[0]:02d}-{indices[-1]:02d}"
        batch_root.mkdir(parents=True, exist_ok=False)
        outcome = None
        last_error = None
        for attempt in range(1, max_attempts + 1):
            attempt_root = batch_root / f"attempt-{attempt:02d}"
            attempt_root.mkdir()
            try:
                outcome = _openrouter_call(
                    model,
                    task,
                    _prompt(
                        task,
                        set(indices),
                        allow_public_web=bool(model.get("allow_public_web", False)),
                        case_order_seed=model.get("seed"),
                    ),
                    _schema(task, len(indices)),
                    attempt_root,
                    indices,
                )
                outcome["transport_metadata"]["request_attempts"] = attempt
                break
            except Exception as exc:
                last_error = exc
                if attempt == max_attempts:
                    raise
                time.sleep(2 ** (attempt - 1))
        if outcome is None:
            raise RuntimeError("OpenRouter batch produced no valid response") from last_error
        (
            outcome["response"],
            collapsed,
            identical,
            out_of_scope,
        ) = _collapse_single_case_repetitions(outcome["response"], indices)
        if collapsed:
            outcome["transport_metadata"]["duplicate_results_collapsed"] = collapsed
            outcome["transport_metadata"]["repeated_results_identical"] = identical
            outcome["transport_metadata"]["out_of_scope_results_discarded"] = out_of_scope
        _validate_result(task, outcome["response"], indices)
        return indices, outcome

    index_batches = [
        list(range(start, min(start + batch_size, 21)))
        for start in range(1, 21, batch_size)
    ]
    with ThreadPoolExecutor(max_workers=batch_workers) as pool:
        futures = {pool.submit(run_batch, indices): indices for indices in index_batches}
        outcomes = [future.result() for future in as_completed(futures)]
    for indices, outcome in sorted(outcomes, key=lambda item: item[0][0]):
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
            _prompt(
                task,
                set(indices),
                allow_public_web=bool(model.get("allow_public_web", False)),
                case_order_seed=model.get("seed"),
            ),
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
    prompt = _prompt(
        task,
        allow_public_web=bool(model.get("allow_public_web", False)),
        case_order_seed=model.get("seed"),
    )
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
