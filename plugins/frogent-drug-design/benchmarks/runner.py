"""Incremental runner for the exposed Agent capability pack."""

import importlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .case_pack import _contained_output, validate_case_pack


def load_agent_factory(specification: str):
    if specification == "frogent":
        from frogent_plugin.research_factory import RuntimeConfig, build_research_service

        plugin_root = Path(__file__).resolve().parents[1]
        return build_research_service(RuntimeConfig.from_env(plugin_root))
    module_name, separator, attribute_name = specification.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("factory must use module:attribute syntax")
    factory = getattr(importlib.import_module(module_name), attribute_name)
    return factory()


def run_cases(pack: Mapping[str, object], agent, output_path: Path, root: Path,
              retry_failures: bool = False) -> dict[str, int]:
    validate_case_pack(pack, expected_size=None)
    target = _contained_output(output_path, root)
    previous = _load_results(target) if target.exists() else {}
    counts = {"completed": 0, "failed": 0, "timeout": 0, "skipped": 0}
    with target.open("a", encoding="utf-8") as stream:
        for case in pack["cases"]:
            case_id = case["case_id"]
            prior = previous.get(case_id)
            if prior and (prior["status"] == "completed" or not retry_failures):
                counts["skipped"] += 1
                continue
            candidate = json.loads(json.dumps(case["candidate_input"], ensure_ascii=False))
            record = _run_one(agent, case_id, case["benchmark"], candidate)
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            counts[record["status"]] += 1
    return counts


def _run_one(agent, case_id: str, benchmark: str,
             candidate: Mapping[str, object]) -> dict[str, object]:
    started = time.monotonic()
    try:
        raw = _invoke(agent, case_id, candidate)
        elapsed = time.monotonic() - started
        return _normal_result(case_id, benchmark, raw, elapsed)
    except TimeoutError as exc:
        return _error_result(case_id, benchmark, "timeout", exc, time.monotonic() - started)
    except Exception as exc:
        return _error_result(case_id, benchmark, "failed", exc, time.monotonic() - started)


def _invoke(agent, case_id: str, candidate: Mapping[str, object]) -> object:
    if hasattr(agent, "run_case"):
        return agent.run_case(candidate)
    if callable(agent):
        return agent(candidate)
    if "sessions" in candidate and hasattr(agent, "ingest_memory_session") and hasattr(agent, "ask_memory"):
        return _invoke_memory_service(agent, case_id, candidate)
    if hasattr(agent, "stream_payload"):
        return _invoke_research_service(agent, case_id, candidate)
    raise TypeError("agent must be callable, expose run_case, or expose stream_payload")


def _invoke_research_service(service, case_id: str, candidate: Mapping[str, object]) -> dict[str, object]:
    history = _history(candidate.get("sessions", []))
    payload = {"message": candidate["question"], "chat_id": case_id, "files": []}
    user_id = "capability-benchmark:" + case_id
    frames = tuple(service.stream_payload(user_id, payload, history=history))
    answer, error, error_type = "", "", ""
    for frame in frames:
        if not frame.startswith("data: {"):
            continue
        value = json.loads(frame[6:])
        answer = str(value.get("content") or answer)
        error = str(value.get("error") or error)
        error_type = str(value.get("error_type") or error_type)
    if error:
        if error_type in {"TimeoutError", "TimeoutExpired"}:
            raise TimeoutError(error)
        raise RuntimeError(error)
    saved = service.store.load(user_id, case_id)
    retrieved, citation_map, provider_calls, reader_tasks = [], {}, 0, 0
    if saved is not None:
        provider_calls, reader_tasks = saved.checkpoint.provider_calls, saved.checkpoint.reader_tasks
        retrieved = _ranked_documents(saved.checkpoint)
        citation_map = {str(item["id"]): str(item["record_id"])
                        for item in saved.admitted_evidence
                        if isinstance(item, Mapping) and "id" in item and "record_id" in item}
    citations = re.findall(r"\b(?:PMID\s*:\s*\d+|10\.\d{4,9}/\S+|ev-[\w.-]+)\b", answer,
                           flags=re.IGNORECASE)
    return {"answer": answer, "retrieved_documents": retrieved,
            "citations": citations, "citation_map": citation_map, "provider_calls": provider_calls,
            "reader_tasks": reader_tasks}


