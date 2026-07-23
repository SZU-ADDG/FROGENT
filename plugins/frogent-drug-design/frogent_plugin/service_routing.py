"""Deterministic app chat routing and contextual tool dispatch."""

from .docking_chat import is_clear_docking_intent
from .molecular_chat import is_clear_admet_intent
from .qualitative_design import is_clear_design_intent


def memory_intent(message: str) -> bool:
    text = message.casefold()
    markers = ("what did i", "do you remember", "remember my", "what is my favorite",
               "my preference", "what did you tell me", "earlier conversation", "previous chat",
               "across chats", "我之前", "你还记得", "我的偏好", "我说过")
    return any(marker in text for marker in markers)


def tool_route(mode, message, design, molecular, docking):
    handlers = {"design": design, "molecular": molecular, "docking": docking}
    if mode in handlers:
        return (mode, handlers[mode])
    if mode != "auto":
        return None
    checks = (("design", design, is_clear_design_intent),
              ("docking", docking, is_clear_docking_intent),
              ("molecular", molecular, is_clear_admet_intent))
    return next(((name, handler) for name, handler, check in checks
                 if handler is not None and check(message)), None)


def run_tool_handler(handler, message, context, history):
    contextual = getattr(handler, "run_with_history", None)
    return contextual(message, context, history) if callable(contextual) else handler.run(
        message, context)
