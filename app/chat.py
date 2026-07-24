"""Chat streaming, persistence, and attachment context for the web app."""

import json
import logging
from datetime import datetime
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def stream_chat(state, user_id, chat_id, chat_session, message, files, history):
    agent_content = message
    if files:
        agent_content = ([{"text": message}] if message else []) + [
            {"file": file_path(item, state["uploads"])} for item in files
        ]
        for item in files:
            state["models"].ChatFiles.create(
                user_id=user_id,
                conversation_id=chat_id,
                filename=require_text(item.get("filename"), "filename"),
                path=file_path(item, state["uploads"]),
                is_molecular=bool(item.get("is_molecular")),
                is_clear=False,
                is_visible=False,
                format=item.get("format"),
            )
    answer, answer_name = [], ""
    try:
        for chunk in state["manager"].chat_stream(user_id, agent_content, history):
            yield chunk
            event = parse_event(chunk)
            if event is None:
                continue
            name = event.get("name")
            if isinstance(name, str) and name and answer_name and name != answer_name:
                persist_answer(
                    state["models"], user_id, chat_id, chat_session, "".join(answer), answer_name
                )
                answer = []
            if isinstance(name, str) and name:
                answer_name = name
            content = event.get("content")
            if isinstance(content, str):
                answer.append(content)
        persist_answer(
            state["models"], user_id, chat_id, chat_session, "".join(answer), answer_name
        )
    except GeneratorExit:
        persist_answer(
            state["models"], user_id, chat_id, chat_session, "".join(answer), answer_name
        )
        raise
    except Exception:
        LOGGER.exception("Agent stream failed")
        yield 'data: {"error":"Agent stream failed safely"}\n\n'
        yield "data: [DONE]\n\n"


def persist_answer(models, user_id, chat_id, chat, content, name):
    if content.strip():
        chat["messages"].append(
            {"content": content.strip(), "isUser": False, "name": name}
        )
    chat["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    record = models.ChatHistory.get_by_conversation_id(user_id, chat_id)
    if record is None:
        models.ChatHistory.create(
            user_id=user_id,
            conversation_id=chat_id,
            title=chat["title"],
            message_data=chat["messages"],
        )
    else:
        record.update(new_message_data=chat["messages"])


def load_chat_sessions(models, user_id, uploads):
    result = {}
    for record in models.ChatHistory.query.filter_by(user_id=user_id).all():
        item = record.to_dict()
        result[item["conversation_id"]] = {
            "id": item["conversation_id"],
            "title": item["title"],
            "messages": item["message_data"],
            "createdAt": item["created_at"],
            "updatedAt": item["updated_at"],
            **split_files(models, user_id, item["conversation_id"], uploads),
        }
    return result


def split_files(models, user_id, chat_id, uploads):
    result = {"files": [], "molecules": []}
    for record in models.ChatFiles.get_by_conversation_id(user_id, chat_id) or ():
        item = record.to_dict()
        if item["is_molecular"]:
            path = Path(file_path(item, uploads))
            item.update(data=path.read_text(encoding="utf-8"), file_id=item["id"])
            result["molecules"].append(item)
        else:
            result["files"].append(item)
    return result


def user_content(message, files):
    if not files:
        return message, []
    paths = [{"file": item.get("path")} for item in files]
    content = ([{"text": message}] if message else []) + paths
    return content, [item.get("filename") for item in files]


def new_chat(chat_id, message):
    now = datetime.now().isoformat(timespec="seconds")
    title = message[:15] + ("..." if len(message) > 15 else "")
    return {
        "id": chat_id,
        "title": title or "File analysis",
        "messages": [],
        "createdAt": now,
        "updatedAt": now,
        "files": [],
        "molecules": [],
    }


def parse_event(chunk):
    if not isinstance(chunk, str) or not chunk.startswith("data: "):
        return None
    raw = chunk[6:].strip()
    if raw == "[DONE]":
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def file_path(item, uploads):
    if not isinstance(item, dict):
        raise ValueError("file metadata must be an object")
    raw = item.get("path")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("file path must be non-empty text")
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("file path must be an absolute non-symlink")
    resolved = path.resolve(strict=True)
    resolved.relative_to(uploads)
    if not resolved.is_file():
        raise ValueError("file path must identify a regular file")
    return str(resolved)


def require_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value.strip()
