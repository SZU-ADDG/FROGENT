#!/usr/bin/env python3
"""Run and score the frozen foundational-knowledge exposed-case panel."""

import csv
import json
import math
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))

from agent.llm.codex_client import CodexClient  # noqa: E402


RUN_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "runtime/evaluation/revision-20260804/source-material/"
          "eight-task-benchmark-r01/extracted/test_data1.csv")
SCHEMA = json.loads((RUN_ROOT / "protocol/schema.json").read_text(encoding="utf-8"))
RAW = RUN_ROOT / "raw"
OUTPUT = RUN_ROOT / "output"
LOCK = threading.Lock()


def _normalize(value: str, answer_type: str) -> str:
    text = " ".join(value.strip().split())
    if answer_type == "multipleChoice":
        labels = re.findall(r"[A-Z]", text.upper())
        return "/".join(sorted(dict.fromkeys(labels)))
    return text.casefold()


def _run_case(row: dict[str, str]) -> dict[str, object]:
    index = int(row["index"])
    path = RAW / f"case-{index:02d}.json"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    client = CodexClient(ROOT, model="gpt-5.6-luna", reasoning_effort="max", timeout=None)
    payload = {
        "case_index": index,
        "question": row["question"],
        "answer_type": row["answer_type"],
        "format_instruction": (
            "For multipleChoice return only the option label or slash-separated labels in "
            "final_answer. For exactMatch return the shortest exact answer."
        ),
    }
    record: dict[str, object] = {
        "case_index": index,
        "answer_type": row["answer_type"],
        "status": "failed",
    }
    try:
        value = client.generate(
            "FROGENT foundational biomedical knowledge solver",
            "Answer the supplied case independently. Do not infer or request a hidden gold answer.",
            payload,
            schema=SCHEMA,
            cwd=RUN_ROOT,
        )
        record.update({"status": "succeeded", "response": value})
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    with LOCK:
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    return record


def _wilson(successes: int, total: int) -> list[float]:
    if total == 0:
        return [math.nan, math.nan]
    z = 1.959963984540054
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return [center - radius, center + radius]


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    final_path = OUTPUT / "summary.json"
    if final_path.exists():
        raise FileExistsError(f"refusing to overwrite {final_path}")
    with SOURCE.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 20 or [int(row["index"]) for row in rows] != list(range(1, 21)):
        raise ValueError("frozen source must contain source-ordered indices 1..20")
    completed: dict[int, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_run_case, row): int(row["index"]) for row in rows}
        for future in as_completed(futures):
            result = future.result()
            completed[int(result["case_index"])] = result
            print(json.dumps({"case_index": result["case_index"], "status": result["status"]}),
                  flush=True)
    per_case = []
    for row in rows:
        result = completed[int(row["index"])]
        prediction = ""
        if result["status"] == "succeeded":
            prediction = str(result["response"]["final_answer"])
        correct = (_normalize(prediction, row["answer_type"])
                   == _normalize(row["answer"], row["answer_type"]))
        per_case.append({
            "case_index": int(row["index"]),
            "answer_type": row["answer_type"],
            "status": result["status"],
            "prediction": prediction,
            "gold": row["answer"],
            "correct": correct,
            "confidence": (result.get("response") or {}).get("confidence"),
        })
    successes = sum(item["status"] == "succeeded" for item in per_case)
    correct = sum(item["correct"] for item in per_case)
    summary = {
        "schema_version": "frogent-eight-task-foundational-result-v1",
        "status": "complete" if successes == len(rows) else "complete_with_call_failures",
        "attempted_cases": len(rows),
        "successful_calls": successes,
        "exact_correct": correct,
        "exact_accuracy": correct / len(rows),
        "wilson_95_ci": _wilson(correct, len(rows)),
        "per_case": per_case,
        "claim_boundary": "post_hoc_author_supplied_exposed_no_tool_luna_max_arm",
    }
    final_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if successes == len(rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
