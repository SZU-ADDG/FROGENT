"""Prepare the exposed 52-case Agent capability pack from official sources."""

import hashlib
import io
import json
import math
import os
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping, TextIO

PUBMED_LABELS = ("yes", "no", "maybe")
MEMORY_TYPES = (
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "multi-session",
    "knowledge-update",
    "temporal-reasoning",
)
CANDIDATE_KEYS = {
    "pubmedqa": {"question"},
    "bioasq": {"question"},
    "longmemeval": {"question", "question_date", "sessions"},
}
ORACLE_KEYS = {
    "pubmedqa": {"label", "target_pmids"},
    "bioasq": {"question_type", "gold_documents", "exact_answer", "ideal_answer"},
    "longmemeval": {"answer", "question_type", "answer_session_ids", "abstention"},
}


def prepare_case_pack(pubmedqa_data: str, pubmedqa_oracle: str, bioasq: str,
                      longmemeval: str, seed: int = 17) -> dict[str, object]:
    """Create 36 PubMedQA, two BioASQ, and 14 LongMemEval cases."""
    data = _read_json(pubmedqa_data)
    oracle = _read_json(pubmedqa_oracle)
    bio_data = _read_json(bioasq)
    if not isinstance(data, Mapping) or not isinstance(oracle, Mapping):
        raise ValueError("PubMedQA sources must be JSON objects")
    cases = _pubmed_cases(data, oracle, seed)
    cases.extend(_bioasq_cases(bio_data, seed))
    cases.extend(_memory_cases(longmemeval, seed))
    pack = {"schema_version": 1, "cases": cases}
    validate_case_pack(pack, expected_size=52)
    return pack


def load_case_pack(path: Path, expected_size: int | None = 52) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_case_pack(value, expected_size)
    return value


def select_cases(pack: Mapping[str, object], case_ids: list[str]) -> dict[str, object]:
    validate_case_pack(pack, expected_size=None)
    if not case_ids:
        return dict(pack)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("selected case IDs must be unique")
    selected = {case["case_id"]: case for case in pack["cases"] if case["case_id"] in case_ids}
    missing = set(case_ids) - selected.keys()
    if missing:
        raise ValueError("unknown selected case IDs: " + ", ".join(sorted(missing)))
    return {"schema_version": pack["schema_version"], "cases": [selected[item] for item in case_ids]}


def validate_case_pack(value: object, expected_size: int | None = 52) -> None:
    if not isinstance(value, Mapping) or set(value) != {"schema_version", "cases"}:
        raise ValueError("case pack fields are invalid")
    if value["schema_version"] != 1 or not isinstance(value["cases"], list):
        raise ValueError("case pack schema is invalid")
    cases = value["cases"]
    if expected_size is not None and len(cases) != expected_size:
        raise ValueError(f"case pack must contain exactly {expected_size} cases")
    seen: set[str] = set()
    for case in cases:
        _validate_case(case, seen)


def write_json(path: Path, value: object, root: Path) -> None:
    target = _contained_output(path, root)
    temporary = target.with_name(target.name + ".tmp")
    if temporary.is_symlink():
        raise ValueError("temporary output cannot be a symlink")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def _pubmed_cases(data: Mapping[object, object], oracle: Mapping[object, object],
                  seed: int) -> list[dict[str, object]]:
    buckets: dict[str, list[tuple[str, str]]] = {label: [] for label in PUBMED_LABELS}
    for raw_pmid, raw_label in oracle.items():
        pmid, label = str(raw_pmid), str(raw_label).strip().lower()
        item = data.get(raw_pmid, data.get(pmid))
        question = _field(item, "QUESTION", "question") if isinstance(item, Mapping) else ""
        if label in buckets and question:
            buckets[label].append((pmid, question))
    chosen: list[tuple[str, str, str]] = []
    for label in PUBMED_LABELS:
        ranked = sorted(buckets[label], key=lambda item: _rank(seed, label, item[0]))
        if len(ranked) < 12:
            raise ValueError(f"PubMedQA needs at least 12 {label} test cases")
        chosen.extend((pmid, question, label) for pmid, question in ranked[:12])
    chosen.sort(key=lambda item: _rank(seed, "all", item[0]))
    return [
        {"case_id": f"pubmedqa-{index:03d}", "benchmark": "pubmedqa",
         "candidate_input": {"question": question},
         "oracle": {"label": label, "target_pmids": [pmid]}}
        for index, (pmid, question, label) in enumerate(chosen, 1)
    ]


