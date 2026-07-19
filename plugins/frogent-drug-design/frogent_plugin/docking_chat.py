"""App-facing target-pocket docking and interaction execution."""

import re
from dataclasses import dataclass

from .contracts import ExecutionContext, StreamEvent
from .docking_chat_plan import CodexDockingPlanner, DockingChatPlan
from .docking_chat_render import answer as _answer
from .docking_chat_render import plan_payload as _plan_payload
from .docking_chat_render import workflow_events as _workflow_events
from .docking_execution import run_docking_workflow
from .docking_microstates import (MicrostateSelectionRequired, binding_for_microstate,
                                  select_microstate)
from .docking_types import DockingWorkflowResult
from .molecular_routing import prepare_molecular_request
from .pubchem_identity import PubChemIdentityResolver


_ACTIONS = ("dock ", "run docking", "perform docking", "execute docking", "generate pose",
            "analyze pose", "run plip", "plip analysis",
            "分子对接", "运行对接", "执行对接", "生成构象", "分析相互作用", "相互作用分析")
_RESEARCH = ("literature", "paper", "publication", "search", "review",
             "文献", "论文", "出版物", "检索", "搜索", "综述")


@dataclass(frozen=True, slots=True)
class DockingChatResult:
    answer: str
    events: tuple[StreamEvent, ...]
    plan: DockingChatPlan | None = None
    workflow: DockingWorkflowResult | None = None


class DockingChatHandler:
    def __init__(self, planner: CodexDockingPlanner, resolver: PubChemIdentityResolver,
                 *, target_provider=None, pocket_provider=None, docking_provider=None,
                 interaction_provider=None, microstate_provider=None,
                 receptor_state_provider=None) -> None:
        self.planner, self.resolver = planner, resolver
        self.target_provider, self.pocket_provider = target_provider, pocket_provider
        self.docking_provider, self.interaction_provider = docking_provider, interaction_provider
        self.microstate_provider = microstate_provider
        self.receptor_state_provider = receptor_state_provider

    def run(self, message: str, context: ExecutionContext) -> DockingChatResult:
        events = [StreamEvent("tool.started", {"capability_id": "molecular.plan"}, "docking")]
        try:
            plan = self.planner.plan(message)
            events.append(StreamEvent("tool.completed", _plan_payload(plan), "docking"))
            binding, identity_gaps = self._molecule(plan)
            binding, ligand_state = self._ligand_state(plan, binding, message, events)
        except MicrostateSelectionRequired as exc:
            return _selection_required(events, plan, binding, exc.states)
        except Exception as exc:
            return _safe_failure(events, "planning_or_identity", exc)
        events.append(StreamEvent("tool.completed", {"capability_id": "pubchem.identity",
            "status": "verified" if not identity_gaps else "coverage_gap",
            "scope": binding.scope, "canonical_isomeric_smiles": binding.canonical_isomeric_smiles,
            "inchikey": binding.inchikey, "coverage_gaps": list(identity_gaps)}, "docking"))
        events.append(StreamEvent("tool.started", {"capability_id": "target.standardize",
            "requested_kind": plan.target.kind, "requested_value": plan.target.value}, "docking"))
        workflow = run_docking_workflow(binding, plan.target, plan.pocket,
            target_provider=self.target_provider, pocket_provider=self.pocket_provider,
            docking_provider=self.docking_provider, interaction_provider=self.interaction_provider,
            config=None, want_interactions=plan.operation == "dock_and_interactions",
            selected_pose_id=plan.selected_pose_id,
            selected_pose_rank=plan.selected_pose_rank, ligand_state=ligand_state,
            receptor_state_provider=self.receptor_state_provider,
            receptor_ph=plan.receptor_ph)
        events.extend(_workflow_events(workflow, identity_gaps))
        answer = _answer(binding, workflow, identity_gaps)
        events.append(StreamEvent("message.delta", {"content": answer}, "docking"))
        if workflow.docking.status != "completed" or (workflow.interaction and
                workflow.interaction.status != "completed"):
            events.append(StreamEvent("error", {"stage": "docking_workflow",
                "recoverable": True, "coverage_gaps": list((*identity_gaps,
                *workflow.coverage_gaps))}, "docking"))
        events.append(StreamEvent("done", {"status": workflow.docking.status}, "docking"))
        return DockingChatResult(answer, tuple(events), plan, workflow)

    def _molecule(self, plan):
        gaps = []
        if plan.molecule_kind == "name":
            resolution = self.resolver.resolve_name(plan.molecule_value)
            if resolution.normalized_identity is None:
                raise ValueError("; ".join(resolution.coverage_gaps))
            smiles = resolution.normalized_identity.canonical_isomeric_smiles
        else:
            smiles = plan.molecule_value
        intake = prepare_molecular_request(smiles, "docking", self.resolver.normalizer,
            target_id=plan.target.value, pocket_id=plan.pocket.pocket_id if plan.pocket else "",
            selected_structure_scope=plan.molecule_scope,
            selected_structure_smiles=plan.selected_structure_smiles)
        binding = intake.selected_input
        if plan.molecule_kind == "smiles":
            resolution = self.resolver.resolve_binding(binding)
            gaps.extend(resolution.coverage_gaps)
        return binding, tuple(gaps)

    def _ligand_state(self, plan, binding, message, events):
        selected = plan.selected_microstate_id or plan.selected_microstate_smiles
        if self.microstate_provider is None:
            if selected:
                raise ValueError("ligand microstate provider is unavailable")
            return binding, None
        events.append(StreamEvent("tool.started", {"capability_id": "ligand.microstates"},
                                  "docking"))
        states = self.microstate_provider.enumerate(binding)
        if not selected:
            raise MicrostateSelectionRequired(states)
        state = select_microstate(states, state_id=plan.selected_microstate_id,
            selected_smiles=plan.selected_microstate_smiles,
            evidence=plan.microstate_selection_text, message=message)
        events.append(StreamEvent("tool.completed", {"capability_id": "ligand.microstates",
            "status": "selected", "state_id": state.state_id,
            "canonical_isomeric_smiles": state.canonical_isomeric_smiles,
            "inchikey": state.inchikey, "formal_charge": state.formal_charge,
            "ph_min": state.ph_min, "ph_max": state.ph_max,
            "precision": state.precision, "source_artifact_id": state.source_artifact.id},
            "docking"))
        return binding_for_microstate(binding, state), state


