"""User-scoped, bounded conversation memory over project-contained SQLite."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from agent.app.memory_retrieval import bundled_candidates, ranked_rows

_ROLES = frozenset({"user", "assistant"})


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    turn_id: str
    role: str
    content: str
    occurred_at: str

    def __post_init__(self) -> None:
        if not self.turn_id.strip() or self.role not in _ROLES or not self.content.strip():
            raise ValueError("conversation turn is invalid")
        _timestamp(self.occurred_at)


@dataclass(frozen=True, slots=True)
class MemoryHit:
    memory_id: str
    conversation_id: str
    session_id: str
    turn_id: str
    role: str
    content: str
    occurred_at: str
    insertion_order: int
    matched_terms: tuple[str, ...]
    provenance: str = "conversation_turn"


class ConversationMemoryStore:
    """Persist exact turns and retrieve bounded lexical matches for one user."""

    def __init__(self, path: Path, project_root: Path) -> None:
        self.root = project_root.resolve()
        self.path = path.resolve(strict=False)
        try:
            self.path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("memory database must stay inside project root") from exc
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents
                                    if parent != self.root.parent):
            raise ValueError("memory database path cannot traverse symlinks")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS conversation_turns ("
                "insertion_order INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, "
                "conversation_id TEXT NOT NULL, session_id TEXT NOT NULL, turn_id TEXT NOT NULL, "
                "role TEXT NOT NULL, content TEXT NOT NULL, occurred_at TEXT NOT NULL, "
                "UNIQUE(user_id,session_id,turn_id))")
            connection.execute("CREATE INDEX IF NOT EXISTS conversation_turn_user_time "
                               "ON conversation_turns(user_id,occurred_at,insertion_order)")

    def ingest_session(self, user_id: str, conversation_id: str, session_id: str,
                       turns: Iterable[ConversationTurn]) -> int:
        _identity(user_id, conversation_id, session_id)
        values = tuple(turns)
        if len({item.turn_id for item in values}) != len(values):
            raise ValueError("session turn IDs must be unique")
        inserted = 0
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            for item in values:
                occurred_at = _timestamp(item.occurred_at).isoformat()
                row = connection.execute(
                    "SELECT conversation_id,role,content,occurred_at FROM conversation_turns "
                    "WHERE user_id=? AND session_id=? AND turn_id=?",
                    (user_id, session_id, item.turn_id)).fetchone()
                expected = (conversation_id, item.role, item.content, occurred_at)
                if row and tuple(row) != expected:
                    raise ValueError("turn identity conflicts with persisted content")
                if row:
                    continue
                connection.execute("INSERT INTO conversation_turns "
                    "(user_id,conversation_id,session_id,turn_id,role,content,occurred_at) "
                    "VALUES(?,?,?,?,?,?,?)", (user_id, conversation_id, session_id, item.turn_id,
                                               item.role, item.content, occurred_at))
                inserted += 1
        return inserted

    def retrieve(self, user_id: str, query: str, *, limit: int = 8,
                 max_prompt_chars: int = 8000) -> tuple[MemoryHit, ...]:
        if not user_id.strip() or not query.strip() or limit <= 0 or max_prompt_chars <= 0:
            raise ValueError("memory retrieval parameters are invalid")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT conversation_id,session_id,turn_id,role,content,occurred_at,insertion_order "
                "FROM conversation_turns WHERE user_id=? ORDER BY insertion_order DESC LIMIT 1000",
                (user_id,)).fetchall()
        ranked = ranked_rows(rows, query, _temporal_terms)
        return _bounded_hits(ranked, rows, limit, max_prompt_chars)

    def count(self, user_id: str) -> int:
        if not user_id.strip():
            raise ValueError("user_id must be non-empty")
        with closing(self._connect()) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM conversation_turns WHERE user_id=?",
                                          (user_id,)).fetchone()[0])

    def turn_time(self, user_id: str, session_id: str, turn_id: str) -> str | None:
        _identity(user_id, session_id, turn_id)
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT occurred_at FROM conversation_turns "
                                     "WHERE user_id=? AND session_id=? AND turn_id=?",
                                     (user_id, session_id, turn_id)).fetchone()
        return str(row[0]) if row else None

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)


def _bounded_hits(ranked, rows, limit: int, max_chars: int) -> tuple[MemoryHit, ...]:
    candidates = bundled_candidates(ranked, rows, limit)
    result, used = [], 0
    for row, matched, provenance in candidates:
        if len(result) >= limit or used + len(row[4]) > max_chars:
            continue
        result.append(MemoryHit(f"memory:{row[1]}:{row[2]}", row[0], row[1], row[2], row[3],
                                row[4], row[5], row[6], matched, provenance))
        used += len(row[4])
    return tuple(result)


def _temporal_terms(value: str) -> frozenset[str]:
    parsed = _timestamp(value)
    names = ("january", "february", "march", "april", "may", "june", "july", "august",
             "september", "october", "november", "december")
    return frozenset({str(parsed.year), names[parsed.month - 1], names[parsed.month - 1][:3],
                      parsed.date().isoformat()})


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("occurred_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("occurred_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _identity(*values: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError("memory identity fields must be non-empty")
