"""Deterministic metrics for the exposed Agent capability pack."""

import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Mapping

from .case_pack import validate_case_pack


def score_results(pack: Mapping[str, object], results_path: Path) -> dict[str, object]:
    validate_case_pack(pack, expected_size=None)
    cases = {case["case_id"]: case for case in pack["cases"]}
    results = _latest_results(results_path, cases)
    per_case = [_score_case(case, results.get(case_id)) for case_id, case in cases.items()]
    return {"schema_version": 1, "per_case": per_case, "aggregate": _aggregate(per_case),
            "not_measured": {
                "bioasq_ideal_answer_semantic_quality": "requires an independent semantic judge",
                "longmemeval_semantic_correctness": "requires the official judge or an independent judge",
                "citation_entailment": "identifier checks cannot establish claim support",
                "cost": "runtime output does not expose a common cost field",
            }}


def _score_case(case: Mapping[str, object], result: Mapping[str, object] | None) -> dict[str, object]:
    benchmark, oracle = case["benchmark"], case["oracle"]
    status = "missing" if result is None else result["status"]
    scored = {"case_id": case["case_id"], "benchmark": benchmark, "status": status,
              "metrics": {}, "error": None if result is None else result.get("error")}
    if status != "completed":
        return scored
    answer = result.get("answer", "")
    retrieved = result.get("retrieved_documents", [])[:10]
    citations = result.get("citations", [])
    citation_map = result.get("citation_map", {})
    scored["metrics"].update(_citation_metrics(citations, citation_map, retrieved))
    scored["metrics"].update({"provider_calls": result.get("provider_calls", 0),
                              "reader_tasks": result.get("reader_tasks", 0),
                              "wall_time_seconds": result.get("wall_time_seconds")})
    if benchmark == "pubmedqa":
        predicted = _answer_label(answer)
        targets = {_identifier(value) for value in oracle["target_pmids"]}
        ranked = [_identifier(value) for value in retrieved]
        scored["metrics"].update({"gold_label": oracle["label"], "predicted_label": predicted,
                                  "answer_correct": predicted == oracle["label"],
                                  "target_pmid_hit_at_1": bool(targets & set(ranked[:1])),
                                  "target_pmid_hit_at_5": bool(targets & set(ranked[:5])),
                                  "target_pmid_hit_at_10": bool(targets & set(ranked[:10]))})
    elif benchmark == "bioasq":
        gold = {_identifier(value) for value in oracle["gold_documents"]}
        found = gold & {_identifier(value) for value in retrieved}
        exact = _bioasq_exact(answer, oracle["exact_answer"], oracle["question_type"])
        scored["metrics"].update({"gold_document_recall_at_10": _ratio(len(found), len(gold)),
                                  "exact_answer_correct": exact})
    else:
        gold = oracle["answer"]
        normalized_answer, normalized_gold = _normalize(answer), _normalize(gold)
        scored["metrics"].update({"question_type": oracle["question_type"],
                                  "abstention": oracle["abstention"],
                                  "exact_match": answer.strip().casefold() == gold.strip().casefold(),
                                  "normalized_match": normalized_answer == normalized_gold,
                                  "normalized_gold_containment": bool(
                                      normalized_gold and normalized_gold in normalized_answer)})
    return scored


