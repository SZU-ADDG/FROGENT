"""Native Codex output schemas for the four structured research roles."""

STRING = {"type": "string", "minLength": 1}
WAVES = ("sentinel", "discovery", "confirmation", "expansion", "challenge", "update")


def _array(items, *, minimum: int = 0, maximum: int | None = None):
    value = {"type": "array", "items": items, "minItems": minimum}
    if maximum is not None:
        value["maxItems"] = maximum
    return value


def _object(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(required or properties), "additionalProperties": False}


def planner_schema(routes: tuple[str, ...], max_queries: int,
                   max_results_per_query: int) -> dict[str, object]:
    capabilities = tuple({"europe_pmc": "europe-pmc.search", "pubmed": "pubmed.search"}[item]
                         for item in routes)
    query = _object({"capability_id": {"type": "string", "enum": list(capabilities)},
                     "source": {"type": "string", "enum": list(routes)},
                     "wave": {"type": "string", "enum": list(WAVES)},
                     "query": STRING, "limit": {"type": "integer", "minimum": 1,
                                                 "maximum": max_results_per_query}})
    candidate = _object({"id": STRING, "kind": STRING, "value": STRING, "claim": STRING,
                         "verification_query": STRING, "pmid": {"type": "string"},
                         "doi": {"type": "string"}})
    return _object({"plan_id": STRING, "question": STRING,
                    "as_of": {"type": "string", "format": "date"},
                    "queries": _array(query, minimum=1, maximum=max_queries),
                    "inclusion_criteria": _array(STRING, minimum=1),
                    "exclusion_criteria": _array(STRING, minimum=1),
                    "stop_rules": _array(STRING, minimum=1),
                    "knowledge_candidates": _array(candidate)})


def reader_schema() -> dict[str, object]:
    claim = _object({"statement": STRING, "locator": STRING, "population_or_model": STRING,
                     "intervention": STRING, "comparator": STRING, "outcome": STRING,
                     "direction": STRING, "magnitude": STRING,
                     "limitations": _array(STRING)})
    return _object({"task_id": STRING, "family_id": STRING, "record_id": STRING,
                    "claims": _array(claim, minimum=1), "counterevidence": {"type": "boolean"},
                    "integrity_status": {"type": "string",
                                         "enum": ["clear", "corrected", "retracted", "uncertain"]},
                    "limitations": _array(STRING),
                    "unresolved_questions": _array(STRING)})


def screener_schema() -> dict[str, object]:
    return _object({"outcome": {"type": "string", "enum": ["include", "exclude", "uncertain"]},
                    "reasons": _array(STRING, minimum=1),
                    "strength": {"type": "string", "enum": ["high", "moderate", "low", "unassessed"]}})


def synthesizer_schema(evidence_ids: tuple[str, ...] = ()) -> dict[str, object]:
    evidence_id = ({"type": "string", "enum": list(evidence_ids)}
                   if evidence_ids else STRING)
    references = _array(evidence_id, maximum=None if evidence_ids else 0)
    return _object({"source_study_answer": STRING, "current_evidence_update": STRING,
                    "citations": references,
                    "counterevidence": dict(references),
                    "gaps": _array(STRING),
                    "limitations": _array(STRING)})


def memory_answer_schema(memory_ids: tuple[str, ...] = ()) -> dict[str, object]:
    memory_id = ({"type": "string", "enum": list(memory_ids)} if memory_ids else STRING)
    supporting = _array(memory_id, maximum=None if memory_ids else 0)
    return _object({"answer": STRING, "supporting_memory_ids": supporting,
                    "abstain": {"type": "boolean"}})
