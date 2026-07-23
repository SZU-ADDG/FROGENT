"""Strict, evidence-bounded answer role for cross-conversation memory."""

from dataclasses import dataclass

from agent.llm.codex_client import CodexClient
from agent.llm.codex_schemas import memory_answer_schema
from agent.app.conversation_memory import MemoryHit


@dataclass(frozen=True, slots=True)
class MemoryAnswer:
    answer: str
    supporting_memory_ids: tuple[str, ...]
    abstain: bool
    recovery_error: "MemoryRecoveryError | None" = None


@dataclass(frozen=True, slots=True)
class MemoryRecoveryError:
    error_type: str
    message: str
    stage: str = "memory_answer"
    recoverable: bool = True

    def as_payload(self) -> dict[str, object]:
        return {"error_type": self.error_type, "message": self.message,
                "stage": self.stage, "recoverable": self.recoverable}


class CodexMemoryAnswerer:
    def __init__(self, client: CodexClient, max_prompt_chars: int = 8000) -> None:
        if max_prompt_chars <= 0:
            raise ValueError("memory prompt bound must be positive")
        self.client, self.max_prompt_chars = client, max_prompt_chars

    def answer(self, question: str, hits: tuple[MemoryHit, ...]) -> MemoryAnswer:
        if not question.strip() or len(question) >= self.max_prompt_chars:
            raise ValueError("memory question exceeds the configured prompt bound")
        bounded = _bounded(hits, self.max_prompt_chars - len(question))
        if not bounded:
            return MemoryAnswer("I do not have relevant saved conversation memory for that question.", (), True)
        allowed = tuple(item.memory_id for item in bounded)
        schema = memory_answer_schema(allowed)
        payload = {"question": question, "memory_hits": [_hit(item) for item in bounded]}
        value = self.client.generate(
            "cross-conversation memory answerer",
            "Answer only from supplied bounded memory hits. Combine compatible facts across sessions; "
            "sum explicit durations or counts when asked; compare occurred_at timestamps for temporal "
            "questions; join related facts sharing a session_id, including same_session_context. Prefer "
            "current user-stated facts over generic assistant material. When user turns in one session "
            "coherently identify an entity or context and a later event, a qualified inference may link "
            "them only while citing both exact IDs. Abstain when conflicting entities or sessions make "
            "the linkage ambiguous. For recommendations, extract a preference checklist of prefer, "
            "avoid, time, and scope constraints first, then filter every suggestion against the negative "
            "constraints. For comparisons, build an evidence checklist for current item or context, "
            "target or desired change, usage, fit or feel and physical constraints, performance, and "
            "avoid or preference constraints. Compare every supported dimension, label unsupported "
            "dimensions as evidence gaps, and avoid generic shopping advice that ignores the saved "
            "current item and desired change. Provide constraint-aware tips from sufficient evidence "
            "without requiring an exact product choice. Cite every used memory_id and "
            "abstain when required evidence is incomplete; an abstention may cite available partial "
            "evidence while explaining the missing facts. Return answer, supporting_memory_ids, abstain.",
            payload, schema=schema)
        try:
            return _validated(value, allowed)
        except MemorySemanticError as exc:
            try:
                repaired = self.client.generate("cross-conversation memory answer repair",
                    "Repair support and abstention consistency using only allowed memory IDs.",
                    {"validation_error": str(exc), "previous_output": dict(value),
                     "allowed_memory_ids": list(allowed),
                     "question": question,
                     "memory_hits": [_hit(item) for item in bounded]}, schema=schema)
                return _validated(repaired, allowed)
            except Exception as repair_error:
                message = (f"initial validation: {exc}; repair failed: "
                           f"{type(repair_error).__name__}: {repair_error}")
                error = MemoryRecoveryError(type(repair_error).__name__, message)
                return MemoryAnswer("I cannot answer reliably from the retrieved conversation memory.",
                                    (), True, error)


class MemorySemanticError(ValueError):
    pass


def _validated(value, allowed_ids: tuple[str, ...]) -> MemoryAnswer:
    if set(value) != {"answer", "supporting_memory_ids", "abstain"}:
        raise ValueError("memory answer fields are invalid")
    answer, ids, abstain = value["answer"], value["supporting_memory_ids"], value["abstain"]
    if not isinstance(answer, str) or not answer.strip() or not isinstance(abstain, bool):
        raise ValueError("memory answer values are invalid")
    if not isinstance(ids, list) or any(not isinstance(item, str) or not item for item in ids):
        raise ValueError("supporting memory IDs must be non-empty strings")
    supporting = tuple(ids)
    if len(set(supporting)) != len(supporting):
        raise ValueError("supporting memory IDs must be unique")
    if not set(supporting).issubset(allowed_ids):
        raise MemorySemanticError("memory answer cited an unavailable memory ID")
    if not abstain and not supporting:
        raise MemorySemanticError("memory answer abstention and support are inconsistent")
    return MemoryAnswer(answer.strip(), supporting, abstain)


def _hit(item: MemoryHit) -> dict[str, object]:
    return {"memory_id": item.memory_id, "role": item.role, "content": item.content,
            "conversation_id": item.conversation_id, "session_id": item.session_id,
            "turn_id": item.turn_id, "occurred_at": item.occurred_at,
            "insertion_order": item.insertion_order, "matched_terms": list(item.matched_terms),
            "provenance": item.provenance}


def _bounded(hits: tuple[MemoryHit, ...], available: int) -> tuple[MemoryHit, ...]:
    result, used = [], 0
    for item in hits:
        if used + len(item.content) > available:
            continue
        result.append(item)
        used += len(item.content)
    return tuple(result)
