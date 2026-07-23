"""Shared recovery for app-facing computational tool responses."""

from agent.core.contracts import StreamEvent


def persistence_recovery(answer, events, errors, agent):
    if not errors:
        return answer, events
    messages = tuple(dict.fromkeys(f"conversation memory persistence failed: "
        f"{type(item).__name__}: {item}" for item in errors))
    values = list(events)
    done = values.pop() if values and values[-1].kind == "done" else None
    values.extend(StreamEvent("error", {"stage": "memory_persistence",
        "error_type": type(item).__name__, "message": str(item), "recoverable": True},
        agent) for item in errors)
    if done:
        values.append(done)
    return answer + "\n" + "\n".join("Coverage gap: " + item for item in messages), tuple(values)
