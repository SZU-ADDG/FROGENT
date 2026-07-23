"""Evidence-bound molecular chat execution, rendering, and typed events."""

import re
from dataclasses import dataclass

from agent.molecular.admet_execution import ADMETPredictor
from agent.molecular.admet_workflow import ADMETWorkflowResult, run_prepared_admet
from agent.core.contracts import ExecutionContext, StreamEvent
from agent.molecular.molecular_binding import MolecularInputBinding
from agent.molecular.molecular_chat_plan import CodexMolecularPlanner, MolecularChatEntity, MolecularChatPlan
from agent.molecular.molecular_routing import prepare_molecular_request
from agent.molecular.pubchem_identity import PubChemIdentityResolver, PubChemResolution


_ADMET_ACTIONS = ("run ", "predict", "calculate", "estimate", "compare", "evaluate",
                  "运行", "执行", "预测", "计算", "估算", "估计", "比较", "对比", "评估", "评价")
_RESEARCH_MARKERS = ("literature", "paper", "publication", "search",
                     "文献", "论文", "出版物", "检索", "搜索", "查找")


@dataclass(frozen=True, slots=True)
class MolecularVerification:
    role: str
    binding: MolecularInputBinding
    resolution: PubChemResolution


@dataclass(frozen=True, slots=True)
class MolecularChatResult:
    answer: str
    events: tuple[StreamEvent, ...]
    plan: MolecularChatPlan | None = None
    workflow: ADMETWorkflowResult | None = None
    verifications: tuple[MolecularVerification, ...] = ()


class MolecularChatHandler:
    def __init__(self, planner: CodexMolecularPlanner, resolver: PubChemIdentityResolver,
                 predictor: ADMETPredictor) -> None:
        self.planner, self.resolver, self.predictor = planner, resolver, predictor

    def run(self, message: str, context: ExecutionContext) -> MolecularChatResult:
        events = [StreamEvent("tool.started", {"capability_id": "molecular.plan"}, "molecular")]
        try:
            plan = self.planner.plan(message)
        except Exception as exc:
            return _safe_failure(events, "planning", exc)
        events.append(StreamEvent("tool.completed", _plan_payload(plan), "molecular"))
        events.append(StreamEvent("tool.started", {"capability_id": "pubchem.identity",
            "roles": [role for role, _ in _entities(plan)]}, "molecular"))
        seeds, seed_gaps = self._seeds(plan)
        if seed_gaps:
            events.append(StreamEvent("tool.completed", {"capability_id": "pubchem.identity",
                "status": "coverage_gap", "coverage_gaps": list(seed_gaps)}, "molecular"))
            return _safe_gap(events, plan, seed_gaps)
        try:
            intake = _intake(plan, seeds, self.resolver)
        except Exception as exc:
            return _safe_failure(events, "molecular_intake", exc, plan)
        verifications = self._verify(intake, plan, seeds)
        events.extend(_verification_events(verifications))
        gaps = tuple(gap for item in verifications for gap in item.resolution.coverage_gaps)
        capability = next((item.capability_id for item in intake.tool_plan.steps
                           if item.capability_id.startswith("admet.")), "admet")
        events.append(StreamEvent("tool.started", {"capability_id": capability,
                    "role_order": list(next((item.tool_input.role_order
                    for item in intake.tool_plan.steps if item.capability_id == capability), ()))},
                    "molecular"))
        workflow = run_prepared_admet(intake, self.predictor, plan.requested_properties,
                                      coverage_gaps=gaps)
        execution = workflow.execution
        status = execution.status if execution else "failed"
        events.append(StreamEvent("tool.completed", _execution_payload(workflow), "molecular"))
        answer = _answer(workflow)
        events.append(StreamEvent("message.delta", {"content": answer}, "molecular"))
        if status != "completed":
            events.append(StreamEvent("error", {"stage": "admet", "status": status,
                "recoverable": True, "coverage_gaps": list(workflow.coverage_gaps)}, "molecular"))
        events.append(StreamEvent("done", {"status": status}, "molecular"))
        return MolecularChatResult(answer, tuple(events), plan, workflow, verifications)

    def _seeds(self, plan):
        result, gaps = [], []
        for role, entity in _entities(plan):
            try:
                resolution = (self.resolver.resolve_name(entity.value)
                              if entity.kind == "name" else None)
            except Exception as exc:
                resolution = _resolution_failure("PubChem name resolution", exc)
            result.append((role, entity, resolution))
            if resolution and resolution.external is None:
                gaps.extend(resolution.coverage_gaps)
        return tuple(result), tuple(gaps)

    def _verify(self, intake, plan, seeds):
        values = []
        bindings = (intake.selected_input, intake.selected_baseline_input)
        for (role, _, seed), binding in zip(seeds, bindings, strict=False):
            if binding is None:
                continue
            if seed and seed.normalized_identity and seed.normalized_identity.inchikey == binding.inchikey:
                resolution = seed
            else:
                try:
                    resolution = self.resolver.resolve_binding(binding)
                except Exception as exc:
                    resolution = _resolution_failure("PubChem binding verification", exc)
            values.append(MolecularVerification(role, binding, resolution))
        return tuple(values)


