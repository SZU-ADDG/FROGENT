#!/usr/bin/env python3
"""Offline CLI for PLAN forward preregistration, ingestion, and replay."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from frogent_plugin.plan_eval_runner import evaluate_plan_outputs, verify_plan_result  # noqa: E402
from frogent_plugin.plan_eval_assets import (  # noqa: E402
    load_plan_bundle, worker_input_digest, write_contained_exclusive,
)
from frogent_plugin.plan_eval_schema import validate_plan_output  # noqa: E402


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
    bundle = load_plan_bundle(PLUGIN_ROOT, Path(args.manifest))
    if args.command == "validate-preregistration":
        print(json.dumps({"pack_status": bundle.manifest["pack_status"]}, sort_keys=True))
        return 0
    if args.command == "worker-receipt":
        print(worker_input_digest(bundle, args.case, args.profile, args.replicate))
        return 0
    if args.command == "validate-output":
        value = _read_json(args.output)
        validate_plan_output(value, bundle)
        return 0
    if args.command == "ingest":
        value = _read_json(args.output)
        validated = validate_plan_output(value, bundle)
        name = "-".join((validated["case_id"], validated["profile"], validated["replicate_label"])) + ".json"
        write_contained_exclusive(
            PLUGIN_ROOT, Path("evals/plan-forward-v1.outputs") / name,
            _canonical(validated) + "\n",
        )
        return 0
    controlled = [_read_controlled(path) for path in args.outputs]
    values = [item["value"] for item in controlled]
    metadata = [{"identity": item["identity"], "digest": item["digest"]} for item in controlled]
    if args.command == "verify-result":
        expected = _read_json(args.expected)
        verify_plan_result(bundle, values, expected, input_metadata=metadata)
        return 0
    result = evaluate_plan_outputs(bundle, values, input_metadata=metadata)
    write_contained_exclusive(
        PLUGIN_ROOT, Path(args.result), _canonical(result) + "\n"
    )
    return 0


def _read_json(path: str) -> Any:
    return json.loads(_safe_path(path).read_text(encoding="utf-8"))


def _read_controlled(value: str) -> dict[str, Any]:
    path = _safe_path(value)
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {"invalid_json_input": True}
    return {"identity": str(Path(value)), "digest": hashlib.sha256(raw).hexdigest(),
            "value": payload}


def _safe_path(value: str, must_exist: bool = True) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("CLI paths must be relative and contained")
    resolved = (PLUGIN_ROOT / path).resolve(strict=must_exist)
    resolved.relative_to(PLUGIN_ROOT.resolve(strict=True))
    return resolved


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
