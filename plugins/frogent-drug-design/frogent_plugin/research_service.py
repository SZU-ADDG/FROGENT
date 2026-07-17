"""app_v4-compatible service boundary with persistent research sessions."""

import json
import hashlib
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Mapping, Protocol
from uuid import uuid4

from .contracts import ExecutionContext, StreamEvent
from .conversation_memory import ConversationMemoryStore, ConversationTurn
from .cross_chat_memory import CrossChatMemory, MemoryResponse
from .memory_answer import CodexMemoryAnswerer
from .research_memory import ResearchMemory, SQLiteResearchStore
from .research_types import ResearchRequest


class Planner(Protocol):
    def plan(self, question: str, as_of: date, context: ExecutionContext, history=()) -> ResearchRequest: ...


class Controller(Protocol):
    def run(self, request: ResearchRequest, context: ExecutionContext, checkpoint=None, *,
            revoked_record_ids: tuple[str, ...] = ()): ...


class ResearchService:
    """Convert app_v4 chat payloads to typed runs and legacy SSE frames."""

    def __init__(self, planner: Planner, controller: Controller, store: SQLiteResearchStore,
                 workspace: Path, clock=date.today, *, memory_store: ConversationMemoryStore | None = None,
                 memory_answerer: CodexMemoryAnswerer | None = None, max_memory_hits: int = 8,
                 max_memory_prompt_chars: int = 8000) -> None:
        self.planner, self.controller, self.store = planner, controller, store
        self.workspace, self.clock = workspace.resolve(), clock
        self.memory_store, self.memory_answerer = memory_store, memory_answerer
        if max_memory_hits <= 0 or max_memory_prompt_chars <= 0:
            raise ValueError("memory bounds must be positive")
        self.max_memory_hits, self.max_memory_prompt_chars = max_memory_hits, max_memory_prompt_chars
        self.cross_chat_memory = (CrossChatMemory(memory_store, memory_answerer,
                                  max_hits=max_memory_hits, max_prompt_chars=max_memory_prompt_chars)
                                  if memory_store and memory_answerer else None)
        self.typed_events: dict[tuple[str, str], tuple[StreamEvent, ...]] = {}

    def chat_stream(self, user_id: str, chat_id: str, message: str, history=(), files=()):
        return self.stream_payload(user_id, {"message": message, "chat_id": chat_id,
                                             "files": list(files)}, history=history)

    def stream_payload(self, user_id: str, payload: Mapping[str, object], *, history=()):
        try:
            message, chat_id, files, mode = _payload(payload)
            self._ingest_history(user_id, chat_id, message, history)
            if mode == "memory" or (mode == "auto" and _memory_intent(message)):
                yield from self._memory_stream(user_id, chat_id, message, history)
                return
            context = ExecutionContext(user_id, chat_id, "research-" + uuid4().hex, self.workspace)
            saved = self.store.load(user_id, chat_id)
            request = saved.request if saved and saved.request.plan.question == message else None
            compact = saved.conversation_context if saved else ()
            request = request or self.planner.plan(message, self.clock(), context,
                                                   history=compact + tuple(history))
            checkpoint = saved.checkpoint if saved and saved.request.plan.question == message else None
            revocations = saved.revocations if saved else ()
            result = self.controller.run(request, context, checkpoint, revoked_record_ids=revocations)
            admitted = tuple(_evidence_summary(item) for item in result.ledger.admitted())
            answers = ((saved.answer_versions if saved else ()) + (result.answer,))[-8:]
            conversation = _conversation(compact, message, result.answer)
            state = ResearchMemory(request, result.checkpoint, admitted, answers,
                                   result.checkpoint.revoked_record_ids, conversation)
            self.store.save(user_id, chat_id, state)
            self._persist_exchange(user_id, chat_id, message, result.answer, len(tuple(history)))
            self.typed_events[(user_id, chat_id)] = tuple(result.events)
            yield _frame({"content": result.answer, "name": "research"})
            yield _frame({"stop": True, "name": "research"})
        except Exception as exc:
            event = StreamEvent("error", {"error_type": type(exc).__name__, "message": str(exc)}, "research")
            chat_id = str(payload.get("chat_id") or "")
            self.typed_events[(user_id, chat_id)] = (event,)
            yield _frame({"error": str(exc), "error_type": type(exc).__name__, "name": "research"})
        yield "data: [DONE]\n\n"

    def _memory_stream(self, user_id: str, chat_id: str, message: str, history):
        result = self.ask_memory(user_id, chat_id, message, occurred_at=_timestamp(self.clock()))
        events = (StreamEvent("message.delta", {"content": result.answer,
                  "supporting_memory_ids": list(result.supporting_memory_ids),
                  "abstain": result.abstain}, "memory"),)
        if result.recovery_error:
            events += (StreamEvent("error", result.recovery_error.as_payload(), "memory"),)
        events += (StreamEvent("done", {}, "memory"),)
        self.typed_events[(user_id, chat_id)] = events
        yield _frame({"content": result.answer, "name": "memory"})
        yield _frame({"stop": True, "name": "memory"})
        yield "data: [DONE]\n\n"

    def _ingest_history(self, user_id: str, chat_id: str, message: str, history) -> None:
        if self.memory_store is None:
            return
        timestamp = _timestamp(self.clock())
        turns, occurrences, values = [], {}, tuple(history)
        for index, item in enumerate(values):
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            role = item.get("role")
            role = role if role in {"user", "assistant"} else ("user" if item.get("isUser") else "assistant")
            if not isinstance(content, str) or not content.strip():
                continue
            if index == len(values) - 1 and role == "user" and content.strip() == message:
                continue
            event_time = item.get("occurred_at")
            identity = f"{role}\0{content.strip()}\0{event_time if isinstance(event_time, str) else ''}"
            digest = hashlib.sha256(identity.encode()).hexdigest()[:20]
            occurrence = occurrences.get(digest, 0)
            occurrences[digest] = occurrence + 1
            turn_id = f"history-{digest}-{occurrence}"
            event_time = event_time if isinstance(event_time, str) else (
                self.memory_store.turn_time(user_id, chat_id, turn_id) or timestamp)
            turns.append(ConversationTurn(turn_id, role, content[:4000], event_time))
        self.memory_store.ingest_session(user_id, chat_id, chat_id, turns)

    def ingest_memory_session(self, user_id: str, session_id: str,
                              turns, *, conversation_id: str | None = None) -> int:
        if self.cross_chat_memory is None:
            raise RuntimeError("cross-chat memory is not configured")
        return self.cross_chat_memory.ingest_session(user_id, session_id, turns,
                                                     conversation_id=conversation_id)

    def ask_memory(self, user_id: str, conversation_id: str, question: str, *,
                   occurred_at: str | None = None, persist: bool = True) -> MemoryResponse:
        if self.cross_chat_memory is None:
            raise RuntimeError("cross-chat memory is not configured")
        return self.cross_chat_memory.ask(user_id, conversation_id, question,
                                          occurred_at=occurred_at, persist=persist)

    def _persist_exchange(self, user_id: str, chat_id: str, message: str, answer: str,
                          history_count: int) -> None:
        if self.memory_store is None:
            return
        stamp = _timestamp(self.clock())
        key = hashlib.sha256(f"{history_count}\0{message}".encode()).hexdigest()[:16]
        answer_key = hashlib.sha256(answer.encode()).hexdigest()[:12]
        user_turn, assistant_turn = "current-user-" + key, "current-assistant-" + key + "-" + answer_key
        user_time = self.memory_store.turn_time(user_id, chat_id, user_turn) or stamp
        assistant_time = self.memory_store.turn_time(user_id, chat_id, assistant_turn) or stamp
        turns = (ConversationTurn(user_turn, "user", message[:4000], user_time),
                 ConversationTurn(assistant_turn, "assistant", answer[:4000], assistant_time))
        self.memory_store.ingest_session(user_id, chat_id, chat_id, turns)

    def revoke(self, user_id: str, conversation_id: str, record_ids: tuple[str, ...]) -> None:
        saved = self.store.load(user_id, conversation_id)
        if saved is None:
            raise KeyError("research session does not exist")
        values = tuple(dict.fromkeys(saved.revocations + record_ids))
        updated = replace(saved.checkpoint, revoked_record_ids=values)
        self.store.save(user_id, conversation_id, ResearchMemory(saved.request, updated,
                        tuple(item for item in saved.admitted_evidence if item.get("record_id") not in values),
                        saved.answer_versions, values, saved.conversation_context))