def _aggregate(per_case: list[Mapping[str, object]]) -> dict[str, object]:
    statuses = {key: sum(item["status"] == key for item in per_case)
                for key in ("completed", "failed", "timeout", "missing")}
    completed = [item for item in per_case if item["status"] == "completed"]
    pubmed = [item for item in completed if item["benchmark"] == "pubmedqa"]
    bioasq = [item for item in completed if item["benchmark"] == "bioasq"]
    memory = [item for item in completed if item["benchmark"] == "longmemeval"]
    wall_times = [item["metrics"]["wall_time_seconds"] for item in completed
                  if isinstance(item["metrics"].get("wall_time_seconds"), (int, float))]
    aggregate = {"case_count": len(per_case), "status_counts": statuses,
                 "completion_rate": _ratio(statuses["completed"], len(per_case)),
                 "failure_rate": _ratio(statuses["failed"], len(per_case)),
                 "timeout_rate": _ratio(statuses["timeout"], len(per_case)),
                 "provider_calls": sum(item["metrics"].get("provider_calls", 0) for item in completed),
                 "reader_tasks": sum(item["metrics"].get("reader_tasks", 0) for item in completed),
                 "wall_time_seconds_p50": _percentile(wall_times, 0.50),
                 "wall_time_seconds_p95": _percentile(wall_times, 0.95)}
    aggregate["pubmedqa"] = _pubmed_aggregate(pubmed)
    aggregate["bioasq"] = {"measured_cases": len(bioasq),
                            "gold_document_recall_at_10": _mean_metric(bioasq, "gold_document_recall_at_10"),
                            "exact_answer_accuracy": _mean_metric(bioasq, "exact_answer_correct")}
    aggregate["longmemeval"] = _memory_aggregate(memory)
    aggregate["citations"] = {"resolvable_rate": _sum_ratio(completed, "citations_resolvable"),
                               "within_retrieved_set_rate": _sum_ratio(completed,
                                                                        "citations_within_retrieved_set")}
    return aggregate


def _pubmed_aggregate(items: list[Mapping[str, object]]) -> dict[str, object]:
    metrics = [item["metrics"] for item in items]
    return {"measured_cases": len(items), "accuracy": _mean_metric(items, "answer_correct"),
            "macro_f1": _macro_f1(metrics),
            "target_pmid_hit_at_1": _mean_metric(items, "target_pmid_hit_at_1"),
            "target_pmid_hit_at_5": _mean_metric(items, "target_pmid_hit_at_5"),
            "target_pmid_hit_at_10": _mean_metric(items, "target_pmid_hit_at_10")}


def _memory_aggregate(items: list[Mapping[str, object]]) -> dict[str, object]:
    types = sorted({item["metrics"]["question_type"] for item in items})
    return {"measured_cases": len(items), "exact_match_accuracy": _mean_metric(items, "exact_match"),
            "normalized_match_accuracy": _mean_metric(items, "normalized_match"),
            "normalized_gold_containment": _mean_metric(items, "normalized_gold_containment"),
            "per_type_accuracy": {
                question_type: _mean_metric(
                    [item for item in items if item["metrics"]["question_type"] == question_type],
                    "normalized_match") for question_type in types}}


def _citation_metrics(citations: object, citation_map: object,
                      retrieved: object) -> dict[str, object]:
    values = citations if isinstance(citations, list) else []
    mappings = citation_map if isinstance(citation_map, Mapping) else {}
    retrieved_ids = {_identifier(value) for value in retrieved if isinstance(value, str)}
    resolvable = within = 0
    for citation in values:
        if not isinstance(citation, str):
            continue
        target = mappings.get(citation, citation)
        canonical = _identifier(target) if isinstance(target, str) else ""
        resolvable += bool(canonical and (_persistent_identifier(canonical) or citation in mappings))
        within += bool(canonical and canonical in retrieved_ids)
    return {"citations_resolvable": {"numerator": resolvable, "denominator": len(values)},
            "citations_within_retrieved_set": {"numerator": within, "denominator": len(values)}}


def _bioasq_exact(answer: str, gold: object, question_type: str) -> bool | None:
    if question_type == "summary" or gold is None:
        return None
    if question_type == "yesno":
        return _normalize(answer) == _normalize(str(gold))
    groups = _answer_groups(gold)
    if not groups:
        return None
    if question_type == "factoid":
        return _normalize(answer) in set().union(*groups)
    candidates = {_normalize(item) for item in re.split(r"[,;\n]+|\band\b", answer,
                                                        flags=re.IGNORECASE) if _normalize(item)}
    return len(candidates) == len(groups) and all(candidates & group for group in groups)


