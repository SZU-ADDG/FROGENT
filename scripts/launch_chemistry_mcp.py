#!/usr/bin/env python3
"""Launch the chemistry MCP with an interpreter that can import RDKit."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp/chemistry_mcp.py"


def _supports_rdkit(executable: str) -> bool:
    completed = subprocess.run(
        [executable, "-c", "import rdkit"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
        check=False,
    )
    return completed.returncode == 0


def main() -> int:
    candidates = (
        os.environ.get("FROGENT_CHEMISTRY_PYTHON"),
        shutil.which("python"),
        sys.executable,
        shutil.which("python3"),
    )
    checked = []
    for candidate in candidates:
        if not candidate or candidate in checked:
            continue
        checked.append(candidate)
        if _supports_rdkit(candidate):
            os.execv(candidate, [candidate, str(SERVER)])
    sys.stderr.write(
        "No Python interpreter with RDKit is available; set FROGENT_CHEMISTRY_PYTHON.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