def _payload(value: Mapping[str, object]) -> tuple[str, str, list[object], str]:
    message, chat_id, files = value.get("message"), value.get("chat_id"), value.get("files", [])
    mode = value.get("mode", "auto")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be non-empty text")
    if not isinstance(chat_id, str) or not chat_id.strip():
        raise ValueError("chat_id must be non-empty text")
    if not isinstance(files, list):
        raise ValueError("files must be a list")
    if mode not in {"auto", "research", "memory"}:
        raise ValueError("mode must be auto, research, or memory")
    return message.strip(), chat_id.strip(), files, mode


def _evidence_summary(item) -> dict[str, object]:
    return {"id": item.id, "record_id": item.record_id, "claim": item.claim,
            "locator": item.locator, "strength": item.strength.value,
            "limitations": list(item.limitations)}


def _frame(value: Mapping[str, object]) -> str:
    return "data: " + json.dumps(value, ensure_ascii=False) + "\n\n"


def _conversation(previous, message: str, answer: str) -> tuple[Mapping[str, object], ...]:
    turns = list(previous)
    if len(turns) >= 2 and turns[-2].get("role") == "user" and turns[-2].get("content") == message:
        turns[-1] = {"role": "assistant", "content": answer[:2000]}
    else:
        turns.extend(({"role": "user", "content": message[:2000]},
                      {"role": "assistant", "content": answer[:2000]}))
    return tuple(turns[-8:])


def _timestamp(value) -> str:
    if isinstance(value, datetime):
        current = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    elif isinstance(value, date):
        current = datetime.combine(value, datetime.min.time(), timezone.utc)
    else:
        raise ValueError("clock must return date or datetime")
    return current.astimezone(timezone.utc).isoformat()


def _memory_intent(message: str) -> bool:
    text = message.casefold()
    markers = ("what did i", "do you remember", "remember my", "what is my favorite",
               "my preference", "what did you tell me", "earlier conversation", "previous chat",
               "across chats", "我之前", "你还记得", "我的偏好", "我说过")
    return any(marker in text for marker in markers)
