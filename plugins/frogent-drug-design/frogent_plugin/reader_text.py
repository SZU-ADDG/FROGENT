"""Deterministic bounded evidence text packing for paper readers."""

import re

_MARKER = re.compile(r"(?m)^\[(?:TITLE|ABSTRACT|SECTION)[^\]]*\]")
_EVIDENCE = ("result", "discussion", "conclusion", "correction", "limitation",
             "counterevidence", "conflict")
_LOW_VALUE = ("method", "introduction")


def pack_reader_text(text: str, max_chars: int) -> str:
    """Keep structured evidence sections or balanced unstructured boundaries."""
    if max_chars <= 0:
        raise ValueError("reader text bound must be positive")
    if len(text) <= max_chars:
        return text
    blocks = _blocks(text)
    if len(blocks) < 2:
        return _head_tail(text, max_chars)
    primary = tuple(item for item in blocks if _priority(item[1]) <= 1)
    if not primary:
        return _head_tail(text, max_chars)
    selected = _primary_fragments(primary, max_chars)
    used = sum(len(value) for value in selected.values()) + max(0, len(selected) - 1)
    for index, block in sorted(blocks, key=lambda item: (_priority(item[1]), item[0])):
        if index in selected or used >= max_chars:
            continue
        available = max_chars - used - (1 if selected else 0)
        if available < 24:
            continue
        selected[index] = block[:available]
        used += len(selected[index]) + (1 if len(selected) > 1 else 0)
    return "\n".join(selected[index] for index in sorted(selected))[:max_chars]


def _blocks(text: str) -> tuple[tuple[int, str], ...]:
    starts = tuple(match.start() for match in _MARKER.finditer(text))
    return tuple((index, text[start:starts[index + 1] if index + 1 < len(starts) else None].strip())
                 for index, start in enumerate(starts))


def _priority(block: str) -> int:
    label = block.split("]", 1)[0].casefold()
    if label.startswith("[title") or label.startswith("[abstract"):
        return 0
    if any(term in label for term in _EVIDENCE):
        return 1
    if any(term in label for term in _LOW_VALUE):
        return 3
    return 2


def _primary_fragments(blocks: tuple[tuple[int, str], ...], max_chars: int) -> dict[int, str]:
    budget = max(1, max_chars - len(blocks) + 1)
    share, extra = divmod(budget, len(blocks))
    result = {}
    for position, (index, block) in enumerate(blocks):
        limit = share + (1 if position < extra else 0)
        result[index] = block[:limit]
    return result


def _head_tail(text: str, max_chars: int) -> str:
    marker = "\n[OMITTED MIDDLE]\n"
    if max_chars <= len(marker) + 2:
        return text[:max_chars]
    content = max_chars - len(marker)
    head = (content + 1) // 2
    return text[:head] + marker + text[-(content - head):]
