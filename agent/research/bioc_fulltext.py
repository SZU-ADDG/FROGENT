"""Strict, section-preserving NCBI BioC full-text extraction."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BioCArticle:
    text: str
    license: str = ""


_SKIP = {"REF", "REFS", "REFERENCE", "REFERENCES", "BIBLIOGRAPHY"}
_HEADINGS = {
    "TITLE": "Title", "ABSTRACT": "Abstract", "INTRO": "Introduction",
    "INTRODUCTION": "Introduction", "METHOD": "Methods", "METHODS": "Methods",
    "RESULT": "Results", "RESULTS": "Results", "DISCUSS": "Discussion",
    "DISCUSSION": "Discussion", "CONCL": "Conclusion", "CONCLUSION": "Conclusion",
    "CORRECTION": "Correction", "CORRIGENDUM": "Correction", "ERRATUM": "Correction",
    "LIMITATION": "Limitations", "LIMITATIONS": "Limitations", "TABLE": "Table",
    "TABLE_CAPTION": "Table", "FIG": "Figure", "FIGURE": "Figure",
    "FIG_CAPTION": "Figure",
}


def parse_bioc_full_text(raw: bytes) -> BioCArticle:
    root = ET.fromstring(raw)
    chunks: list[str] = []
    counters: dict[str, int] = {}
    for passage in root.iter("passage"):
        infons = {str(item.get("key") or "").casefold(): _clean(item.text)
                  for item in passage.findall("infon")}
        values = {_kind(value) for key, value in infons.items()
                  if key in {"section_type", "section", "type"} and value}
        if values & _SKIP:
            continue
        value = _clean(passage.findtext("text"))
        if not value:
            continue
        heading = _heading(values)
        counters[heading] = counters.get(heading, 0) + 1
        if heading == "Title":
            chunks.append("[TITLE] " + value)
        elif heading == "Abstract":
            chunks.append(f"[ABSTRACT 1 P{counters[heading]}] {value}")
        else:
            chunks.append(f"[SECTION {len(counters)} {heading} P{counters[heading]}] {value}")
    if not chunks:
        raise ValueError("NCBI BioC full text has no readable article passages")
    return BioCArticle("\n".join(chunks), _license(root))


def _heading(values: set[str]) -> str:
    return next((_HEADINGS[value] for value in sorted(values) if value in _HEADINGS), "Body")


def _license(root: ET.Element) -> str:
    return next((_clean(item.text) for item in root.iter("infon")
                 if str(item.get("key") or "").casefold() in {"license", "license_type"}
                 and _clean(item.text)), "")


def _kind(value: str) -> str:
    return value.upper().replace("-", "_").replace(" ", "_")


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())
