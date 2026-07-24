"""Bounded page-addressable extraction for optional pypdf deployments."""

import importlib
from io import BytesIO

from agent.core.contracts import ArtifactRef

_PAGE_LIMIT = "[PDF TEXT TRUNCATED: page limit]"
_CHARACTER_LIMIT = "[PDF TEXT TRUNCATED: character limit]"
_MIN_CHARS = len(_PAGE_LIMIT) + len(_CHARACTER_LIMIT) + 2


class PypdfTextExtractor:
    def __init__(self, max_pages: int = 100, max_chars: int = 500_000, *, module=None) -> None:
        if not _positive_int(max_pages) or not _positive_int(max_chars) or max_chars < _MIN_CHARS:
            raise ValueError("PDF bounds must be positive integers with room for truncation markers")
        self.max_pages, self.max_chars = max_pages, max_chars
        self._pypdf = module or importlib.import_module("pypdf")

    def extract(self, content: bytes, artifact: ArtifactRef) -> str:
        try:
            reader = self._pypdf.PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("encrypted PDF requires an explicit decryption tool")
            result = self._pages(reader.pages)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"PDF is unreadable: {type(exc).__name__}: {exc}") from exc
        if not result:
            raise ValueError("PDF has no extractable text; OCR required")
        return result

    def _pages(self, pages) -> str:
        chunks: list[str] = []
        for page_number, page in enumerate(pages, 1):
            if page_number > self.max_pages:
                break
            value = page.extract_text()
            if value is not None and not isinstance(value, str):
                raise ValueError("PDF page text must be a string")
            text = " ".join((value or "").split())
            if not text:
                continue
            chunks.append(f"[PDF PAGE {page_number}] {text}")
        if not chunks:
            return ""
        markers = [_PAGE_LIMIT] if len(pages) > self.max_pages else []
        content = "\n".join(chunks)
        candidate = "\n".join(chunks + markers)
        if len(candidate) <= self.max_chars:
            return candidate
        markers.append(_CHARACTER_LIMIT)
        suffix = "\n".join(markers)
        available = self.max_chars - len(suffix) - 1
        return content[:available].rstrip() + "\n" + suffix


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