def _bioasq_cases(value: object, seed: int) -> list[dict[str, object]]:
    items = value.get("questions") if isinstance(value, Mapping) else value
    if not isinstance(items, list):
        raise ValueError("BioASQ source must contain a questions list")
    valid = [item for item in items if isinstance(item, Mapping) and _field(item, "body", "question")]
    ranked = sorted(valid, key=lambda item: _rank(seed, "bioasq", str(item.get("id", ""))))
    if len(ranked) < 2:
        raise ValueError("BioASQ source needs at least two sample questions")
    cases = []
    for index, item in enumerate(ranked[:2], 1):
        question_type = str(item.get("type", "")).lower()
        if question_type not in {"yesno", "factoid", "list", "summary"}:
            raise ValueError("BioASQ question type is invalid")
        cases.append({
            "case_id": f"bioasq-{index:03d}", "benchmark": "bioasq",
            "candidate_input": {"question": _field(item, "body", "question")},
            "oracle": {"question_type": question_type,
                       "gold_documents": _string_list(item.get("documents", []), "BioASQ documents"),
                       "exact_answer": item.get("exact_answer"),
                       "ideal_answer": item.get("ideal_answer")},
        })
    return cases


def _memory_cases(source: str, seed: int) -> list[dict[str, object]]:
    regular: dict[str, list[tuple[bytes, Mapping[str, object]]]] = {key: [] for key in MEMORY_TYPES}
    abstentions: dict[str, list[tuple[bytes, Mapping[str, object]]]] = {key: [] for key in MEMORY_TYPES}
    with _open_text(source) as stream:
        for item in _iter_json_array(stream):
            if not isinstance(item, Mapping):
                raise ValueError("LongMemEval cases must be objects")
            question_type = str(item.get("question_type", ""))
            question_id = str(item.get("question_id", ""))
            if question_type not in regular or not question_id:
                continue
            bucket = abstentions if question_id.endswith("_abs") else regular
            _keep_best(bucket[question_type], (_rank(seed, question_type, question_id), item), 2)
    selected: list[Mapping[str, object]] = []
    for question_type in MEMORY_TYPES:
        if len(regular[question_type]) < 2:
            raise ValueError(f"LongMemEval needs two {question_type} cases")
        selected.extend(item for _, item in sorted(regular[question_type], key=lambda pair: pair[0])[:2])
    available = [key for key in MEMORY_TYPES if abstentions[key]]
    available.sort(key=lambda key: _rank(seed, "abstention-type", key))
    if len(available) < 2:
        raise ValueError("LongMemEval needs abstentions from two question types")
    selected.extend(sorted(abstentions[key], key=lambda pair: pair[0])[0][1] for key in available[:2])
    selected.sort(key=lambda item: _rank(seed, "memory-all", str(item["question_id"])))
    return [_memory_case(item, index) for index, item in enumerate(selected, 1)]


def _memory_case(item: Mapping[str, object], index: int) -> dict[str, object]:
    question = item.get("question")
    answer = _answer_text(item.get("answer"))
    question_type = str(item.get("question_type", ""))
    question_id = str(item.get("question_id", ""))
    if not isinstance(question, str) or not question.strip():
        raise ValueError("LongMemEval question must be text")
    sessions = _memory_sessions(item)
    return {
        "case_id": f"longmemeval-{index:03d}", "benchmark": "longmemeval",
        "candidate_input": {"question": question, "question_date": str(item.get("question_date", "")),
                            "sessions": sessions},
        "oracle": {"answer": answer, "question_type": question_type,
                   "answer_session_ids": _string_list(item.get("answer_session_ids", []),
                                                      "answer session ids"),
                   "abstention": question_id.endswith("_abs")},
    }


