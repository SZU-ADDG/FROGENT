#!/usr/bin/env python3
"""Run FROGENT's dependency-free regression and active evaluation checks."""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    from agent.evaluation.eval_manifest import load_bundle
    from agent.evaluation.eval_runner import evaluate_bundle, verify_result

    node = shutil.which("node")
    if node:
        subprocess.run(
            [node, "--check", str(project_root / "app/assets/app.js")],
            cwd=project_root,
            check=True,
        )
    else:
        print("javascript_syntax=SKIP reason=node-unavailable")
    suite = unittest.defaultTestLoader.discover(str(project_root / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    manifest = project_root / "evaluation/cases/research-eval-v1.manifest.json"
    committed = project_root / "evaluation/cases/research-eval-v1.result.json"
    replay = evaluate_bundle(load_bundle(project_root, manifest.relative_to(project_root)))
    expected = json.loads(committed.read_text(encoding="utf-8"))
    verify_result(expected)
    if replay != expected:
        raise ValueError("committed eval result does not match exact replay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
