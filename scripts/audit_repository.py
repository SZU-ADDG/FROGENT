#!/usr/bin/env python3
"""Read-only audit of the Agent-first repository boundary."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_TRACKED_BYTES = 10 * 1024 * 1024
PRODUCT_DIRECTORIES = {
    "agent", "app", "docs", "evaluation", "mcp", "runtime", "scripts", "skills", "tests"
}
REQUIRED_PATHS = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / ".codex-plugin" / "plugin.json",
    ROOT / "agent" / "__init__.py",
    ROOT / "agent" / "app" / "research_service.py",
    ROOT / "app" / "chat.py",
    ROOT / "app" / "models.py",
    ROOT / "app" / "server.py",
    ROOT / "docs" / "ARCHITECTURE.md",
    ROOT / "evaluation" / "cases" / "research-eval-v1.manifest.json",
    ROOT / "mcp" / "trioworkspace_mcp.py",
    ROOT / "runtime" / "README.md",
)
FORBIDDEN_TOP_LEVEL = {"copy-plan", "plugins", "sources"}
FORBIDDEN_TRACKED_FRAGMENTS = {
    "REFACTORING_LOG",
    "plan-forward",
    "plan_eval",
    "source-acquisition",
    "app_v4",
    "v4_adapter",
    "research_v4",
}


def _tracked_files() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    return tuple(item.decode("utf-8") for item in result.stdout.split(b"\0") if item)


def audit() -> dict[str, int]:
    if (ROOT / ".runtime").exists():
        raise ValueError("hidden .runtime is forbidden; local execution state belongs in runtime/")
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_PATHS if not path.is_file()]
    if missing:
        raise ValueError("required repository paths are missing: " + ", ".join(missing))

    visible = {path.name for path in ROOT.iterdir() if path.is_dir() and not path.name.startswith(".")}
    missing_product = PRODUCT_DIRECTORIES - visible
    if missing_product:
        raise ValueError(f"Agent product directories are missing: {sorted(missing_product)!r}")
    forbidden_present = FORBIDDEN_TOP_LEVEL & visible
    if forbidden_present:
        raise ValueError(f"retired top-level directories remain: {sorted(forbidden_present)!r}")
    unexpected_visible = visible - PRODUCT_DIRECTORIES
    if unexpected_visible:
        raise ValueError(
            f"unexpected visible top-level directories remain: {sorted(unexpected_visible)!r}"
        )

    tracked = _tracked_files()
    historical = [
        path for path in tracked
        if any(fragment in path for fragment in FORBIDDEN_TRACKED_FRAGMENTS)
    ]
    if historical:
        raise ValueError(f"historical construction material is tracked: {historical!r}")

    runtime_paths = [path for path in tracked if path.startswith("runtime/")]
    if runtime_paths != ["runtime/README.md"]:
        raise ValueError(f"unexpected tracked runtime payload: {runtime_paths!r}")

    oversize: list[str] = []
    symlinks: list[str] = []
    for relative in tracked:
        path = ROOT / relative
        path.resolve(strict=True).relative_to(ROOT)
        if path.is_symlink():
            symlinks.append(relative)
        if path.stat().st_size > MAX_TRACKED_BYTES:
            oversize.append(relative)
    if symlinks:
        raise ValueError(f"tracked symlinks are not allowed: {symlinks!r}")
    if oversize:
        raise ValueError(f"tracked files exceed 10 MiB: {oversize!r}")

    active_python = tuple(sorted((ROOT / "agent").rglob("*.py")))
    web_python = tuple(sorted((ROOT / "app").glob("*.py")))
    oversized_modules = [
        str(path.relative_to(ROOT))
        for path in (*active_python, *web_python)
        if len(path.read_text(encoding="utf-8").splitlines()) > 260
    ]
    if oversized_modules:
        raise ValueError(f"runtime modules exceed 260 lines: {oversized_modules!r}")
    forbidden_snapshot_refs: list[str] = []
    for code_root in (ROOT / "agent", ROOT / "mcp"):
        for path in code_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "sources/" in text or "plugins/frogent-drug-design" in text:
                forbidden_snapshot_refs.append(str(path.relative_to(ROOT)))
    if forbidden_snapshot_refs:
        raise ValueError(
            "active code references retired layouts: " + ", ".join(forbidden_snapshot_refs)
        )

    return {
        "tracked_files": len(tracked),
        "agent_modules": len(active_python),
        "agent_lines": sum(
            len(path.read_text(encoding="utf-8").splitlines()) for path in active_python
        ),
        "web_modules": len(web_python),
        "skills": len(tuple((ROOT / "skills").glob("*/SKILL.md"))),
    }


def main() -> int:
    try:
        result = audit()
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"repository_audit=FAIL error={error}", file=sys.stderr)
        return 1
    print("repository_audit=PASS")
    for key, value in result.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