def _memory_sessions(item: Mapping[str, object]) -> list[dict[str, object]]:
    sessions = item.get("haystack_sessions")
    ids, dates = item.get("haystack_session_ids"), item.get("haystack_dates")
    if not isinstance(sessions, list) or not isinstance(ids, list) or not isinstance(dates, list):
        raise ValueError("LongMemEval history fields must be lists")
    if len(sessions) != len(ids) or len(sessions) != len(dates):
        raise ValueError("LongMemEval history fields must align")
    clean = []
    for session_id, session_date, turns in zip(ids, dates, sessions):
        if not isinstance(turns, list):
            raise ValueError("LongMemEval session turns must be a list")
        clean_turns = []
        for turn in turns:
            if not isinstance(turn, Mapping) or set(turn).isdisjoint({"role", "content"}):
                raise ValueError("LongMemEval turn is malformed")
            role, content = turn.get("role"), turn.get("content")
            if role not in {"user", "assistant"} or not isinstance(content, str):
                raise ValueError("LongMemEval turn fields are invalid")
            clean_turns.append({"role": role, "content": content})
        clean.append({"session_id": str(session_id), "date": str(session_date), "turns": clean_turns})
    return clean


def _answer_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if type(value) in {int, float} and math.isfinite(value):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    raise ValueError("LongMemEval answer must be text or a finite number")


def _validate_case(case: object, seen: set[str]) -> None:
    if not isinstance(case, Mapping) or set(case) != {"case_id", "benchmark", "candidate_input", "oracle"}:
        raise ValueError("case fields are invalid")
    case_id, benchmark = case["case_id"], case["benchmark"]
    if not isinstance(case_id, str) or not case_id or case_id in seen:
        raise ValueError("case id must be unique non-empty text")
    if benchmark not in CANDIDATE_KEYS:
        raise ValueError("benchmark is invalid")
    candidate, oracle = case["candidate_input"], case["oracle"]
    if not isinstance(candidate, Mapping) or set(candidate) != CANDIDATE_KEYS[benchmark]:
        raise ValueError("candidate fields are invalid or leak evaluator data")
    if not isinstance(oracle, Mapping) or set(oracle) != ORACLE_KEYS[benchmark]:
        raise ValueError("oracle fields are invalid")
    if not isinstance(candidate.get("question"), str) or not candidate["question"].strip():
        raise ValueError("candidate question must be non-empty text")
    seen.add(case_id)


def _field(item: Mapping[object, object], *names: str) -> str:
    for name in names:
        value = item.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _string_list(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a list of text")
    return list(value)


def _rank(seed: int, group: str, identity: str) -> bytes:
    return hashlib.blake2b(f"{seed}:{group}:{identity}".encode(), digest_size=16).digest()


def _keep_best(values: list[tuple[bytes, Mapping[str, object]]], item, limit: int) -> None:
    values.append(item)
    values.sort(key=lambda pair: pair[0])
    del values[limit:]


def _read_json(source: str) -> object:
    with _open_text(source) as stream:
        return json.load(stream)


@contextmanager
def _open_text(source: str) -> Iterator[TextIO]:
    if source.startswith(("https://", "http://")):
        response = urllib.request.urlopen(source, timeout=120)
        wrapper = io.TextIOWrapper(response, encoding="utf-8")
        try:
            yield wrapper
        finally:
            wrapper.close()
        return
    with Path(source).open(encoding="utf-8") as stream:
        yield stream


def _iter_json_array(stream: TextIO, chunk_size: int = 65536) -> Iterator[object]:
    decoder, buffer, started, finished = json.JSONDecoder(), "", False, False
    while not finished:
        chunk = stream.read(chunk_size)
        if chunk:
            buffer += chunk
        else:
            finished = True
        while True:
            buffer = buffer.lstrip()
            if not started:
                if not buffer and not finished:
                    break
                if not buffer.startswith("["):
                    raise ValueError("streamed source must be a JSON array")
                buffer, started = buffer[1:], True
                continue
            buffer = buffer.lstrip()
            if buffer.startswith(","):
                buffer = buffer[1:]
                continue
            if buffer.startswith("]"):
                if buffer[1:].strip():
                    raise ValueError("unexpected data after JSON array")
                return
            if not buffer:
                break
            try:
                value, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                if finished:
                    raise ValueError("streamed JSON array is malformed") from None
                break
            yield value
            buffer = buffer[end:]
    raise ValueError("streamed JSON array is incomplete")


def _contained_output(path: Path, root: Path) -> Path:
    base, target = root.resolve(), path.resolve(strict=False)
    if target != base and base not in target.parents:
        raise ValueError("output path must remain inside plugin root")
    if target.is_symlink():
        raise ValueError("output path cannot be a symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent.resolve() != base and base not in target.parent.resolve().parents:
        raise ValueError("output parent escaped plugin root")
    return target
