"""Behavior tests for the small Agent capability benchmark loop."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.benchmarks.case_pack import (  # noqa: E402
    load_case_pack, prepare_case_pack, select_cases, validate_case_pack,
)
from evaluation.benchmarks.runner import (  # noqa: E402
    _invoke, _invoke_research_service, _ranked_documents, run_cases,
)
from evaluation.benchmarks.scoring import _bioasq_exact, score_results  # noqa: E402


TYPES = (
    "single-session-user", "single-session-assistant", "single-session-preference",
    "multi-session", "knowledge-update", "temporal-reasoning",
)


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _sources(directory: Path):
    pubmed = {}
    oracle = {}
    for label in ("yes", "no", "maybe"):
        for index in range(15):
            pmid = f"{label[0]}{index:02d}"
            pubmed[pmid] = {"QUESTION": f"Question {pmid}?", "CONTEXTS": ["hidden"]}
            oracle[pmid] = label
    bioasq = {"questions": [
        {"id": f"b{index}", "body": f"Bio question {index}?", "type": "yesno",
         "documents": [f"http://www.ncbi.nlm.nih.gov/pubmed/{100 + index}"],
         "exact_answer": "yes", "ideal_answer": ["hidden ideal"]}
        for index in range(3)]}
    memory = []
    for question_type in TYPES:
        for index in range(3):
            memory.append(_memory_item(f"{question_type}-{index}", question_type))
        memory.append(_memory_item(f"{question_type}-0_abs", question_type))
    paths = [directory / name for name in ("pubmed.json", "oracle.json", "bio.json", "memory.json")]
    for path, value in zip(paths, (pubmed, oracle, bioasq, memory)):
        _write(path, value)
    return tuple(str(path) for path in paths)


def _memory_item(question_id: str, question_type: str):
    return {"question_id": question_id, "question_type": question_type,
            "question": f"Remember {question_id}?",
            "answer": 3 if question_type == "multi-session" else f"answer {question_id}",
            "question_date": "2024-01-02", "haystack_session_ids": ["s1"],
            "haystack_dates": ["2024-01-01"],
            "haystack_sessions": [[{"role": "user", "content": "private fact",
                                     "has_answer": True},
                                    {"role": "assistant", "content": "ack"}]],
            "answer_session_ids": ["s1"]}


def _small_pack():
    return {"schema_version": 1, "cases": [
        {"case_id": "p", "benchmark": "pubmedqa", "candidate_input": {"question": "P?"},
         "oracle": {"label": "yes", "target_pmids": ["123"]}},
        {"case_id": "b", "benchmark": "bioasq", "candidate_input": {"question": "B?"},
         "oracle": {"question_type": "yesno", "gold_documents": ["https://pubmed.ncbi.nlm.nih.gov/456/"],
                    "exact_answer": "yes", "ideal_answer": ["hidden"]}},
        {"case_id": "m", "benchmark": "longmemeval",
         "candidate_input": {"question": "M?", "question_date": "2024-01-02", "sessions": []},
         "oracle": {"answer": "Blue car", "question_type": "knowledge-update",
                    "answer_session_ids": ["s"], "abstention": False}},
    ]}


class AgentCapabilityBenchmarkTests(unittest.TestCase):
    def test_prepare_is_deterministic_balanced_and_hides_oracles(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            sources = _sources(Path(temporary))
            first = prepare_case_pack(*sources, seed=29)
            second = prepare_case_pack(*sources, seed=29)
        self.assertEqual(first, second)
        self.assertEqual(52, len(first["cases"]))
        pubmed = [case for case in first["cases"] if case["benchmark"] == "pubmedqa"]
        self.assertEqual({"yes": 12, "no": 12, "maybe": 12},
                         {label: sum(case["oracle"]["label"] == label for case in pubmed)
                          for label in ("yes", "no", "maybe")})
        self.assertTrue(all(set(case["candidate_input"]) == {"question"} for case in pubmed))
        memory = [case for case in first["cases"] if case["benchmark"] == "longmemeval"]
        self.assertEqual(14, len(memory))
        self.assertEqual(2, sum(case["oracle"]["abstention"] for case in memory))
        self.assertEqual(2, len({case["oracle"]["question_type"] for case in memory
                                if case["oracle"]["abstention"]}))
        self.assertEqual({"3"}, {case["oracle"]["answer"] for case in memory
                                 if case["oracle"]["question_type"] == "multi-session"
                                 and not case["oracle"]["abstention"]})
        self.assertNotIn("has_answer", json.dumps([case["candidate_input"] for case in memory]))

    def test_run_passes_only_candidate_input_and_resumes_completed(self):
        pack = _small_pack()
        captured = []

        class Fake:
            def run_case(self, candidate):
                captured.append(candidate)
                return {"answer": "yes", "retrieved_documents": ["PMID:123"],
                        "citations": ["PMID:123"], "provider_calls": 1,
                        "reader_tasks": 2, "wall_time_seconds": 0.5}

        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            output = Path(temporary) / "results.jsonl"
            first = run_cases(pack, Fake(), output, ROOT)
            second = run_cases(pack, Fake(), output, ROOT)
            lines = output.read_text().splitlines()
        self.assertEqual((3, 3), (first["completed"], second["skipped"]))
        self.assertEqual(3, len(lines))
        self.assertEqual([case["candidate_input"] for case in pack["cases"]], captured)
        self.assertTrue(all("oracle" not in value for value in captured))

    def test_scoring_reports_retrieval_answers_memory_citations_and_telemetry(self):
        pack = _small_pack()
        results = [
            _result("p", "pubmedqa", "Yes", ["PMID:123"], ["PMID:123"], None),
            _result("b", "bioasq", "yes", ["https://pubmed.ncbi.nlm.nih.gov/456/"],
                    ["https://pubmed.ncbi.nlm.nih.gov/456/"], 2.0),
            _result("m", "longmemeval", "I remember your blue car.", [], [], 3.0),
        ]
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            path = Path(temporary) / "results.jsonl"
            path.write_text("".join(json.dumps(item) + "\n" for item in results))
            scored = score_results(pack, path)
        aggregate = scored["aggregate"]
        self.assertEqual(1.0, aggregate["pubmedqa"]["accuracy"])
        self.assertEqual(1.0, aggregate["pubmedqa"]["target_pmid_hit_at_1"])
        self.assertEqual(1.0, aggregate["bioasq"]["gold_document_recall_at_10"])
        self.assertEqual(0.0, aggregate["longmemeval"]["normalized_match_accuracy"])
        self.assertEqual(1.0, aggregate["longmemeval"]["normalized_gold_containment"])
        self.assertEqual((6, 3), (aggregate["reader_tasks"], aggregate["provider_calls"]))
        self.assertEqual(2.5, aggregate["wall_time_seconds_p50"])
        self.assertEqual(1.0, aggregate["citations"]["within_retrieved_set_rate"])
        self.assertIn("citation_entailment", scored["not_measured"])

    def test_bioasq_list_answer_accepts_plain_conjunction(self):
        gold = [["phentermine"], ["topiramate"]]
        self.assertTrue(_bioasq_exact("Phentermine and topiramate.", gold, "list"))
        self.assertFalse(_bioasq_exact("Phentermine.", gold, "list"))

    def test_runner_preserves_timeout_and_failure_records(self):
        pack = _small_pack()

        class Fake:
            def run_case(self, candidate):
                if candidate["question"] == "P?":
                    raise TimeoutError("model deadline")
                if candidate["question"] == "B?":
                    raise RuntimeError("provider unavailable")
                return "memory answer"

        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            output = Path(temporary) / "failures.jsonl"
            counts = run_cases(pack, Fake(), output, ROOT)
            records = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual((1, 1, 1), (counts["completed"], counts["failed"], counts["timeout"]))
        self.assertEqual("TimeoutError", records[0]["error"]["type"])
        self.assertEqual("RuntimeError", records[1]["error"]["type"])
        self.assertIn("provider unavailable", records[1]["error"]["message"])

    def test_ranked_documents_use_one_canonical_position_per_first_hit(self):
        records = tuple(SimpleNamespace(id=record_id, identifiers={"pmid": pmid, "doi": doi})
                        for record_id, pmid, doi in (("z", "3", "10.3/z"),
                                                     ("a", "1", "10.1/a"),
                                                     ("b", "2", "10.2/b")))
        hits = tuple(SimpleNamespace(record_id=record_id) for record_id in ("b", "a", "b", "z"))
        checkpoint = SimpleNamespace(records=records, hits=hits)
        self.assertEqual(["2", "1", "3"], _ranked_documents(checkpoint))

    def test_long_memory_uses_chronological_store_api_without_history_stuffing(self):
        calls = []

        class MemoryService:
            def ingest_memory_session(self, user_id, session_id, turns, *, conversation_id=None):
                calls.append(("ingest", user_id, session_id, conversation_id, tuple(turns)))

            def ask_memory(self, user_id, conversation_id, question, *, occurred_at=None):
                calls.append(("ask", user_id, conversation_id, question, occurred_at))
                hit = SimpleNamespace(memory_id="memory:s2:turn-0000")
                return SimpleNamespace(answer="Target", supporting_memory_ids=(hit.memory_id,),
                                       abstain=False, hits=(hit,))

        candidate = {"question": "Where?", "question_date": "2024/01/03 (Wed) 03:00",
                     "sessions": [
                         {"session_id": "s2", "date": "2024/01/02 (Tue) 02:00",
                          "turns": [{"role": "assistant", "content": "Target"}]},
                         {"session_id": "s1", "date": "2024/01/01 (Mon) 01:00",
                          "turns": [{"role": "user", "content": "Context"}]},
                     ]}
        result = _invoke(MemoryService(), "m1", candidate)
        self.assertEqual(["s1", "s2"], [item[2] for item in calls[:2]])
        self.assertTrue(all(item[4][0].occurred_at.endswith("+00:00") for item in calls[:2]))
        self.assertEqual(("ask", "capability-benchmark:m1", "m1-question", "Where?"), calls[2][:4])
        self.assertEqual(["memory:s2:turn-0000"], result["supporting_memory_ids"])
        self.assertNotIn("sessions", result)

    def test_research_service_timeout_identity_is_preserved(self):
        class TimedOutService:
            def stream_payload(self, user_id, payload, *, history=()):
                yield 'data: {"error":"planner deadline","error_type":"TimeoutExpired"}\n\n'
                yield "data: [DONE]\n\n"

        with self.assertRaisesRegex(TimeoutError, "planner deadline"):
            _invoke_research_service(TimedOutService(), "p-timeout", {"question": "P?"})

    def test_malformed_pack_and_results_fail_closed(self):
        pack = _small_pack()
        leaked = json.loads(json.dumps(pack))
        leaked["cases"][0]["candidate_input"]["label"] = "yes"
        with self.assertRaisesRegex(ValueError, "leak evaluator data"):
            validate_case_pack(leaked, expected_size=None)
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            pack_path = Path(temporary) / "pack.json"
            _write(pack_path, pack)
            self.assertEqual(pack, load_case_pack(pack_path, expected_size=None))
            results = Path(temporary) / "bad.jsonl"
            results.write_text('{"case_id":"unknown","status":"completed"}\n')
            with self.assertRaisesRegex(ValueError, "unknown case identity"):
                score_results(pack, results)

    def test_case_selection_is_explicit_ordered_and_fail_closed(self):
        pack = _small_pack()
        selected = select_cases(pack, ["m", "p"])
        self.assertEqual(["m", "p"], [item["case_id"] for item in selected["cases"]])
        with self.assertRaisesRegex(ValueError, "unknown selected"):
            select_cases(pack, ["missing"])
        with self.assertRaisesRegex(ValueError, "must be unique"):
            select_cases(pack, ["p", "p"])


def _result(case_id, benchmark, answer, retrieved, citations, wall):
    return {"case_id": case_id, "benchmark": benchmark, "status": "completed",
            "answer": answer, "retrieved_documents": retrieved, "citations": citations,
            "citation_map": {}, "provider_calls": 1, "reader_tasks": 2,
            "wall_time_seconds": wall, "raw_output": {"answer": answer}}


if __name__ == "__main__":
    unittest.main()
