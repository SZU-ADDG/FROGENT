"""Transport-neutral chat request and event adapters."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.core.contracts import ExecutionContext, StreamEvent


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _first_text(*values: Any) -> str | None:
    return next((text for value in values if (text := _text(value))), None)


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Normalized subset of the web chat route input."""

    user_id: str
    conversation_id: str
    job_id: str
    message: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ChatRequest":
        fields = {
            "user_id": _text(payload.get("user_id")),
            "conversation_id": _first_text(
                payload.get("conversation_id"), payload.get("chat_id")
            ),
            "job_id": _text(payload.get("job_id")),
            "message": _first_text(payload.get("message"), payload.get("query")),
        }
        missing = [name for name, value in fields.items() if value is None]
        if missing:
            raise ValueError(f"chat request has invalid fields: {', '.join(missing)}")
        return cls(**fields)  # type: ignore[arg-type]

    def execution_context(self, workspace: Path) -> ExecutionContext:
        return ExecutionContext(
            self.user_id,
            self.conversation_id,
            self.job_id,
            workspace,
        )


def chat_messages_to_events(messages: Sequence[Mapping[str, Any]]) -> tuple[StreamEvent, ...]:
    """Convert the latest chat turn into transport-neutral runtime events."""

    current_turn = _latest_turn(messages)
    events = tuple(event for message in current_turn for event in _message_events(message))
    return events + (StreamEvent("done", {"event_count": len(events)}),)


def _latest_turn(messages: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    start = 0
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get("role") == "user":
            start = index + 1
            break
    return messages[start:]


def _message_events(message: Mapping[str, Any]) -> tuple[StreamEvent, ...]:
    role = message.get("role")
    if role == "assistant":
        return _assistant_events(message)
    if role == "function":
        return _function_events(message)
    return ()


def _assistant_events(message: Mapping[str, Any]) -> tuple[StreamEvent, ...]:
    agent = _text(message.get("name"))
    events: list[StreamEvent] = []
    function_call = message.get("function_call")
    if isinstance(function_call, Mapping):
        name = _text(function_call.get("name"))
        if name:
            events.append(
                StreamEvent(
                    "tool.started",
                    {"name": name, "arguments": function_call.get("arguments", "")},
                    agent,
                )
            )
        else:
            events.append(
                StreamEvent("error", {"message": "function call has no name"}, agent)
            )
    reasoning = _text(message.get("reasoning_content"))
    if reasoning:
        events.append(StreamEvent("message.delta", {"text": reasoning, "channel": "reasoning"}, agent))
    content = _text(message.get("content"))
    if content:
        events.append(StreamEvent("message.delta", {"text": content, "channel": "answer"}, agent))
    return tuple(events)


def _function_events(message: Mapping[str, Any]) -> tuple[StreamEvent, ...]:
    name = _text(message.get("name"))
    if not name:
        return (StreamEvent("error", {"message": "function message has no name"}),)
    return (
        StreamEvent(
            "tool.completed",
            {"name": name, "content": message.get("content", "")},
        ),
    )
