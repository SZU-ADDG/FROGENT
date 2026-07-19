"""App-facing target-pocket docking and interaction execution."""

import re
from dataclasses import dataclass

from .contracts import ExecutionContext, StreamEvent
from .docking_chat_plan import CodexDockingPlanner, DockingChatPlan
from .docking_execution import run_docking_workflow
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
                 interaction_provider=None) -> None:
        self.planner, self.resolver = planner, resolver
        self.target_provider, self.pocket_provider = target_provider, pocket_provider
        self.docking_provider, self.interaction_provider = docking_provider, interaction_provider

    def run(self, message: str, context: ExecutionContext) -> DockingChatResult:
        events = [StreamEvent("tool.started", {"capability_id": "molecular.plan"}, "docking")]
        try:
            plan = self.planner.plan(message)
            events.append(StreamEvent("tool.completed", _plan_payload(plan), "docking"))
            binding, identity_gaps = self._molecule(plan)
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
            selected_pose_id=plan.selected_pose_id)
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


def is_clear_docking_intent(message: str) -> bool:
    text = message.casefold()
    return (any(item in text for item in _ACTIONS)
            and not any(item in text for item in _RESEARCH))


def _workflow_events(workflow, identity_gaps):
    values = []
    target = workflow.target
    values.append(StreamEvent("tool.completed", {"capability_id": "target.standardize",
        "status": "verified" if target else "blocked",
        "target_identifier": target.identifier if target else "",
        "provider": target.provider if target else ""}, "docking"))
    pocket = workflow.pocket
    values.append(StreamEvent("tool.completed", {"capability_id": "pocket.prepare",
        "status": "verified" if pocket else "blocked", "pocket_id": pocket.pocket_id if pocket else "",
        "target_identifier": pocket.target_identifier if pocket else "",
        "chain": pocket.chain if pocket else "", "provider": pocket.provider if pocket else "",
        "provider_version": pocket.provider_version if pocket else ""}, "docking"))
    docking = workflow.docking
    values.append(StreamEvent("tool.completed", {"capability_id": "docking.generate-conformation",
        "status": docking.status, "score_direction": (docking.docking_input.config.score_direction
        if docking.docking_input else ""), "poses": [{"pose_id": pose.pose_id, "rank": pose.rank,
        "score": pose.score, "artifact_id": pose.artifact.id} for pose in docking.poses],
        "provider": docking.provider, "provider_version": docking.provider_version,
        "input_artifact_ids": [item.id for item in docking.input_artifacts],
        "command_argv": list(docking.command_argv),
        "preparation_provenance": [_preparation_payload(item)
                                   for item in docking.preparation_provenance],
        "config": ({"pose_count": docking.docking_input.config.pose_count,
                    "exhaustiveness": docking.docking_input.config.exhaustiveness,
                    "cpu": docking.docking_input.config.cpu,
                    "seed": docking.docking_input.config.seed,
                    "energy_range": docking.docking_input.config.energy_range}
                   if docking.docking_input else {}),
        "warnings": list(docking.warnings), "coverage_gaps": list((*identity_gaps,
        *docking.coverage_gaps))}, "docking"))
    if workflow.interaction:
        item = workflow.interaction
        values.append(StreamEvent("tool.completed", {"capability_id": "sar.analyze",
            "status": item.status, "pose_id": item.pose_id,
            "provider": item.provider, "provider_version": item.provider_version,
            "complex_artifact_id": item.complex_artifact_id,
            "ligand_residue_identity": item.ligand_residue_identity,
            "command_argv": list(item.command_argv),
            "interactions": [_interaction_payload(value) for value in item.interactions],
            "warnings": list(item.warnings), "coverage_gaps": list(item.coverage_gaps)}, "docking"))
    return values


def _interaction_payload(item):
    return {"interaction_type": item.interaction_type, "protein_chain": item.protein_chain,
            "protein_residue": item.protein_residue, "ligand_feature": item.ligand_feature,
            "distance": item.distance, "angle": item.angle}


def _preparation_payload(item):
    return {"tool": item.tool, "version": item.version, "operation": item.operation,
            "source_artifact_ids": [value.id for value in item.source_artifacts],
            "output_artifact_ids": [value.id for value in item.output_artifacts],
            "command_argv": list(item.command_argv), "lossless": item.lossless,
            "moved_record_count": item.moved_record_count,
            "dropped_record_count": item.dropped_record_count}


def _plan_payload(plan):
    return {"capability_id": "molecular.plan", "status": "completed",
            "operation": plan.operation, "molecule": plan.molecule_value,
            "target_kind": plan.target.kind, "target_value": plan.target.value,
            "pocket_id": plan.pocket.pocket_id if plan.pocket else "",
            "selected_pose_id": plan.selected_pose_id}


def _answer(binding, workflow, identity_gaps):
    lines = [f"Docking execution status: {workflow.docking.status}",
        f"molecule: scope={binding.scope}; SMILES={binding.canonical_isomeric_smiles}; "
        f"InChIKey={binding.inchikey}"]
    if workflow.target:
        lines.append(f"target: {workflow.target.kind}:{workflow.target.identifier}; "
                     f"provider={workflow.target.provider}")
    if workflow.pocket:
        lines.append(f"pocket: {workflow.pocket.pocket_id}; chain={workflow.pocket.chain}; "
                     f"numbering={workflow.pocket.numbering_scheme}; artifact={workflow.pocket.artifact.id}")
    for pose in workflow.docking.poses:
        lines.append(f"pose {pose.pose_id}: rank={pose.rank}; score={pose.score:.12g}; "
                     f"artifact={pose.artifact.id}")
    if workflow.interaction:
        lines.append(f"interaction status: {workflow.interaction.status}; "
                     f"selected_pose={workflow.interaction.pose_id or 'none'}")
        for item in workflow.interaction.interactions:
            lines.append(f"interaction: {item.interaction_type}; {item.protein_chain}:"
                         f"{item.protein_residue}; ligand={item.ligand_feature}")
    lines.extend("Warning: " + item for item in workflow.docking.warnings)
    if workflow.interaction:
        lines.extend("Warning: " + item for item in workflow.interaction.warnings)
    lines.extend("Coverage gap: " + item for item in dict.fromkeys(
        (*identity_gaps, *workflow.coverage_gaps)))
    lines.append("Computational docking evidence only; experimental_evidence=false. No binding "
                 "affinity, validated mechanism, or automatic pose-selection claim is inferred.")
    return "\n".join(lines)


def _safe_failure(events, stage, exc):
    gap = f"{stage} failed: {type(exc).__name__}: {exc}"
    answer = "Docking request could not execute safely.\nCoverage gap: " + gap
    events.extend((StreamEvent("message.delta", {"content": answer}, "docking"),
                   StreamEvent("error", {"stage": stage, "recoverable": True,
                               "coverage_gaps": [gap]}, "docking"),
                   StreamEvent("done", {"status": "failed"}, "docking")))
    return DockingChatResult(answer, tuple(events))
