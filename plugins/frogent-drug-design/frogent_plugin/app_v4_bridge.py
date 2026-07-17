"""Drop-in bridge from app_v4 assistant manager calls to ResearchService."""

from pathlib import Path
from typing import Callable, Mapping, Protocol


class StreamingResearchService(Protocol):
    def stream_payload(self, user_id: str, payload: Mapping[str, object], *, history=()): ...


class AppV4ResearchManager:
    """Match QwenAssistantManager.chat_stream without importing Flask."""

    def __init__(self, service: StreamingResearchService,
                 conversation_id_getter: Callable[[str], str],
                 allowed_upload_root: Path | None = None) -> None:
        self.service, self.conversation_id_getter = service, conversation_id_getter
        self.allowed_upload_root = allowed_upload_root.resolve() if allowed_upload_root else None

    def chat_stream(self, user_id: str, agent_content_list_or_text, chat_history):
        chat_id = self.conversation_id_getter(user_id)
        if not isinstance(chat_id, str) or not chat_id.strip():
            raise ValueError("conversation id getter must return non-empty text")
        if not isinstance(chat_history, (list, tuple)):
            raise ValueError("chat history must be a list or tuple")
        message, files = _content(agent_content_list_or_text, self.allowed_upload_root)
        payload = {"message": message, "chat_id": chat_id.strip(), "files": files}
        return self.service.stream_payload(user_id, payload, history=chat_history)


def _content(value, allowed_upload_root: Path | None = None) -> tuple[str, list[Mapping[str, str]]]:
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("research message must be non-empty")
        return value.strip(), []
    if not isinstance(value, list):
        raise ValueError("agent content must be text or a list")
    texts, files = [], []
    for item in value:
        if not isinstance(item, Mapping) or set(item) not in ({"text"}, {"file"}):
            raise ValueError("agent content items must contain only text or file")
        if "text" in item:
            text = item["text"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("content text must be non-empty")
            texts.append(text.strip())
        else:
            path = item["file"]
            if not isinstance(path, str) or not path.strip():
                raise ValueError("content file must be non-empty text")
            files.append({"path": _upload_path(path.strip(), allowed_upload_root)})
    if not texts and not files:
        raise ValueError("agent content list must be non-empty")
    message = "\n".join(texts) if texts else "Analyze the supplied files."
    return message, files


def _upload_path(value: str, root: Path | None) -> str:
    if root is None:
        return value
    source = Path(value)
    if not source.is_absolute():
        raise ValueError("upload path must be absolute")
    try:
        _reject_upload_symlinks(source, root)
        resolved = source.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError("upload path must be a real file inside the allowed upload root") from exc
    if not resolved.is_file():
        raise ValueError("upload path must identify a regular file")
    return str(resolved)


def _reject_upload_symlinks(source: Path, root: Path) -> None:
    current = source
    while current != root and current != current.parent:
        if current.is_symlink():
            raise ValueError("upload path cannot traverse symlinks")
        current = current.parent
    if current != root or root.is_symlink():
        raise ValueError("upload path must stay inside the allowed upload root")
