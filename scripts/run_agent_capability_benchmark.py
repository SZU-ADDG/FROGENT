#!/usr/bin/env python3
"""Prepare, run, and score the small FROGENT Agent capability benchmark."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.benchmarks import (  # noqa: E402
    load_agent_factory,
    load_case_pack,
    prepare_case_pack,
    run_cases,
    score_results,
    select_cases,
    write_json,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    commands = value.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="extract the exposed 52-case pack")
    prepare.add_argument("--pubmedqa-data", required=True)
    prepare.add_argument("--pubmedqa-oracle", required=True)
    prepare.add_argument("--bioasq", required=True)
    prepare.add_argument("--longmemeval", required=True)
    prepare.add_argument("--seed", type=int, default=17)
    prepare.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("run", help="run or resume Agent cases")
    run.add_argument("--pack", type=Path, required=True)
    run.add_argument("--factory", default="frogent",
                     help="'frogent' or a zero-argument module:attribute factory")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--case-id", action="append", default=[], help="run one selected case; repeatable")
    run.add_argument("--retry-failures", action="store_true")
    score = commands.add_parser("score", help="score raw JSONL results")
    score.add_argument("--pack", type=Path, required=True)
    score.add_argument("--results", type=Path, required=True)
    score.add_argument("--output", type=Path)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "prepare":
        pack = prepare_case_pack(args.pubmedqa_data, args.pubmedqa_oracle, args.bioasq,
                                 args.longmemeval, args.seed)
        write_json(args.output, pack, ROOT)
        print(json.dumps({"cases": len(pack["cases"]), "output": str(args.output)}))
    elif args.command == "run":
        pack = select_cases(load_case_pack(args.pack), args.case_id)
        counts = run_cases(pack, load_agent_factory(args.factory), args.output, ROOT,
                           args.retry_failures)
        print(json.dumps(counts, sort_keys=True))
    else:
        pack = load_case_pack(args.pack)
        scored = score_results(pack, args.results)
        if args.output:
            write_json(args.output, scored, ROOT)
        else:
            print(json.dumps(scored, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
