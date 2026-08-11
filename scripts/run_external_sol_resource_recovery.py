#!/usr/bin/env python3
"""Run and audit the two preregistered Sol resource-boundary recovery cells."""

from __future__ import annotations

import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_external_sol_resource_enabled as base
from scripts import score_clean_ten_model_panel as scorer

ROOT = base.ROOT
RUN_ROOT = ROOT / "runtime/evaluation/revision-20260810/external-sol-resource-enabled-recovery-r05"
ORIGINAL_PROMPT = base._prompt


def _load() -> dict[str, Any]:
    protocol = json.loads((RUN_ROOT / "protocol/protocol.json").read_text(encoding="utf-8"))
    if protocol.get("status") != "preregistered_before_outputs":
        raise ValueError("recovery protocol is not preregistered")
    if protocol.get("base_model") != "gpt-5.6-sol":
        raise ValueError("recovery model drift")
    if sum(len(s["tasks"]) for s in protocol["systems"]) != 2:
        raise ValueError("recovery must contain exactly two rejected cells")
    return protocol


def _hardened_prompt(system: dict[str, Any], task: str, source: Path, python: Path,
                     workdir: Path) -> str:
    prompt = ORIGINAL_PROMPT(system, task, source, python, workdir)
    guard = (
        "Experimental filesystem guard: do not search for or read AGENTS.md, SKILL.md, .agents, "
        ".codex, the user home, any user cache, /tmp, prior evaluation outputs, or unrelated project "
        "paths. Do not run command-v/cache discovery. The only authorized readable experiment paths "
        f"are {source} and {python.parent.parent}; the only writable path is {workdir}. Put every "
        "temporary or downloaded file inside that workdir. If a component would require anything "
        "else, mark it unavailable and continue with authorized public web evidence. "
    )
    return guard + prompt


def _audit(terminal: dict[str, Any], source: Path, python: Path, workdir: Path) -> list[str]:
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
        for match in set(part for part in command.split() if part.startswith(str(ROOT) + "/")):
            cleaned = match.strip("'\";,)")
            if not any(cleaned.startswith(prefix) for prefix in allowed_project):
                violations.append(command)
                break
    return sorted(set(violations))


def main() -> int:
    protocol = _load()
    original_prompt = base._prompt
    base._prompt = _hardened_prompt
    try:
        jobs = [(system, task) for system in protocol["systems"] for task in system["tasks"]]
        with ThreadPoolExecutor(max_workers=2) as pool:
            terminals = list(as_completed([
                pool.submit(base._run_cell, RUN_ROOT, protocol, system, task)
                for system, task in jobs
            ]))
            for future in terminals:
                future.result()
    finally:
        base._prompt = original_prompt

    cells = []
    for system in protocol["systems"]:
        source = base._resolve_project_path(system["source_root"])
        python = base._resolve_project_path(system["environment_python"], allow_external_symlink=True)
        for task in system["tasks"]:
            cell_root = RUN_ROOT / "raw" / base._slug(system["name"]) / task
            terminal = json.loads((cell_root / "terminal.json").read_text(encoding="utf-8"))
            violations = _audit(terminal, source, python, cell_root / "workdir")
            record: dict[str, Any] = {"system": system["name"], "task": task,
                                      "terminal_status": terminal["status"],
                                      "resource_audit": "failed" if violations else "passed",
                                      "violations": violations, "score": None}
            if terminal["status"] == "succeeded" and not violations:
                details = scorer.SCORERS[task](terminal["response"])
                values = [float(row["score"]) for row in details
                          if isinstance(row.get("score"), (int, float))
                          and math.isfinite(float(row["score"]))]
                record.update(score=sum(values) / len(values), measured_cases=len(values))
            cells.append(record)
    status = "complete" if all(c["resource_audit"] == "passed" and c["score"] is not None
                               for c in cells) else "partial"
    analysis = {"schema_version": "frogent-external-sol-resource-recovery-analysis-v1",
                "status": status, "cells": cells, "parent_run": protocol["parent_run"]}
    out = RUN_ROOT / "analysis"
    out.mkdir(exist_ok=True)
    (out / "summary.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2,
                                                  sort_keys=True) + "\n", encoding="utf-8")
    if status == "complete":
        (out / "final-manifest.json").write_text(json.dumps({
            "schema_version": "frogent-external-sol-resource-recovery-final-v1",
            "status": "complete", "accepted_cells": 2, "parent_run": protocol["parent_run"]
        }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        parent = json.loads((ROOT / protocol["parent_run"] / "analysis/summary.json").read_text(
            encoding="utf-8"))
        replacement = {(cell["system"], cell["task"]): cell for cell in cells}
        combined_cells = []
        for cell in parent["cells"]:
            key = (cell["system"], cell["task"])
            if key in replacement:
                recovered = replacement[key]
                combined_cells.append({
                    "system": recovered["system"], "task": recovered["task"],
                    "model_id": protocol["base_model"], "status": "scored",
                    "score": recovered["score"], "measured_cases": recovered["measured_cases"],
                    "resource_audit": "passed", "provenance_run": str(RUN_ROOT.relative_to(ROOT)),
                })
            else:
                accepted = dict(cell)
                accepted.update(resource_audit="passed",
                                provenance_run=protocol["parent_run"])
                combined_cells.append(accepted)
        combined = {
            "schema_version": "frogent-external-sol-resource-combined-v1",
            "status": "complete", "model_id": protocol["base_model"],
            "accepted_cells": 6, "cells": combined_cells,
            "claim_boundary": "Task-aligned current-model adaptations with each public system's frozen files, available native tools and public web; not original-paper reproduction.",
        }
        (out / "combined-summary.json").write_text(json.dumps(
            combined, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (out / "combined-final-manifest.json").write_text(json.dumps({
            "schema_version": "frogent-external-sol-resource-combined-final-v1",
            "status": "complete", "accepted_cells": 6, "model_id": protocol["base_model"],
            "parent_run": protocol["parent_run"], "recovery_run": str(RUN_ROOT.relative_to(ROOT)),
        }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if status == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
