"""Knowledge-led qualitative design role, validation, and routing."""

import re
from typing import Mapping, Protocol

from agent.llm.codex_schemas import design_strategy_schema
from agent.design.decision_policy import (
    CalibrationRequest, DecisionConstraint, DecisionContext, DesignHypothesis,
    HypothesisPortfolio, OptimizationHandoff,
)


_DESIGN_ACTIONS = ("design", "optimize", "improve", "modify", "propose", "prioritize",
                   "rank", "explore", "brainstorm", "设计", "优化", "改造", "修饰", "改进",
                   "提出", "排序", "优先", "探索", "做", "给出")
_DESIGN_OBJECTS = ("molecule", "compound", "ligand", "lead", "drug", "peptide", "protein",
                   "target", "route", "analog", "analogue", "series", "sar", "bioisostere",
                   "scaffold hop", "modification", "分子", "化合物", "配体", "先导", "药物",
                   "肽", "蛋白", "靶点", "路线", "侧链", "氨基酸", "类似物", "构效关系",
                   "骨架跃迁", "生物电子等排", "修饰")
_CONSTRAINT_ACTIONS = ("avoid", "preserve", "retain", "keep", "must", "priority", "forbid",
                       "避免", "保留", "保持", "必须", "优先", "禁止", "不能改")
_CONSTRAINT_OBJECTS = ("amine", "core", "scaffold", "motif", "exposure", "potency", "selectivity",
                       "clearance", "solubility", "permeability", "charge", "stereo", "fragment",
                       "胺", "核心", "骨架", "药效团", "暴露", "活性", "选择性", "清除",
                       "溶解度", "通透性", "电荷", "立体", "片段")
_RESEARCH_MARKERS = ("literature", "paper", "publication", "patent", "search", "find papers",
                     "文献", "论文", "专利", "检索", "搜索", "查找论文")


class StructuredClient(Protocol):
    def generate(self, role: str, contract: str, payload: Mapping[str, object], *, schema): ...


class CodexDesignStrategist:
    def __init__(self, client: StructuredClient) -> None:
        self.client = client

    def propose(self, message: str, history=()) -> HypothesisPortfolio:
        if not isinstance(message, str) or not message.strip():
            raise ValueError("design request must be non-empty")
        turns = _context_turns(message, history)
        payload = {"request": message, "conversation_context": turns}
        schema = design_strategy_schema()
        value = self.client.generate("qualitative medicinal-design strategist", _CONTRACT,
                                     payload, schema=schema)
        sources = {item["turn_id"]: item["content"] for item in turns if item["role"] == "user"}
        try:
            return _portfolio(value, sources)
        except ValueError as exc:
            repaired = self.client.generate("qualitative medicinal-design strategist repair",
                _REPAIR_CONTRACT, {**payload, "validation_error": str(exc),
                "previous_output": value}, schema=schema)
            return _portfolio(repaired, sources)


def is_clear_design_intent(message: str) -> bool:
    text = message.casefold()
    action = any(term in text for term in _DESIGN_ACTIONS)
    design_object = any(term in text for term in _DESIGN_OBJECTS)
    constraint = any(term in text for term in _CONSTRAINT_ACTIONS) and any(
        term in text for term in _CONSTRAINT_OBJECTS)
    research = any(term in text for term in _RESEARCH_MARKERS)
    return (action and design_object or constraint) and not research and not re.search(
        r"\b(?:search|find)\s+(?:a\s+)?(?:molecule|compound|ligand|drug)\b", text)


def is_design_constraint_only(message: str) -> bool:
    text = message.casefold()
    return (any(term in text for term in _CONSTRAINT_ACTIONS)
            and any(term in text for term in _CONSTRAINT_OBJECTS)
            and not any(term in text for term in _DESIGN_ACTIONS))


