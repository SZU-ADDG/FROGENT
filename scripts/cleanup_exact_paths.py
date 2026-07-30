#!/usr/bin/env python3
"""Dry-run and remove explicit project-local paths after safety checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PERMANENTLY_REFUSED = {
    PROJECT_ROOT,
    PROJECT_ROOT / "runtime",
    PROJECT_ROOT / "runtime" / "evaluation",
    PROJECT_ROOT / "runtime" / "evaluation" / "revision-20260730" / "nongpu-final",
}


def inventory(raw_target: str) -> dict[str, object]:
    if not raw_target.strip():
        raise ValueError("target path must be non-empty")
    target = Path(raw_target)
    if not target.is_absolute():
        raise ValueError("target path must be absolute")
    if target.is_symlink():
        raise ValueError("symlink targets are refused")
    resolved = target.resolve(strict=True)
    if resolved in PERMANENTLY_REFUSED:
        raise ValueError(f"protected root refused: {resolved}")
    if not resolved.is_relative_to(PROJECT_ROOT):
        raise ValueError(f"target escapes project root: {resolved}")
    runtime_allowed = resolved.is_relative_to(PROJECT_ROOT / "runtime" / "evaluation")
    cache_allowed = resolved.name == "__pycache__" and any(
        resolved.is_relative_to(PROJECT_ROOT / root_name)
        for root_name in ("agent", "tests", "scripts")
    )
    if not (runtime_allowed or cache_allowed):
        raise ValueError(f"target is outside allowed cleanup roots: {resolved}")

    files = [path for path in resolved.rglob("*") if path.is_file()]
    links = [path for path in resolved.rglob("*") if path.is_symlink()]
    if links:
        raise ValueError(f"nested symlinks are refused: {links}")
    return {
        "target": str(resolved),
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "files": [str(path) for path in sorted(files)],
    }


def remove_inventory(record: dict[str, object]) -> None:
    target = Path(str(record["target"]))
    expected_files = [Path(str(path)) for path in record["files"]]
    current_files = sorted(path for path in target.rglob("*") if path.is_file())
    if current_files != expected_files:
        raise ValueError("target inventory changed after dry-run")
    for path in expected_files:
        path.unlink()
    directories = sorted(
        (path for path in target.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for path in directories:
        path.rmdir()
    target.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    records = [inventory(raw_target) for raw_target in args.target]
    if args.apply:
        for record in records:
            remove_inventory(record)
    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "records": records,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
