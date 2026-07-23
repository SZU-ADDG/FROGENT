#!/usr/bin/env python3
"""Read-only repository boundary and layout audit."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "frogent-drug-design"
MAX_TRACKED_BYTES = 10 * 1024 * 1024
ALLOWED_SOURCE_FILES = {"sources/README.md"}
REQUIRED_PATHS = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "docs" / "source-acquisition" / "README.md",
    ROOT / "sources" / "README.md",
    PLUGIN / ".codex-plugin" / "plugin.json",
    PLUGIN / "docs" / "ARCHITECTURE.md",
    PLUGIN / "frogent_plugin" / "research_service.py",
)


def _tracked_files() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return tuple(item.decode("utf-8") for item in result.stdout.split(b"\0") if item)


def audit() -> dict[str, int]:
    if any(not path.is_file() for path in REQUIRED_PATHS):
        missing = [str(path.relative_to(ROOT)) for path in REQUIRED_PATHS if not path.is_file()]
        raise ValueError("required repository paths are missing: " + ", ".join(missing))

    tracked = _tracked_files()
    source_files = {path for path in tracked if path.startswith("sources/")}
    if source_files != ALLOWED_SOURCE_FILES:
        raise ValueError(f"unexpected tracked source snapshots: {sorted(source_files)!r}")

    runtime_paths = [
        path for path in tracked if path.startswith(".runtime/") or "/.runtime/" in path
    ]
    if runtime_paths:
        raise ValueError(f"runtime artifacts are tracked: {runtime_paths!r}")

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

    active_python = tuple((PLUGIN / "frogent_plugin").glob("*.py"))
    forbidden_snapshot_refs: list[str] = []
    for root in (PLUGIN / "frogent_plugin", PLUGIN / "mcp_servers"):
        for path in root.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "sources/mcp" in text or "sources/trioworkspace" in text:
                forbidden_snapshot_refs.append(str(path.relative_to(ROOT)))
    if forbidden_snapshot_refs:
        raise ValueError(
            "active code references reference-only snapshots: "
            + ", ".join(forbidden_snapshot_refs)
        )

    source_frogent = ROOT / "sources" / "frogent"
    if source_frogent.exists():
        required_compatibility = (
            source_frogent / "app_v4.py",
            source_frogent / "models.py",
            source_frogent / "templates" / "index.html",
            source_frogent / "assets",
        )
        if any(not path.exists() for path in required_compatibility):
            raise ValueError("local sources/frogent is missing the app-v4 compatibility surface")

    return {
        "tracked_files": len(tracked),
        "runtime_modules": len(active_python),
        "runtime_lines": sum(
            len(path.read_text(encoding="utf-8").splitlines()) for path in active_python
        ),
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
