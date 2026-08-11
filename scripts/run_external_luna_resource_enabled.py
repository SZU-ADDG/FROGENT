#!/usr/bin/env python3
"""Run and audit the preregistered Luna external-system panel."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_external_sol_resource_enabled as base
from scripts import score_clean_ten_model_panel as scorer


DEFAULT_RUN_ROOT = (
    ROOT
    / "runtime/evaluation/revision-20260810/external-luna-resource-enabled-r01"
)
ORIGINAL_PROMPT = base._prompt


def _load(run_root: Path) -> dict[str, Any]:
    protocol = json.loads(
        (run_root / "protocol/protocol.json").read_text(encoding="utf-8")
    )
    if protocol.get("status") != "preregistered_before_outputs":
        raise ValueError("Luna protocol is not preregistered")
    if protocol.get("base_model") != "gpt-5.6-luna":
        raise ValueError("Luna model drift")
    if protocol.get("reasoning_effort") != "max":
        raise ValueError("Luna reasoning-effort drift")
    if sum(len(system["tasks"]) for system in protocol["systems"]) != 6:
        raise ValueError("Luna protocol must contain exactly six aligned cells")
    return protocol


def _hardened_prompt(
    system: dict[str, Any], task: str, source: Path, python: Path, workdir: Path
) -> str:
    prompt = ORIGINAL_PROMPT(system, task, source, python, workdir)
    guard = (
        "Experimental filesystem guard: do not search for or read AGENTS.md, SKILL.md, "
        ".agents, .codex, the user home, any user cache, /tmp, prior evaluation outputs, "
        "or unrelated project paths. Do not run command-v/cache discovery. The only "
        f"authorized readable experiment paths are {source} and {python.parent.parent}; "
        f"the only writable path is {workdir}. Put every temporary or downloaded file "
        "inside that workdir. If a component would require anything else, mark it "
        "unavailable and continue with authorized public web evidence. "
    )
    return guard + prompt


def _audit(
    terminal: dict[str, Any], source: Path, python: Path, workdir: Path
) -> list[str]:
    violations: list[str] = []
    forbidden_paths = ("/Users/dongxu/.codex", "/Users/dongxu/.cache", "/tmp/")
    allowed_project = (str(source), str(python.parent.parent), str(workdir))
    for command in terminal.get("event_summary", {}).get("commands", []):
        if any(token in command for token in forbidden_paths):
            violations.append(command)
            continue
        if "AGENTS.md" in command and "!AGENTS.md" not in command:
            violations.append(command)
            continue
        if "SKILL.md" in command and "!SKILL.md" not in command:
            violations.append(command)
            continue
        project_tokens = {
            part.strip("'\";,)")
            for part in command.split()
            if part.startswith(str(ROOT) + "/")
        }
        if any(
            not any(token.startswith(prefix) for prefix in allowed_project)
            for token in project_tokens
        ):
            violations.append(command)
    return sorted(set(violations))


def _score_and_audit(
    run_root: Path, protocol: dict[str, Any]
) -> dict[str, Any]:
    cells = []
    for system in protocol["systems"]:
        source = base._resolve_project_path(system["source_root"])
        python = base._resolve_project_path(
            system["environment_python"], allow_external_symlink=True
        )
        for task in system["tasks"]:
            cell_root = run_root / "raw" / base._slug(system["name"]) / task
            terminal_path = cell_root / "terminal.json"
            record: dict[str, Any] = {
                "system": system["name"],
                "task": task,
                "model_id": protocol["base_model"],
                "status": "missing",
                "resource_audit": "not_run",
                "score": None,
            }
            if terminal_path.is_file():
                terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
                violations = _audit(terminal, source, python, cell_root / "workdir")
                record.update(
                    status=terminal["status"],
                    resource_audit="failed" if violations else "passed",
                    violations=violations,
                    command_count=terminal.get("event_summary", {}).get(
                        "command_count", 0
                    ),
                    web_search_count=terminal.get("event_summary", {}).get(
                        "web_search_count", 0
                    ),
                    wall_seconds=terminal.get("wall_seconds"),
                )
                if terminal["status"] == "succeeded" and not violations:
                    details = scorer.SCORERS[task](terminal["response"])
                    values = [
                        float(row["score"])
                        for row in details
                        if isinstance(row.get("score"), (int, float))
                        and math.isfinite(float(row["score"]))
                    ]
                    record.update(
                        status="scored",
                        score=sum(values) / len(values) if values else None,
                        measured_cases=len(values),
                    )
                elif terminal["status"] != "succeeded":
                    record["error"] = terminal.get("error")
            cells.append(record)
    status = (
        "complete"
        if all(
            cell["status"] == "scored" and cell["resource_audit"] == "passed"
            for cell in cells
        )
        else "partial"
    )
    counts = {
        cell_status: sum(cell["status"] == cell_status for cell in cells)
        for cell_status in sorted({cell["status"] for cell in cells})
    }
    analysis = {
        "schema_version": "frogent-external-luna-resource-analysis-v1",
        "status": status,
        "model_id": protocol["base_model"],
        "cell_counts": counts,
        "cells": cells,
        "claim_boundary": protocol["claim_boundary"],
    }
    output = run_root / "analysis"
    output.mkdir(exist_ok=True)
    (output / "summary.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    fields = sorted({key for cell in cells for key in cell if key != "violations"})
    with (output / "cells.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(cells)
    if status == "complete":
        (output / "final-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": "frogent-external-luna-resource-final-v1",
                    "status": "complete",
                    "accepted_cells": 6,
                    "model_id": protocol["base_model"],
                    "reasoning_effort": protocol["reasoning_effort"],
                    "resource_audit": "passed_all_cells",
                    "analysis_files": ["summary.json", "cells.csv"],
                    "claim_boundary": protocol["claim_boundary"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    run_root.relative_to(ROOT.resolve())
    protocol = _load(run_root)
    if not args.analyze_only:
        jobs = [
            (system, task)
            for system in protocol["systems"]
            for task in system["tasks"]
        ]
        previous_prompt = base._prompt
        base._prompt = _hardened_prompt
        try:
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                futures = [
                    pool.submit(
                        base._run_cell, run_root, protocol, system, task
                    )
                    for system, task in jobs
                ]
                for future in as_completed(futures):
                    future.result()
        finally:
            base._prompt = previous_prompt
    analysis = _score_and_audit(run_root, protocol)
    print(json.dumps(analysis["cell_counts"], sort_keys=True), flush=True)
    return 0 if analysis["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