def _invoke_memory_service(service, case_id: str,
                           candidate: Mapping[str, object]) -> dict[str, object]:
    from frogent_plugin.cross_chat_memory import turn

    user_id = "capability-benchmark:" + case_id
    sessions = candidate.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError("memory sessions must be a list")
    ordered = sorted(enumerate(sessions), key=lambda item: (str(item[1].get("date", "")), item[0]))
    for _, session in ordered:
        if not isinstance(session, Mapping) or not isinstance(session.get("turns"), list):
            raise ValueError("memory session is malformed")
        session_id = str(session.get("session_id") or "")
        timestamp = _memory_timestamp(str(session.get("date") or ""))
        turns = tuple(turn(f"turn-{index:04d}", str(item.get("role") or ""),
                           str(item.get("content") or ""), timestamp)
                      for index, item in enumerate(session["turns"]))
        service.ingest_memory_session(user_id, session_id, turns, conversation_id=session_id)
    response = service.ask_memory(user_id, case_id + "-question", str(candidate["question"]),
                                  occurred_at=_memory_timestamp(str(candidate.get("question_date") or "")))
    return {"answer": response.answer, "retrieved_documents": [], "citations": [],
            "citation_map": {}, "provider_calls": 0, "reader_tasks": 0,
            "memory_hits": [item.memory_id for item in response.hits],
            "supporting_memory_ids": list(response.supporting_memory_ids),
            "abstain": response.abstain}


def _memory_timestamp(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y/%m/%d (%a) %H:%M")
    except ValueError as exc:
        raise ValueError("memory date must match LongMemEval format") from exc
    return parsed.replace(tzinfo=timezone.utc).isoformat()


def _ranked_documents(checkpoint) -> list[str]:
    records = {item.id: item for item in checkpoint.records}
    ordered_ids = [item.record_id for item in checkpoint.hits]
    ordered_ids = ordered_ids or [item.id for item in checkpoint.records]
    result = []
    for record_id in ordered_ids:
        record = records.get(record_id)
        identifier = ((record.identifiers.get("pmid") or record.identifiers.get("doi"))
                      if record is not None else None) or record_id
        if identifier not in result:
            result.append(identifier)
    return result


def _history(sessions: object) -> list[dict[str, object]]:
    if not isinstance(sessions, list):
        return []
    history = []
    for session in sessions:
        if not isinstance(session, Mapping):
            continue
        for turn in session.get("turns", []):
            if isinstance(turn, Mapping):
                history.append({"isUser": turn.get("role") == "user",
                                "content": str(turn.get("content", ""))})
    return history


def _normal_result(case_id: str, benchmark: str, raw: object,
                   measured_elapsed: float) -> dict[str, object]:
    if isinstance(raw, str):
        raw = {"answer": raw}
    if not isinstance(raw, Mapping):
        raise ValueError("agent output must be text or an object")
    status = raw.get("status", "completed")
    if status not in {"completed", "failed", "timeout"}:
        raise ValueError("agent status is invalid")
    answer = raw.get("answer", "")
    if not isinstance(answer, str):
        raise ValueError("agent answer must be text")
    retrieved = _text_list(raw.get("retrieved_documents", raw.get("retrieved_ids", [])),
                           "retrieved documents")
    citations = _text_list(raw.get("citations", []), "citations")
    citation_map = raw.get("citation_map", {})
    if not isinstance(citation_map, Mapping) or any(not isinstance(key, str) or not isinstance(value, str)
                                                    for key, value in citation_map.items()):
        raise ValueError("citation map must map text to text")
    record = {"case_id": case_id, "benchmark": benchmark, "status": status,
              "answer": answer, "retrieved_documents": retrieved, "citations": citations,
              "citation_map": dict(citation_map),
              "provider_calls": _count(raw.get("provider_calls", 0), "provider calls"),
              "reader_tasks": _count(raw.get("reader_tasks", 0), "reader tasks"),
              "wall_time_seconds": _duration(raw.get("wall_time_seconds", measured_elapsed)),
              "raw_output": dict(raw)}
    if status != "completed":
        record["error"] = str(raw.get("error", "agent reported unsuccessful status"))
    json.dumps(record, ensure_ascii=False)
    return record


def _error_result(case_id: str, benchmark: str, status: str, exc: Exception,
                  elapsed: float) -> dict[str, object]:
    return {"case_id": case_id, "benchmark": benchmark, "status": status, "answer": "",
            "retrieved_documents": [], "citations": [], "citation_map": {},
            "provider_calls": 0, "reader_tasks": 0, "wall_time_seconds": elapsed,
            "raw_output": None, "error": {"type": type(exc).__name__, "message": str(exc)}}


def _load_results(path: Path) -> dict[str, Mapping[str, object]]:
    results = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"result line {line_number} is invalid JSON") from exc
        if not isinstance(value, Mapping) or not isinstance(value.get("case_id"), str):
            raise ValueError(f"result line {line_number} is malformed")
        if value.get("status") not in {"completed", "failed", "timeout"}:
            raise ValueError(f"result line {line_number} has invalid status")
        results[value["case_id"]] = value
    return results


def _text_list(value: object, name: str) -> list[str]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a list of text")
    return list(value)


def _count(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _duration(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValueError("wall time must be non-negative")
    return float(value)
