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


def molecular_planner_schema() -> dict[str, object]:
    return _object({
        "operation": {"type": "string", "enum": ["predict", "compare"]},
        "candidate_kind": {"type": "string", "enum": ["name", "smiles"]},
        "candidate_value": STRING,
        "baseline_kind": {"type": "string", "enum": ["none", "name", "smiles"]},
        "baseline_value": {"type": "string"},
        "candidate_scope": {"type": "string",
                            "enum": ["unspecified", "full", "parent_candidate"]},
        "candidate_structure_smiles": {"type": "string"},
        "candidate_selection_text": {"type": "string"},
        "baseline_scope": {"type": "string",
                           "enum": ["unspecified", "full", "parent_candidate"]},
        "baseline_structure_smiles": {"type": "string"},
        "baseline_selection_text": {"type": "string"},
    })


def design_strategy_schema() -> dict[str, object]:
    basis = {"type": "string", "enum": ["world_knowledge",
        "medicinal_chemistry_judgment", "mechanistic_reasoning", "literature_precedent",
        "computational_signal", "experimental_evidence"]}
    hypothesis = _object({
        "hypothesis_id": STRING,
        "rank": {"type": "integer", "minimum": 1, "maximum": 6},
        "recommendation": STRING,
        "rationale": STRING,
        "expected_benefits": _array(STRING, minimum=1),
        "tradeoffs": _array(STRING, minimum=1),
        "failure_modes": _array(STRING, minimum=1),
        "knowledge_bases": _array(basis, minimum=1),
        "calibration_requests": _array(_object({
            "request_id": STRING,
            "capability_id": {"type": "string", "enum": [
                "molecular.identity", "literature.research", "admet.predict", "admet.compare",
                "docking.score", "sar.analyze", "retrosynthesis.flash",
                "retrosynthesis.explorer", "peptide.docking-score", "experimental.assay"]},
            "purpose": STRING,
            "decision_rule": STRING,
        }), minimum=1),
        "decisive_experiment": STRING,
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    })
    constraint = _object({"text": STRING, "source_turn_id": STRING,
                          "immutable": {"type": "boolean"}})
    handoff = _object({
        "applicable": {"type": "boolean"},
        "objective": {"type": "string"},
        "constraints": _array(STRING),
        "search_space": {"type": "string"},
        "discriminator": {"type": "string"},
        "optimizer": {"type": "string"},
        "stopping_rule": {"type": "string"},
        "residual_qualitative_choices": _array(STRING),
    })
    return _object({
        "objective": STRING,
        "reliable_discriminator": {"type": "boolean"},
        "unresolved_qualitative_choices": {"type": "boolean"},
        "discriminator": {"type": "string"},
        "constraints": _array(constraint),
        "optimization_handoff": handoff,
        "hypotheses": _array(hypothesis, minimum=1, maximum=6),
    })


def docking_planner_schema() -> dict[str, object]:
    return _object({
        "operation": {"type": "string", "enum": ["dock", "dock_and_interactions"]},
        "molecule_kind": {"type": "string", "enum": ["name", "smiles"]},
        "molecule_value": STRING,
        "molecule_scope": {"type": "string",
                           "enum": ["unspecified", "full", "parent_candidate"]},
        "selected_structure_smiles": {"type": "string"},
        "molecule_selection_text": {"type": "string"},
        "selected_microstate_id": {"type": "string"},
        "selected_microstate_smiles": {"type": "string"},
        "microstate_selection_text": {"type": "string"},
        "target_kind": {"type": "string", "enum": ["pdb", "uniprot", "name_candidate"]},
        "target_value": STRING,
        "target_chain": {"type": "string"},
        "target_text": STRING,
        "pocket_id": {"type": "string"},
        "pocket_kind": {"type": "string",
                        "enum": ["none", "residues", "reference_ligand", "artifact"]},
        "pocket_chain": {"type": "string"},
        "numbering_scheme": {"type": "string"},
        "residue_ids": _array(STRING),
        "reference_ligand": {"type": "string"},
        "pocket_artifact_id": {"type": "string"},
        "pocket_artifact_name": {"type": "string"},
        "pocket_artifact_media_type": {"type": "string"},
        "pocket_artifact_uri": {"type": "string"},
        "pocket_text": {"type": "string"},
        "selected_pose_id": {"type": "string"},
        "selected_pose_rank": {"type": "integer", "minimum": 0},
        "pose_selection_text": {"type": "string"},
        "receptor_ph": {"type": "number", "minimum": -1, "maximum": 14},
        "receptor_state_text": {"type": "string"},
    })
