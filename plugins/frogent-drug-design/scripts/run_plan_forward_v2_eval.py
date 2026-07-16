#!/usr/bin/env python3
"""Offline CLI for PLAN forward v2 preregistration and exact replay."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin.plan_eval_v2_assets import (  # noqa: E402
    load_plan_v2_bundle, worker_receipt,
)
from frogent_plugin.plan_eval_v2_runner import evaluate_plan_outputs, verify_plan_result  # noqa: E402
from frogent_plugin.plan_eval_v2_schema import validate_plan_output  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prereg = commands.add_parser("validate-preregistration")
    prereg.add_argument("manifest")
    receipt = commands.add_parser("worker-receipt")
    receipt.add_argument("manifest")
    receipt.add_argument("--case", required=True, choices=("PLAN-01", "PLAN-02"))
    receipt.add_argument("--profile", required=True, choices=("no_skill", "single_skill"))
    receipt.add_argument("--replicate", required=True, choices=("17", "29", "43"))
    output = commands.add_parser("validate-output")
    output.add_argument("manifest")
    output.add_argument("output")
    ingest = commands.add_parser("ingest")
    ingest.add_argument("manifest")
    ingest.add_argument("output")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("manifest")
    evaluate.add_argument("outputs", nargs="+")
    evaluate.add_argument("--result", required=True)
    verify = commands.add_parser("verify-result")
    verify.add_argument("manifest")
    verify.add_argument("outputs", nargs="+")
    verify.add_argument("--expected", required=True)
    args = parser.parse_args()
    bundle = load_plan_v2_bundle(PLUGIN_ROOT, Path(args.manifest))
    if args.command == "validate-preregistration":
        print(_canonical({"pack_status": bundle.manifest["pack_status"], "fresh_workers": 0,
                          "effect_outcome": "not_evaluated", "promotion_eligible": False}))
        return 0
    if args.command == "worker-receipt":
        print(_canonical(worker_receipt(bundle, args.case, args.profile, args.replicate)))
        return 0
    if args.command == "validate-output":
        validate_plan_output(_read_json(args.output), bundle)
        return 0
    if args.command == "ingest":
        value = validate_plan_output(_read_json(args.output), bundle)
        name = "-".join((value["case_id"], value["profile"], value["replicate_label"])) + ".json"
        _write_exclusive(Path("evals/plan-forward-v2.outputs") / name, _canonical(value) + "\n")
        return 0
    controlled = [_read_controlled(path) for path in args.outputs]
    values = [item["value"] for item in controlled]
    metadata = [{"identity": item["identity"], "digest": item["digest"]} for item in controlled]
    if args.command == "verify-result":
        verify_plan_result(bundle, values, _read_json(args.expected), input_metadata=metadata)
        return 0
    result = evaluate_plan_outputs(bundle, values, input_metadata=metadata)
    _write_exclusive(Path(args.result), _canonical(result) + "\n")
    return 0


def _read_json(value: str) -> Any:
    return json.loads(_safe_path(Path(value)).read_text(encoding="utf-8"))


def _read_controlled(value: str) -> dict[str, Any]:
    raw = _safe_path(Path(value)).read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {"invalid_json_input": True}
    return {"identity": str(Path(value)), "digest": hashlib.sha256(raw).hexdigest(), "value": payload}


def _safe_path(path: Path, must_exist: bool = True) -> Path:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("CLI paths must be relative and contained")
    resolved = (PLUGIN_ROOT / path).resolve(strict=must_exist)
    resolved.relative_to(PLUGIN_ROOT.resolve(strict=True))
    return resolved


def _write_exclusive(path: Path, content: str) -> None:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("output path must be relative and contained")
    parent = _contained_directory(path.parent)
    target = parent / path.name
    if target.is_symlink():
        raise ValueError("output leaf cannot be a symlink")
    try:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise ValueError("output leaf already exists") from exc


def _contained_directory(path: Path) -> Path:
    existing = _safe_path(path.parent)
    target = existing / path.name
    if target.is_symlink():
        raise ValueError("output directory cannot be a symlink")
    target.mkdir(exist_ok=True)
    target.resolve(strict=True).relative_to(PLUGIN_ROOT.resolve(strict=True))
    return target


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
