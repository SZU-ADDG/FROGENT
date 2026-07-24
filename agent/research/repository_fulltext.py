"""OpenAlex repository discovery and injectable PDF evidence extraction."""

import json
import urllib.parse
from dataclasses import dataclass
from typing import Mapping, Protocol

from agent.research.biomedical_providers import HttpTransport, UrllibTransport
from agent.core.contracts import ArtifactRef, ExecutionContext
from agent.core.evidence import LiteratureRecord
from agent.research.research_types import FullTextDocument

_PDF_HEADERS = {"User-Agent": "FROGENT/1.0 (biomedical literature research)"}


@dataclass(frozen=True, slots=True)
class RepositoryLocation:
    landing_url: str
    pdf_url: str
    repository_name: str
    repository_host: str
    version: str
    license: str


class PdfTextExtractor(Protocol):
    def extract(self, content: bytes, artifact: ArtifactRef) -> str: ...


class OpenAlexRepositoryLocator:
    BASE = "https://api.openalex.org/works"

    def __init__(self, transport: HttpTransport | None = None, api_key: str = "") -> None:
        self.transport, self.api_key = transport or UrllibTransport(), api_key.strip()

    def locate(self, *, doi: str = "", pmid: str = "") -> RepositoryLocation | None:
        doi, pmid = _doi(doi), pmid.strip()
        identity = "pmid:" + pmid if pmid else "https://doi.org/" + doi if doi else ""
        if not identity:
            raise ValueError("repository discovery requires DOI or PMID")
        params = {"select": "ids,locations"}
        if self.api_key:
            params["api_key"] = self.api_key
        payload = json.loads(self.transport.get(self.BASE + "/" + urllib.parse.quote(
            identity, safe=":/"), params))
        _validate_identity(payload, doi, pmid)
        locations = payload.get("locations")
        if not isinstance(locations, list):
            raise ValueError("OpenAlex work locations are missing")
        candidates = tuple(location for item in locations
                           if (location := _repository_location(item)) is not None)
        return next((item for item in candidates if item.pdf_url), candidates[0] if candidates else None)


class OpenAlexRepositoryResolver:
    def __init__(self, locator: OpenAlexRepositoryLocator,
                 extractor: PdfTextExtractor | None = None,
                 transport: HttpTransport | None = None,
                 max_pdf_bytes: int = 20_000_000) -> None:
        if isinstance(max_pdf_bytes, bool) or not isinstance(max_pdf_bytes, int) or max_pdf_bytes <= 0:
            raise ValueError("repository PDF byte limit must be positive and finite")
        self.locator, self.extractor = locator, extractor
        self.transport = transport or UrllibTransport()
        self.max_pdf_bytes = max_pdf_bytes
        self._gaps: dict[str, str] = {}

    def resolve(self, record: LiteratureRecord, context: ExecutionContext) -> FullTextDocument | None:
        self._gaps.pop(record.id, None)
        try:
            location = self.locator.locate(
                doi=_identifier(record.identifiers, "doi"),
                pmid=_identifier(record.identifiers, "pmid"))
        except Exception as exc:
            self._gaps[record.id] = f"OpenAlex repository discovery failed: {type(exc).__name__}: {exc}"
            return None
        if location is None:
            self._gaps[record.id] = "OpenAlex found no true repository location"
            return None
        detail = _detail(location)
        if not location.pdf_url:
            self._gaps[record.id] = detail + "; repository has no direct PDF"
            return None
        if self.extractor is None:
            self._gaps[record.id] = detail + "; repository PDF extraction unavailable"
            return None
        artifact = ArtifactRef("repository-" + record.id, detail, "application/pdf", location.pdf_url)
        try:
            content = self.transport.get(location.pdf_url, {}, _PDF_HEADERS)
        except Exception as exc:
            self._gaps[record.id] = detail + f"; repository PDF download failed: {type(exc).__name__}: {exc}"
            return None
        if len(content) > self.max_pdf_bytes:
            self._gaps[record.id] = (detail + f"; repository PDF exceeds {self.max_pdf_bytes} byte limit "
                                     f"({len(content)} bytes)")
            return None
        if not content.lstrip(b" \t\r\n").startswith(b"%PDF-"):
            self._gaps[record.id] = detail + "; repository response is not PDF (%PDF- signature missing)"
            return None
        try:
            text = self.extractor.extract(content, artifact).strip()
        except Exception as exc:
            self._gaps[record.id] = detail + f"; repository PDF extraction failed: {type(exc).__name__}: {exc}"
            return None
        if not text:
            self._gaps[record.id] = detail + "; repository PDF extraction returned no text"
            return None
        self._gaps[record.id] = detail + "; repository PDF evidence extracted"
        return FullTextDocument(record.id, artifact, text, "repository_pdf")

    def coverage_gap(self, record_id: str) -> str:
        return self._gaps.pop(record_id, "")


def _repository_location(value: object) -> RepositoryLocation | None:
    if not isinstance(value, Mapping):
        return None
    source = value.get("source")
    if not isinstance(source, Mapping) or source.get("type") != "repository":
        return None
    landing, pdf = str(value.get("landing_page_url") or ""), str(value.get("pdf_url") or "")
    if not _web(landing) or pdf and not _web(pdf):
        return None
    host = str(urllib.parse.urlparse(landing).hostname or "")
    if host.casefold() == "pubmed.ncbi.nlm.nih.gov":
        return None
    name = str(source.get("display_name") or host)
    if not name or not host:
        return None
    return RepositoryLocation(landing, pdf, name, host, str(value.get("version") or "unknown"),
                              str(value.get("license") or "unknown"))


def _validate_identity(payload: object, doi: str, pmid: str) -> None:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("ids"), Mapping):
        raise ValueError("OpenAlex work identity is missing")
    ids = payload["ids"]
    if pmid and _tail(str(ids.get("pmid") or "")) != pmid.casefold():
        raise ValueError("OpenAlex PMID identity mismatch")
    if doi and _doi(str(ids.get("doi") or "")) != doi:
        raise ValueError("OpenAlex DOI identity mismatch")


def _detail(location: RepositoryLocation) -> str:
    return (f"repository={location.repository_name}; host={location.repository_host}; "
            f"version={location.version}; license={location.license}; landing={location.landing_url}")


def _identifier(values: Mapping[str, str], wanted: str) -> str:
    return next((value for key, value in values.items() if key.casefold() == wanted), "")


def _doi(value: str) -> str:
    return value.strip().casefold().removeprefix("https://doi.org/").removeprefix("doi:")


def _tail(value: str) -> str:
    return value.strip().casefold().rstrip("/").rsplit("/", 1)[-1].removeprefix("pmid:")


def _web(value: str) -> bool:
    return urllib.parse.urlparse(value).scheme in {"http", "https"}
