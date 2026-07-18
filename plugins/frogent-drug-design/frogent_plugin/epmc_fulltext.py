"""Section-preserving Europe PMC JATS full-text extraction."""

import xml.etree.ElementTree as ET


def parse_epmc_full_text(raw: bytes) -> str:
    root = ET.fromstring(raw)
    chunks = []
    title = _first(root, "article-title")
    if title is not None and (value := _text(title)):
        chunks.append("[TITLE] " + value)
    for abstract_index, abstract in enumerate(_elements(root, "abstract"), 1):
        values = _paragraphs(abstract)
        if not values and (value := _text(abstract)):
            values = (value,)
        chunks.extend(f"[ABSTRACT {abstract_index} P{index}] {value}"
                      for index, value in enumerate(values, 1))
    body = _first(root, "body")
    if body is not None:
        _body(body, (), "Body", chunks)
    if not chunks:
        fallback = []
        _content(root, fallback)
        chunks.extend(f"[SECTION BODY P{index}] {value}"
                      for index, value in enumerate(fallback, 1))
    if not chunks:
        raise ValueError("Europe PMC full text has no readable article content")
    return "\n".join(chunks)


def _body(node: ET.Element, path: tuple[int, ...], title: str, chunks: list[str]) -> None:
    section_index = paragraph_index = 0
    label = ".".join(map(str, path)) if path else "BODY"
    for child in node:
        tag = _tag(child)
        if tag == "ref-list":
            continue
        if tag == "sec":
            section_index += 1
            _section(child, path + (section_index,), chunks)
        else:
            direct = []
            _content(child, direct)
            for value in direct:
                paragraph_index += 1
                chunks.append(f"[SECTION {label} {title} P{paragraph_index}] {value}")


def _section(node: ET.Element, path: tuple[int, ...], chunks: list[str]) -> None:
    heading = next((_text(child) for child in node if _tag(child) == "title"), "Untitled")
    _body(node, path, heading or "Untitled", chunks)


def _content(node: ET.Element, result: list[str]) -> None:
    tag = _tag(node)
    if tag in {"ref-list", "sec", "title"}:
        return
    if tag == "p":
        if value := _text(node):
            result.append(value)
        return
    for child in node:
        _content(child, result)


def _paragraphs(node: ET.Element) -> tuple[str, ...]:
    return tuple(value for child in node.iter() if _tag(child) == "p"
                 if (value := _text(child)))


def _elements(node: ET.Element, tag: str) -> tuple[ET.Element, ...]:
    return tuple(child for child in node.iter() if _tag(child) == tag)


def _first(node: ET.Element, tag: str) -> ET.Element | None:
    return next((child for child in node.iter() if _tag(child) == tag), None)


def _tag(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _text(node: ET.Element) -> str:
    return " ".join(" ".join(node.itertext()).split())