def is_clear_docking_intent(message: str) -> bool:
    text = message.casefold()
    return (any(item in text for item in _ACTIONS)
            and not any(item in text for item in _RESEARCH))


def _safe_failure(events, stage, exc):
    gap = f"{stage} failed: {type(exc).__name__}: {exc}"
    answer = "Docking request could not execute safely.\nCoverage gap: " + gap
    events.extend((StreamEvent("message.delta", {"content": answer}, "docking"),
                   StreamEvent("error", {"stage": stage, "recoverable": True,
                               "coverage_gaps": [gap]}, "docking"),
                   StreamEvent("done", {"status": "failed"}, "docking")))
    return DockingChatResult(answer, tuple(events))


def _selection_required(events, plan, binding, states):
    candidates = [{"state_id": item.state_id,
        "canonical_isomeric_smiles": item.canonical_isomeric_smiles,
        "formal_charge": item.formal_charge, "ph_min": item.ph_min,
        "ph_max": item.ph_max, "protomer_id": item.protomer_id,
        "source_artifact_id": item.source_artifact.id} for item in states]
    payload = {"capability_id": "ligand.microstates", "status": "selection_required",
        "candidates": candidates, "warnings": list(dict.fromkeys(
            warning for item in states for warning in item.warnings))}
    lines = ["Ligand microstate selection is required before docking.",
        f"parent: scope={binding.scope}; SMILES={binding.canonical_isomeric_smiles}; "
        f"InChIKey={binding.inchikey}",
        "Choose one exact state_id or canonical isomeric SMILES:"]
    lines.extend(f"- {item.state_id} | {item.canonical_isomeric_smiles} | "
                 f"charge={item.formal_charge} | pH={item.ph_min:g}-{item.ph_max:g}"
                 for item in states)
    answer = "\n".join(lines)
    events.extend((StreamEvent("tool.completed", payload, "docking"),
                   StreamEvent("message.delta", {"content": answer}, "docking"),
                   StreamEvent("done", {"status": "blocked",
                               "reason": "microstate_selection_required"}, "docking")))
    return DockingChatResult(answer, tuple(events), plan)
