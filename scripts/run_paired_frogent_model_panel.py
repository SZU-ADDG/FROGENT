#!/usr/bin/env python3
"""Run exact base models inside the frozen FROGENT paired benchmark arm."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.llm.codex_client import CodexClient
from agent.llm.openrouter_client import OpenRouterClient
from scripts.run_clean_ten_model_panel import (
    CODEX_EXECUTABLE,
    TASK_FILES,
    _schema,
    _slug,
    _task_payload,
    _collapse_single_case_repetitions,
    _validate_result,
)

DEFAULT_RUN_ROOT = (
    ROOT
    / "runtime/evaluation/revision-20260805/"
    "paired-twelve-model-frogent-r20"
)
WRITE_LOCK = threading.Lock()


def _client(
    model: dict[str, Any],
    *,
    max_attempts: int,
    allow_provider_fallbacks: bool,
    max_tokens: int,
):
    if model["transport"] == "codex":
        return CodexClient(
            ROOT,
            executable=str(CODEX_EXECUTABLE),
            model=model["model_id"],
            reasoning_effort=model["reasoning"]["effort"],
            timeout=None,
        )
    return OpenRouterClient(
        ROOT,
        model=model["model_id"],
        reasoning=model["reasoning"],
        timeout=None,
        max_tokens=max_tokens,
        provider_order=tuple(model.get("provider_order", ())),
        allow_provider_fallbacks=allow_provider_fallbacks,
        max_attempts=max_attempts,
    )


def _run_cell(
    run_root: Path,
    evidence_root: Path,
    model: dict[str, Any],
    task: str,
    batch_size: int,
    max_attempts: int,
    allow_provider_fallbacks: bool,
    max_tokens: int,
    resume_from_root: Path | None,
    concise_known_drugs: bool,
    case_order_seed: int | None = None,
) -> dict[str, Any]:
    cell_root = run_root / "raw" / _slug(model["model_id"]) / task
    terminal_path = cell_root / "terminal.json"
    with WRITE_LOCK:
        if terminal_path.exists():
            record = json.loads(terminal_path.read_text(encoding="utf-8"))
            return {
                "model_id": model["model_id"],
                "task": task,
                "status": record["status"],
                "existing": True,
            }
        cell_root.mkdir(parents=True, exist_ok=False)
    instruction, cases = _task_payload(task)
    evidence = json.loads((evidence_root / f"{task}.json").read_text(encoding="utf-8"))
    evidence_by_index = {int(row["case_index"]): row for row in evidence}
    combined: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []
    started = time.monotonic()
    record: dict[str, Any] = {
        "schema_version": "frogent-paired-model-cell-v1",
        "model_id": model["model_id"],
        "display_name": model["display_name"],
        "transport": model["transport"],
        "task": task,
        "status": "failed",
        "frogent_components": [
            "frozen task router",
            "real tool evidence cache",
            "evidence-grounded scientific synthesis",
            "strict structured output",
        ],
    }
    try:
        client = _client(
            model,
            max_attempts=max_attempts,
            allow_provider_fallbacks=allow_provider_fallbacks,
            max_tokens=max_tokens,
        )
        ordered_indices = list(range(1, 21))
        if case_order_seed is not None:
            task_offset = int(hashlib.sha256(task.encode("utf-8")).hexdigest()[:8], 16)
            random.Random(case_order_seed + task_offset).shuffle(ordered_indices)
        for start in range(0, 20, batch_size):
            indices = ordered_indices[start:start + batch_size]
            batch_cases = [
                case for case in cases if int(case["case_index"]) in indices
            ]
            batch_evidence = [evidence_by_index[index] for index in indices]
            payload = {
                "task": task,
                "task_instruction": (
                    instruction
                    + (
                        " Return fewer entries when an exact DrugBank ID or SMILES is "
                        "unknown. Do not reconstruct, approximate, or spell out an "
                        "uncertain long structure."
                        if concise_known_drugs and task == "retrieve_known_drugs"
                        else ""
                    )
                ),
                "cases": batch_cases,
                "frogent_tool_evidence": batch_evidence,
                "evidence_policy": (
                    "Use the supplied real-tool evidence where relevant. Resolve conflicts "
                    "scientifically. Do not invent tool results. Evidence limitations must "
                    "change confidence or prioritization while preserving the required output."
                ),
            }
            batch_name = (
                f"batch-{indices[0]:02d}-{indices[-1]:02d}"
                if case_order_seed is None
                else "batch-"
                + f"{start // batch_size + 1:02d}-"
                + "-".join(f"{index:02d}" for index in indices)
            )
            batch_root = cell_root / batch_name
            batch_root.mkdir()
            payload_path = batch_root / "payload.json"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            if resume_from_root is not None:
                source_batch = (
                    resume_from_root
                    / "raw"
                    / _slug(model["model_id"])
                    / task
                    / batch_name
                    / "unvalidated-response.json"
                )
                if source_batch.is_file():
                    value = json.loads(source_batch.read_text(encoding="utf-8"))
                    value, collapsed, identical, out_of_scope = (
                        _collapse_single_case_repetitions(value, indices)
                    )
                    _validate_result(task, value, indices)
                    combined.extend(value["results"])
                    batches.append({
                        "case_indices": indices,
                        "payload_sha256": hashlib.sha256(
                            payload_path.read_bytes()
                        ).hexdigest(),
                        "transport_metadata": {
                            "reused_batch": str(source_batch.relative_to(ROOT)),
                            "duplicate_results_collapsed": collapsed,
                            "repeated_results_identical": identical,
                            "out_of_scope_results_discarded": out_of_scope,
                        },
                    })
                    (batch_root / "response.json").write_text(
                        json.dumps(
                            value,
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    continue
            value = client.generate(
                "FROGENT evidence-grounded scientific decision and synthesis role",
                (
                    f"Complete all {len(indices)} cases independently using the frozen FROGENT tool "
                    "evidence. Preserve each case_index and return only the exact schema."
                ),
                payload,
                schema=_schema(task, len(indices)),
                cwd=batch_root,
            )
            (batch_root / "unvalidated-response.json").write_text(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            value, collapsed, identical, out_of_scope = (
                _collapse_single_case_repetitions(value, indices)
            )
            if collapsed:
                (batch_root / "normalization.json").write_text(
                    json.dumps(
                        {
                            "rule": "keep_first_single_case_repetition",
                            "duplicates_removed": collapsed,
                            "case_index": indices[0],
                            "repeated_results_identical": identical,
                            "out_of_scope_results_discarded": out_of_scope,
                            "unvalidated_response_retained": True,
                        },
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            _validate_result(task, value, indices)
            combined.extend(value["results"])
            metadata = dict(getattr(client, "last_metadata", {}))
            if collapsed:
                metadata["duplicate_results_collapsed"] = collapsed
                metadata["repeated_results_identical"] = identical
                metadata["out_of_scope_results_discarded"] = out_of_scope
            batches.append({
                "case_indices": indices,
                "payload_sha256": hashlib.sha256(
                    payload_path.read_bytes()
                ).hexdigest(),
                "transport_metadata": metadata,
            })
            (batch_root / "response.json").write_text(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        combined.sort(key=lambda item: int(item["case_index"]))
        response = {"results": combined}
        _validate_result(task, response)
        record.update({
            "status": "succeeded",
            "response": response,
            "batches": batches,
            "wall_seconds": time.monotonic() - started,
        })
    except Exception as exc:
        record.update({
            "error": f"{type(exc).__name__}: {exc}",
            "batches": batches,
            "wall_seconds": time.monotonic() - started,
        })
    terminal_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "model_id": model["model_id"],
        "task": task,
        "status": record["status"],
        "existing": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--models", nargs="*")
    parser.add_argument("--tasks", nargs="*", choices=sorted(TASK_FILES))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--max-attempts", type=int, default=1)
    parser.add_argument("--allow-provider-fallbacks", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=12000)
    parser.add_argument("--resume-from-run-root", type=Path)
    parser.add_argument("--concise-known-drugs", action="store_true")
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    run_root.relative_to(ROOT.resolve())
    protocol = json.loads(
        (run_root / "protocol/protocol.json").read_text(encoding="utf-8")
    )
    models = protocol["models"]
    if args.models:
        requested = set(args.models)
        models = [model for model in models if model["model_id"] in requested]
        missing = requested - {model["model_id"] for model in models}
        if missing:
            raise ValueError(f"models not frozen in protocol: {sorted(missing)}")
    tasks = args.tasks or protocol["tasks"]
    if args.workers < 1 or args.workers > 8:
        raise ValueError("workers must be in 1..8")
    if args.batch_size < 1 or args.batch_size > 5:
        raise ValueError("batch-size must be in 1..5")
    if args.max_attempts < 1 or args.max_attempts > 6:
        raise ValueError("max-attempts must be in 1..6")
    if args.max_tokens < 1000 or args.max_tokens > 131072:
        raise ValueError("max-tokens must be in 1000..131072")
    resume_from_root = (
        args.resume_from_run_root.resolve()
        if args.resume_from_run_root is not None
        else None
    )
    if resume_from_root is not None:
        resume_from_root.relative_to(ROOT.resolve())
    evidence_root = run_root / "evidence"
    if not (evidence_root / "manifest.json").is_file():
        raise FileNotFoundError("frozen FROGENT evidence manifest is missing")
    jobs = [(model, task) for model in models for task in tasks]
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                _run_cell,
                run_root,
                evidence_root,
                model,
                task,
                args.batch_size,
                args.max_attempts,
                args.allow_provider_fallbacks,
                args.max_tokens,
                resume_from_root,
                args.concise_known_drugs,
                None,
            ): (model, task)
            for model, task in jobs
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    return 0 if all(result["status"] == "succeeded" for result in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