def _portfolio(value, sources: Mapping[str, str]) -> HypothesisPortfolio:
    required = {"objective", "reliable_discriminator", "unresolved_qualitative_choices",
                "discriminator", "constraints", "optimization_handoff", "hypotheses"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("design strategist output fields are invalid")
    reliable = value["reliable_discriminator"]
    unresolved = value["unresolved_qualitative_choices"]
    if type(reliable) is not bool or type(unresolved) is not bool:
        raise ValueError("design strategist decision flags are invalid")
    constraints = _constraints(value["constraints"], sources)
    handoff = _optimization_handoff(value["optimization_handoff"])
    context = DecisionContext(_text(value["objective"], "objective"), reliable, unresolved,
                              _optional_text(value["discriminator"], "discriminator"),
                              constraints, handoff)
    items = value["hypotheses"]
    if not isinstance(items, list) or any(not isinstance(item, Mapping) for item in items):
        raise ValueError("design hypotheses must be objects")
    return HypothesisPortfolio(context, tuple(_hypothesis(item) for item in items))


def _hypothesis(value) -> DesignHypothesis:
    fields = ("hypothesis_id", "rank", "recommendation", "rationale", "expected_benefits",
              "tradeoffs", "failure_modes", "knowledge_bases", "calibration_requests",
              "decisive_experiment", "confidence")
    if set(value) != set(fields):
        raise ValueError("design hypothesis fields are invalid")
    arrays = tuple(_strings(value[name], name) for name in fields[4:8])
    requests = _calibration_requests(value["calibration_requests"])
    return DesignHypothesis(_text(value["hypothesis_id"], "hypothesis id"), value["rank"],
        _text(value["recommendation"], "recommendation"), _text(value["rationale"], "rationale"),
        *arrays, requests, _text(value["decisive_experiment"], "decisive experiment"),
        _text(value["confidence"], "confidence"))


def _context_turns(message: str, history) -> list[dict[str, str]]:
    turns = []
    for index, item in enumerate(tuple(history)[-8:]):
        if not isinstance(item, Mapping):
            continue
        content, role = item.get("content"), item.get("role")
        role = role if role in {"user", "assistant"} else (
            "user" if item.get("isUser") else "assistant")
        if isinstance(content, str) and content.strip():
            turns.append({"turn_id": f"history-{index}", "role": role,
                          "content": content.strip()[:2000]})
    turns.append({"turn_id": "current", "role": "user", "content": message.strip()[:4000]})
    return turns


def _constraints(value, sources: Mapping[str, str]) -> tuple[DecisionConstraint, ...]:
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError("design constraints must be objects")
    result = []
    for item in value:
        if set(item) != {"text", "source_turn_id", "immutable"}:
            raise ValueError("design constraint fields are invalid")
        text, source = _text(item["text"], "constraint text"), _text(
            item["source_turn_id"], "constraint source turn id")
        if source not in sources or text.casefold() not in sources[source].casefold():
            raise ValueError("design constraint is not grounded in a user turn")
        result.append(DecisionConstraint(text, source, item["immutable"]))
    return tuple(result)


def _calibration_requests(value) -> tuple[CalibrationRequest, ...]:
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError("calibration requests must be objects")
    fields = {"request_id", "capability_id", "purpose", "decision_rule"}
    if any(set(item) != fields for item in value):
        raise ValueError("calibration request fields are invalid")
    return tuple(CalibrationRequest(*(_text(item[name], name) for name in (
        "request_id", "capability_id", "purpose", "decision_rule"))) for item in value)


def _optimization_handoff(value) -> OptimizationHandoff | None:
    fields = {"applicable", "objective", "constraints", "search_space", "discriminator",
              "optimizer", "stopping_rule", "residual_qualitative_choices"}
    if not isinstance(value, Mapping) or set(value) != fields or type(value["applicable"]) is not bool:
        raise ValueError("optimization handoff fields are invalid")
    if not value["applicable"]:
        if any(value[name] for name in fields - {"applicable"}):
            raise ValueError("inapplicable optimization handoff must be empty")
        return None
    return OptimizationHandoff(_text(value["objective"], "optimization objective"),
        _strings(value["constraints"], "optimization constraints"),
        _text(value["search_space"], "optimization search space"),
        _text(value["discriminator"], "optimization discriminator"),
        _text(value["optimizer"], "optimizer"),
        _text(value["stopping_rule"], "optimization stopping rule"),
        tuple(_strings(value["residual_qualitative_choices"], "residual qualitative choices"))
        if value["residual_qualitative_choices"] else ())


def _strings(value, name):
    if not isinstance(value, list) or not value or any(
            not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must contain non-empty strings")
    result = tuple(item.strip() for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must contain unique strings")
    return result


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _optional_text(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    return value.strip()


_CONTRACT = (
    "Make the scientific design judgment the user needs. Classify the task as qualitative, hybrid, "
    "or quantitative by assessing whether an objective-aligned calibrated discriminator covers the "
    "design space. For qualitative or hybrid work, use world knowledge, medicinal-chemistry or peptide "
    "experience, mechanistic reasoning, and relevant precedent to return 3-6 meaningfully different "
    "ranked hypotheses. For a quantitative task, return a typed optimization handoff with the exact "
    "objective, constraints, search space, reliable discriminator, optimizer, stopping rule, and residual "
    "qualitative choices. Extract user constraints only as exact spans from supplied user turns and bind "
    "each to its source turn; do not invent constraints. Every hypothesis "
    "must contain an exact action, rationale, expected benefits, tradeoffs, plausible failure modes, "
    "knowledge bases, typed calibration capability requests with decision rules, confidence, and one "
    "decisive experiment. Tools calibrate and challenge judgment; missing tools do not erase useful "
    "recommendations. Lead with what to do first."
)

_REPAIR_CONTRACT = (
    "Repair the previous qualitative design output to satisfy the exact native schema and semantic "
    "contract. Preserve useful scientific content, exact user-grounded constraints, differentiated "
    "ranked hypotheses, typed calibration requests, and any applicable quantitative handoff. Return "
    "one corrected object only. Do not add constraints that are absent from the supplied user turns."
)
