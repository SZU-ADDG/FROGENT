#!/usr/bin/env python3
"""Validate a preregistered clean FROGENT installation and freeze its evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SENSITIVE_ENV_MARKERS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD")


def _contained(path: Path, boundary: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(boundary.resolve())
    return resolved


def _contained_executable(path: Path, boundary: Path) -> Path:
    """Keep the venv entry path in-run while allowing its interpreter symlink target."""
    absolute = path.absolute()
    absolute.relative_to(boundary.resolve())
    if not absolute.is_file():
        raise FileNotFoundError(absolute)
    return absolute


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not any(marker in key.upper() for marker in SENSITIVE_ENV_MARKERS)
    }
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(PROJECT_ROOT)
    return environment


def _run(
    name: str,
    command: list[str],
    *,
    logs: Path,
    environment: dict[str, str],
    cwd: Path = PROJECT_ROOT,
) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    stdout = logs / f"{name}.stdout.log"
    stderr = logs / f"{name}.stderr.log"
    stdout.write_text(completed.stdout, encoding="utf-8")
    stderr.write_text(completed.stderr, encoding="utf-8")
    return {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "return_code": completed.returncode,
        "stdout": str(stdout.relative_to(PROJECT_ROOT)),
        "stdout_sha256": _sha256(stdout),
        "stderr": str(stderr.relative_to(PROJECT_ROOT)),
        "stderr_sha256": _sha256(stderr),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--node-root", type=Path, required=True)
    args = parser.parse_args()

    run_root = _contained(args.run_root, PROJECT_ROOT)
    python = _contained_executable(args.python, run_root)
    node_root = _contained(args.node_root, run_root)
    protocol_dir = run_root / "protocol"
    protocol = next(
        (path for path in (protocol_dir / "protocol.json", protocol_dir / "amendment.json")
         if path.is_file()),
        protocol_dir / "protocol.json",
    )
    if not protocol.is_file():
        raise FileNotFoundError(f"missing frozen protocol: {protocol}")
    logs = run_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    environment = _clean_environment()

    smoke = """
from datetime import date
from agent.core.harness import (
    CommandKind, HarnessCommand, HarnessPhase, HarnessPolicy, HarnessState, advance,
)
state = HarnessState(run_id="clean-install-smoke", as_of=date.today())
state = advance(state, HarnessCommand(CommandKind.DELEGATE_AGENT,
    HarnessPhase.PLANNING, "plan clean smoke", "planner"), HarnessPolicy())
assert state.phase is HarnessPhase.PLANNING
state = advance(state, HarnessCommand(CommandKind.CALL_CAPABILITY,
    HarnessPhase.EXECUTION, "execute clean smoke", "local-smoke"), HarnessPolicy())
state = advance(state, HarnessCommand(CommandKind.CALL_CAPABILITY,
    HarnessPhase.EVALUATION, "evaluate clean smoke", "local-smoke"), HarnessPolicy())
state = advance(state, HarnessCommand(CommandKind.COMPLETE,
    HarnessPhase.COMPLETE, "smoke complete"), HarnessPolicy())
assert state.terminal
print("core_harness_smoke=PASS")
""".strip()

    checks = [
        _run(
            "python_version",
            [str(python), "--version"],
            logs=logs,
            environment=environment,
        ),
        _run(
            "pip_freeze",
            [str(python), "-m", "pip", "freeze", "--all"],
            logs=logs,
            environment=environment,
        ),
        _run(
            "npm_tree",
            ["npm", "ls", "--json", "--all"],
            logs=logs,
            environment=environment,
            cwd=node_root,
        ),
        _run(
            "core_harness_smoke",
            [str(python), "-c", smoke],
            logs=logs,
            environment=environment,
        ),
        _run(
            "flask_no_credential_smoke",
            [
                str(python),
                "-m",
                "unittest",
                "tests.test_web_app.WebAppTests.test_routes_stream_research_and_save_history_without_app_writes",
            ],
            logs=logs,
            environment=environment,
        ),
        _run(
            "project_check",
            [str(python), "scripts/check.py"],
            logs=logs,
            environment=environment,
        ),
    ]
    success = all(check["return_code"] == 0 for check in checks)
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    manifest = {
        "schema_version": "frogent-clean-install-result-v1",
        "run_root": str(run_root.relative_to(PROJECT_ROOT)),
        "completed_at": now,
        "status": "complete" if success else "failed",
        "credentials_removed_from_environment": True,
        "protocol": str(protocol.relative_to(PROJECT_ROOT)),
        "protocol_sha256": _sha256(protocol),
        "python_executable": str(python.relative_to(PROJECT_ROOT)),
        "node_root": str(node_root.relative_to(PROJECT_ROOT)),
        "checks": checks,
    }
    manifest_path = run_root / "final-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
