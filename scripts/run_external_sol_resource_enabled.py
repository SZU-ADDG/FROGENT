#!/usr/bin/env python3
"""Run the preregistered Sol resource-enabled external-system adaptations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_clean_ten_model_panel as clean
from scripts import score_clean_ten_model_panel as scorer

DEFAULT_RUN_ROOT = ROOT / "runtime/evaluation/revision-20260810/external-sol-resource-enabled-r03"
CODEX = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
WRITE_LOCK = threading.Lock()


def _slug(value: str) -> str:
    return clean._slug(value)


def _load_protocol(run_root: Path) -> dict[str, Any]:
    protocol = json.loads((run_root / "protocol/protocol.json").read_text(encoding="utf-8"))
    if protocol.get("status") != "preregistered_before_outputs":
        raise ValueError("protocol is not preregistered")
    if protocol.get("base_model") != "gpt-5.6-sol":
        raise ValueError("base model must be gpt-5.6-sol")
    if sum(len(system["tasks"]) for system in protocol["systems"]) != 6:
        raise ValueError("protocol must freeze six aligned cells")
    return protocol


def _resolve_project_path(relative: str, *, allow_external_symlink: bool = False) -> Path:
    path = (ROOT / relative).absolute()
    path.relative_to(ROOT.absolute())
    if not path.exists():
        raise FileNotFoundError(path)
    if not allow_external_symlink:
        path = path.resolve()
        path.relative_to(ROOT.resolve())
    return path


def _prompt(system: dict[str, Any], task: str, source: Path, python: Path, workdir: Path) -> str:
    instruction, cases = clean._task_payload(task, allow_public_web=True)
    payload = {"task": task, "instruction": instruction, "cases": cases}
    return (
        f"Act as a current-model implementation of {system['name']} at frozen commit "
        f"{system['commit']}. Use the public workflow design in {source}. The matching isolated "
        f"Python executable is {python}. You may inspect that repository, execute its usable "
        f"native components from {workdir}, and use public live web search. Record unavailable or "
        "failing native components through the observable command/event trace and continue with "
        "the strongest workflow-consistent analysis supported by the remaining resources. "
        "Do not access FROGENT initialization, FROGENT tools, user-private files or tools, other "
        "system repositories, persistent memory, prior benchmark outputs, hidden answers or gold "
        "labels. Do not modify the frozen source or environment. Complete all cases independently "
        "and return only the JSON object required by the output schema. Preserve each case_index.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


def _event_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    item_types = []
    commands = []
    web_queries = []
    for event in events:
        item = event.get("item") if isinstance(event, dict) else None
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type", ""))
        item_types.append(kind)
        if kind == "command_execution":
            command = item.get("command") or item.get("cmd")
            if command is not None:
                commands.append(str(command))
        if kind == "web_search":
            web_queries.append(str(item.get("query", "")))
    return {
        "event_type_counts": {kind: item_types.count(kind) for kind in sorted(set(item_types))},
        "command_count": len(commands),
        "commands": commands,
        "web_search_count": len(web_queries),
        "web_queries": web_queries,
    }


def _run_cell(run_root: Path, protocol: dict[str, Any], system: dict[str, Any], task: str) -> dict[str, Any]:
    cell_root = run_root / "raw" / _slug(system["name"]) / task
    terminal_path = cell_root / "terminal.json"
    with WRITE_LOCK:
        if terminal_path.is_file():
            return json.loads(terminal_path.read_text(encoding="utf-8"))
        cell_root.mkdir(parents=True)
    workdir = cell_root / "workdir"
    workdir.mkdir()
    subprocess.run(["git", "init", "--quiet", str(workdir)], check=True, capture_output=True)
    source = _resolve_project_path(system["source_root"])
    python = _resolve_project_path(system["environment_python"], allow_external_symlink=True)
    if subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True,
                      text=True, check=True).stdout.strip() != system["commit"]:
        raise ValueError(f"source commit drift for {system['name']}")
    schema = clean._schema(task)
    schema_path = cell_root / "schema.json"
    last_path = cell_root / "last-message.json"
    events_path = cell_root / "events.jsonl"
    stderr_path = cell_root / "stderr.txt"
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    prompt = _prompt(system, task, source, python, workdir)
    (cell_root / "prompt.json").write_text(json.dumps({
        "sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "resource_contract": protocol["resource_contract"],
        "source": str(source.relative_to(ROOT)),
        "environment_python": str(python.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args = [
        str(CODEX), "exec", "--model", protocol["base_model"],
        "-c", f'model_reasoning_effort="{protocol["reasoning_effort"]}"',
        "-c", 'approval_policy="never"', "-c", 'web_search="live"',
        "-c", "project_doc_max_bytes=0", "-c", "skills.include_instructions=false",
        "-c", "skills.bundled.enabled=false", "--ephemeral", "--ignore-user-config",
        "--ignore-rules", "--strict-config", "--sandbox", "workspace-write",
    ]
    for feature in ("plugins", "apps", "memories", "multi_agent", "computer_use",
                    "in_app_browser", "browser_use", "browser_use_external", "skill_search",
                    "skill_mcp_dependency_install"):
        args.extend(("--disable", feature))
    args.extend(("--skip-git-repo-check", "--cd", str(workdir), "--output-schema",
                 str(schema_path), "--output-last-message", str(last_path), "--json", "-"))
    started = time.monotonic()
    completed = subprocess.run(args, input=prompt, text=True, capture_output=True,
                               cwd=workdir, check=False)
    events_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    events = []
    for line in completed.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    terminal: dict[str, Any] = {
        "schema_version": "frogent-external-sol-resource-cell-v1",
        "system": system["name"], "task": task, "model_id": protocol["base_model"],
        "source_commit": system["commit"], "status": "failed",
        "wall_seconds": time.monotonic() - started,
        "returncode": completed.returncode, "event_summary": _event_summary(events),
    }
    try:
        if completed.returncode:
            raise RuntimeError(f"Codex exit {completed.returncode}: {completed.stderr[-1200:]}")
        response = json.loads(last_path.read_text(encoding="utf-8"))
        clean._validate_result(task, response)
        terminal.update(status="succeeded", response=response)
    except Exception as exc:
        terminal["error"] = f"{type(exc).__name__}: {exc}"
    terminal_path.write_text(json.dumps(terminal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    print(json.dumps({"system": system["name"], "task": task, "status": terminal["status"]},
                     ensure_ascii=False), flush=True)
    return terminal


def analyze(run_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    cells = []
    for system in protocol["systems"]:
        for task in system["tasks"]:
            path = run_root / "raw" / _slug(system["name"]) / task / "terminal.json"
            record = {"system": system["name"], "task": task, "model_id": protocol["base_model"],
                      "status": "missing", "score": None}
            if path.is_file():
                terminal = json.loads(path.read_text(encoding="utf-8"))
                record.update(status=terminal["status"],
                              command_count=terminal.get("event_summary", {}).get("command_count", 0),
                              web_search_count=terminal.get("event_summary", {}).get("web_search_count", 0))
                if terminal["status"] == "succeeded":
                    details = scorer.SCORERS[task](terminal["response"])
                    values = [float(row["score"]) for row in details
                              if isinstance(row.get("score"), (int, float))
                              and math.isfinite(float(row["score"]))]
                    record.update(status="scored", score=sum(values) / len(values),
                                  measured_cases=len(values))
                else:
                    record["error"] = terminal.get("error")
            cells.append(record)
    counts = {status: sum(cell["status"] == status for cell in cells)
              for status in sorted({cell["status"] for cell in cells})}
    analysis = {"schema_version": "frogent-external-sol-resource-analysis-v1",
                "status": "complete" if counts.get("scored") == 6 else "partial",
                "cell_counts": counts, "cells": cells,
                "claim_boundary": protocol["claim_boundary"]}
    analysis_root = run_root / "analysis"; analysis_root.mkdir(exist_ok=True)
    (analysis_root / "summary.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (analysis_root / "cells.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cells[0])); writer.writeheader(); writer.writerows(cells)
    if analysis["status"] == "complete":
        (analysis_root / "final-manifest.json").write_text(json.dumps({
            "schema_version": "frogent-external-sol-resource-final-v1", "status": "complete",
            "cell_counts": counts, "model_id": protocol["base_model"],
            "claim_boundary": protocol["claim_boundary"],
        }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    run_root = args.run_root.resolve(); run_root.relative_to(ROOT.resolve())
    protocol = _load_protocol(run_root)
    results = []
    if not args.analyze_only:
        jobs = [(system, task) for system in protocol["systems"] for task in system["tasks"]]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = [future.result() for future in as_completed(
                [pool.submit(_run_cell, run_root, protocol, system, task) for system, task in jobs]
            )]
    analysis = analyze(run_root, protocol)
    return 0 if analysis["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
