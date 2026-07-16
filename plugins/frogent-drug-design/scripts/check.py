#!/usr/bin/env python3
"""Run the plugin's dependency-free architecture checks."""

import sys
import unittest
import json
from pathlib import Path

sys.dont_write_bytecode = True


def main() -> int:
    plugin_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(plugin_root))
    from frogent_plugin.eval_manifest import load_bundle
    from frogent_plugin.eval_runner import evaluate_bundle, verify_result
    from frogent_plugin.plan_eval_assets import load_plan_bundle

    suite = unittest.defaultTestLoader.discover(str(plugin_root / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    manifest = plugin_root / "evals" / "research-eval-v1.manifest.json"
    committed = plugin_root / "evals" / "research-eval-v1.result.json"
    replay = evaluate_bundle(load_bundle(plugin_root, manifest.relative_to(plugin_root)))
    expected = json.loads(committed.read_text(encoding="utf-8"))
    verify_result(expected)
    if replay != expected:
        raise ValueError("committed eval result does not match exact replay")
    pending = load_plan_bundle(
        plugin_root, Path("evals/plan-forward-v1.manifest.json")
    )
    if pending.manifest["pack_status"] != "locked":
        raise ValueError("PLAN forward preregistration must remain locked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
