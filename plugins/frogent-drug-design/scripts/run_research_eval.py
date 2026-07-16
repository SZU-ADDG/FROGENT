#!/usr/bin/env python3
"""Run or verify the offline research effect eval fixture."""

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin.eval_manifest import load_bundle  # noqa: E402
from frogent_plugin.eval_runner import evaluate_bundle, verify_result  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("evals/research-eval-v1.manifest.json"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-result", type=Path)
    parser.add_argument("--require-promotion", action="store_true")
    args = parser.parse_args()
    if args.verify_result:
        committed = json.loads(_contained(args.verify_result).read_text(encoding="utf-8"))
        replay = evaluate_bundle(load_bundle(PLUGIN_ROOT, args.manifest))
        verify_result(committed, args.require_promotion)
        if replay != committed:
            raise ValueError("committed result differs from asset-bound replay")
        return 0
    result = evaluate_bundle(load_bundle(PLUGIN_ROOT, args.manifest))
    verify_result(result, args.require_promotion)
    rendered = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        _contained(args.output, allow_missing=True).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


def _contained(path: Path, allow_missing: bool = False) -> Path:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("CLI path must be relative to plugin root")
    resolved = (PLUGIN_ROOT / path).resolve(strict=not allow_missing)
    resolved.relative_to(PLUGIN_ROOT)
    return resolved


if __name__ == "__main__":
    raise SystemExit(main())