def _answer_groups(value: object) -> list[set[str]]:
    if isinstance(value, str):
        return [{_normalize(value)}]
    if not isinstance(value, list):
        return []
    groups = []
    for item in value:
        values = item if isinstance(item, list) else [item]
        group = {_normalize(str(alias)) for alias in values if isinstance(alias, str)}
        if group:
            groups.append(group)
    return groups


def _latest_results(path: Path, cases: Mapping[str, Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    results = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"result line {line_number} is invalid JSON") from exc
        if not isinstance(value, Mapping) or value.get("case_id") not in cases:
            raise ValueError(f"result line {line_number} has unknown case identity")
        if value.get("status") not in {"completed", "failed", "timeout"}:
            raise ValueError(f"result line {line_number} has invalid status")
        _validate_result(value, cases[value["case_id"]], line_number)
        results[value["case_id"]] = value
    return results


def _validate_result(value: Mapping[str, object], case: Mapping[str, object], line_number: int) -> None:
    if value.get("benchmark") != case["benchmark"] or not isinstance(value.get("answer"), str):
        raise ValueError(f"result line {line_number} has invalid benchmark or answer")
    for key in ("retrieved_documents", "citations"):
        items = value.get(key)
        if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
            raise ValueError(f"result line {line_number} has invalid {key}")
    citation_map = value.get("citation_map")
    if not isinstance(citation_map, Mapping) or any(not isinstance(key, str) or not isinstance(item, str)
                                                    for key, item in citation_map.items()):
        raise ValueError(f"result line {line_number} has invalid citation map")
    for key in ("provider_calls", "reader_tasks"):
        count = value.get(key)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(f"result line {line_number} has invalid {key}")
    wall = value.get("wall_time_seconds")
    if wall is not None and (not isinstance(wall, (int, float)) or isinstance(wall, bool) or wall < 0):
        raise ValueError(f"result line {line_number} has invalid wall time")


def _answer_label(answer: str) -> str:
    matches = re.findall(r"\b(yes|no|maybe)\b", answer.casefold())
    return matches[0] if matches else ""


def _macro_f1(metrics: list[Mapping[str, object]]) -> float | None:
    if not metrics:
        return None
    values = []
    for label in ("yes", "no", "maybe"):
        true_positive = sum(item["gold_label"] == label and item["predicted_label"] == label
                            for item in metrics)
        false_positive = sum(item["gold_label"] != label and item["predicted_label"] == label
                             for item in metrics)
        false_negative = sum(item["gold_label"] == label and item["predicted_label"] != label
                             for item in metrics)
        denominator = 2 * true_positive + false_positive + false_negative
        values.append(0.0 if denominator == 0 else 2 * true_positive / denominator)
    return sum(values) / len(values)


def _identifier(value: str) -> str:
    text = value.strip().casefold().rstrip(".,;)]}")
    pmid = re.search(r"(?:pmid[:/\s]|pubmed/)(\d+)", text)
    if pmid:
        return "pmid:" + pmid.group(1)
    if text.isdigit():
        return "pmid:" + text
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    if re.match(r"^10\.\d{4,9}/", text):
        return "doi:" + text
    return text


def _persistent_identifier(value: str) -> bool:
    return value.startswith(("pmid:", "doi:", "http://", "https://"))


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    text = re.sub(r"[^\w]+", " ", text)
    return " ".join(part for part in text.split() if part not in {"a", "an", "the"})


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _mean_metric(items: list[Mapping[str, object]], key: str) -> float | None:
    values = [item["metrics"].get(key) for item in items]
    measured = [float(value) for value in values if isinstance(value, (int, float, bool))]
    return None if not measured else sum(measured) / len(measured)


def _sum_ratio(items: list[Mapping[str, object]], key: str) -> float | None:
    ratios = [item["metrics"].get(key) for item in items]
    numerator = sum(item["numerator"] for item in ratios if isinstance(item, Mapping))
    denominator = sum(item["denominator"] for item in ratios if isinstance(item, Mapping))
    return _ratio(numerator, denominator)


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)