def is_clear_admet_intent(message: str) -> bool:
    text = message.casefold()
    has_admet = re.search(r"(?<![a-z0-9_])admet(?:-ai)?(?![a-z0-9_])", text) is not None
    action = any(word in text for word in _ADMET_ACTIONS)
    research = any(word in text for word in _RESEARCH_MARKERS)
    return has_admet and action and not research


def _entities(plan):
    values = [("candidate", plan.candidate)]
    if plan.baseline:
        values.append(("baseline", plan.baseline))
    return tuple(values)


def _intake(plan, seeds, resolver):
    structures = []
    for _, entity, resolution in seeds:
        structures.append(resolution.normalized_identity.canonical_isomeric_smiles
                          if resolution else entity.value)
    candidate, baseline = structures[0], structures[1] if len(structures) == 2 else ""
    return prepare_molecular_request(candidate,
        "ADMET compare" if plan.operation == "compare" else "ADMET",
        resolver.normalizer, baseline_smiles=baseline,
        selected_structure_scope=plan.candidate.scope,
        selected_structure_smiles=plan.candidate.selected_structure_smiles,
        baseline_structure_scope=plan.baseline.scope if plan.baseline else None,
        baseline_structure_smiles=(plan.baseline.selected_structure_smiles if plan.baseline else ""))


def _plan_payload(plan):
    return {"capability_id": "molecular.plan", "status": "completed",
            "operation": plan.operation, "candidate": plan.candidate.value,
            "baseline": plan.baseline.value if plan.baseline else "",
            "requested_properties": list(plan.requested_properties)}


def _verification_events(values):
    events = []
    for item in values:
        resolution, binding = item.resolution, item.binding
        payload = {"capability_id": "pubchem.identity", "role": item.role,
                   "status": "verified" if resolution.external else "coverage_gap",
                   **_binding_payload(item.role, binding)}
        if resolution.external:
            payload.update({"cid": resolution.external.cid,
                            "verified_name": resolution.external.verified_name})
        else:
            payload["coverage_gaps"] = list(resolution.coverage_gaps)
        events.append(StreamEvent("tool.completed", payload, "molecular"))
    return events


def _execution_payload(workflow):
    execution = workflow.execution
    if execution is None:
        return {"capability_id": "admet", "status": "failed",
                "coverage_gaps": list(workflow.coverage_gaps)}
    return {"capability_id": execution.capability_id, "status": execution.status,
        "provider": execution.provider, "model": execution.model,
        "model_version": execution.model_version, "role_order": list(execution.role_order),
        "inputs": [_binding_payload(role, binding) for role, binding in
                   zip(execution.role_order, execution.input_bindings, strict=False)],
        "values": [{"role": arm.role, "properties": {value.property_id: value.value
                   for value in arm.values}} for arm in execution.arms],
        "deltas": {item.property_id: item.candidate_minus_baseline for item in execution.deltas},
        "warnings": list(execution.warnings), "coverage_gaps": list(workflow.coverage_gaps),
        "experimental_evidence": False}


def _binding_payload(role, binding):
    return {"role": role, "scope": binding.scope,
            "canonical_isomeric_smiles": binding.canonical_isomeric_smiles,
            "inchikey": binding.inchikey, "removed_fragments": list(binding.removed_fragments)}


def _answer(workflow):
    execution = workflow.execution
    lines = [f"ADMET execution status: {execution.status if execution else 'failed'}"]
    if execution:
        for role, binding in zip(execution.role_order, execution.input_bindings, strict=False):
            lines.append(f"{role}: scope={binding.scope}; SMILES={binding.canonical_isomeric_smiles}; "
                         f"InChIKey={binding.inchikey}")
        for arm in execution.arms:
            for value in arm.values:
                lines.append(f"{arm.role}.{value.property_id}={value.value:.12g}")
        for delta in execution.deltas:
            lines.append(f"candidate-minus-baseline.{delta.property_id}="
                         f"{delta.candidate_minus_baseline:.12g}")
        lines.extend("Warning: " + value for value in execution.warnings)
    lines.extend("Coverage gap: " + value for value in workflow.coverage_gaps)
    lines.append("Computational prediction only; experimental_evidence=false. No aggregate, "
                 "desirability, safety, selection, effect, exposure, or uncertainty claim is inferred.")
    return "\n".join(lines)


def _resolution_failure(stage, exc):
    return PubChemResolution(None, None, (),
        (f"{stage} failed: {type(exc).__name__}: {exc}",))


def _safe_failure(events, stage, exc, plan=None):
    gap = f"{stage} failed: {type(exc).__name__}: {exc}"
    return _safe_gap(events, plan, (gap,))


def _safe_gap(events, plan, gaps):
    answer = "ADMET request could not execute safely.\n" + "\n".join(
        "Coverage gap: " + gap for gap in gaps)
    events.append(StreamEvent("message.delta", {"content": answer}, "molecular"))
    events.append(StreamEvent("error", {"stage": "molecular", "status": "failed",
                  "recoverable": True, "coverage_gaps": list(gaps)}, "molecular"))
    events.append(StreamEvent("done", {"status": "failed"}, "molecular"))
    return MolecularChatResult(answer, tuple(events), plan)
