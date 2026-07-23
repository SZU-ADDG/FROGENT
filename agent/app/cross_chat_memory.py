"""Public stdlib API for chronological session ingest and fresh-chat recall."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Iterable

from agent.app.conversation_memory import ConversationMemoryStore, ConversationTurn, MemoryHit
from agent.app.memory_answer import CodexMemoryAnswerer, MemoryAnswer, MemoryRecoveryError


@dataclass(frozen=True, slots=True)
class MemoryResponse:
    conversation_id: str
    answer: str
    supporting_memory_ids: tuple[str, ...]
    abstain: bool
    hits: tuple[MemoryHit, ...]
    recovery_error: MemoryRecoveryError | None = None


class CrossChatMemory:
    """Benchmark/app boundary that never invokes literature research tools."""

    def __init__(self, store: ConversationMemoryStore, answerer: CodexMemoryAnswerer,
                 *, max_hits: int = 8, max_prompt_chars: int = 8000) -> None:
        if max_hits <= 0 or max_prompt_chars <= 0:
            raise ValueError("memory bounds must be positive")
        self.store, self.answerer = store, answerer
        self.max_hits, self.max_prompt_chars = max_hits, max_prompt_chars

    def ingest_session(self, user_id: str, session_id: str, turns: Iterable[ConversationTurn],
                       *, conversation_id: str | None = None) -> int:
        return self.store.ingest_session(user_id, conversation_id or session_id, session_id, turns)

    def ask(self, user_id: str, conversation_id: str, question: str, *,
            occurred_at: str | None = None, persist: bool = True) -> MemoryResponse:
        hits = self.store.retrieve(user_id, question, limit=self.max_hits,
                                   max_prompt_chars=self.max_prompt_chars)
        value: MemoryAnswer = self.answerer.answer(question, hits)
        if persist:
            self._persist_exchange(user_id, conversation_id, question, value.answer, occurred_at)
        return MemoryResponse(conversation_id, value.answer, value.supporting_memory_ids,
                              value.abstain, hits, value.recovery_error)

    def _persist_exchange(self, user_id: str, conversation_id: str, question: str, answer: str,
                          occurred_at: str | None) -> None:
        timestamp = occurred_at or datetime.now(timezone.utc).isoformat()
        key = hashlib.sha256(f"{conversation_id}\0{question}".encode()).hexdigest()[:16]
        answer_key = hashlib.sha256(answer.encode()).hexdigest()[:12]
        user_turn, assistant_turn = "memory-user-" + key, "memory-assistant-" + key + "-" + answer_key
        user_time = self.store.turn_time(user_id, conversation_id, user_turn) or timestamp
        assistant_time = self.store.turn_time(user_id, conversation_id, assistant_turn) or timestamp
        turns = (ConversationTurn(user_turn, "user", question, user_time),
                 ConversationTurn(assistant_turn, "assistant", answer, assistant_time))
        self.store.ingest_session(user_id, conversation_id, conversation_id, turns)


def turn(turn_id: str, role: str, content: str, occurred_at: str | None = None) -> ConversationTurn:
    timestamp = occurred_at or datetime.now(timezone.utc).isoformat()
    return ConversationTurn(turn_id, role, content, timestamp)
