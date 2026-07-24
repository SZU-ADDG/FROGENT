"""Injectable live adapters for biomedical literature and OA metadata."""

import json
import math
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Mapping, Protocol

from agent.core.contracts import ArtifactRef, ExecutionContext
from agent.research.bioc_fulltext import parse_bioc_full_text
from agent.core.evidence import LiteratureRecord
from agent.research.epmc_fulltext import parse_epmc_full_text
from agent.core.literature import LiteratureBatch, LiteratureQuery
from agent.research.research_types import FullTextDocument


class HttpTransport(Protocol):
    def get(self, url: str, params: Mapping[str, str], headers: Mapping[str, str] = {}) -> bytes: ...


class UrllibTransport:
    def __init__(self, timeout: float | None = None) -> None:
        if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("HTTP timeout must be a positive finite value or None")
        self.timeout = timeout

    def get(self, url: str, params: Mapping[str, str], headers: Mapping[str, str] = {}) -> bytes:
        target = url + ("?" + urllib.parse.urlencode(params) if params else "")
        request = urllib.request.Request(target, headers=dict(headers))
        opener = (urllib.request.urlopen(request) if self.timeout is None else
                  urllib.request.urlopen(request, timeout=self.timeout))
        with opener as response:
            return response.read()


class EuropePMCProvider:
    BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
    BIOC_BASE = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml"

    def __init__(self, transport: HttpTransport | None = None) -> None:
        self.transport = transport or UrllibTransport()
        self._metadata: dict[str, Mapping[str, object]] = {}
        self._resolution_gaps: dict[str, str] = {}

    def search(self, query: LiteratureQuery, context: ExecutionContext) -> LiteratureBatch:
        raw = self.transport.get(self.BASE + "/search", {"query": query.query, "format": "json",
                                 "resultType": "core", "pageSize": str(query.limit)})
        payload = json.loads(raw)
        records = tuple(self._record(item, query) for item in payload.get("resultList", {}).get("result", []))
        return LiteratureBatch(query, records, "europe-pmc-rest", tuple(payload.get("warnings", ())))

    def resolve(self, record: LiteratureRecord, context: ExecutionContext) -> FullTextDocument | None:
        pmcid = _identifier(record.identifiers, "pmcid")
        if not pmcid:
            return None
        self._resolution_gaps.pop(record.id, None)
        primary_url = f"{self.BASE}/{pmcid}/fullTextXML"
        try:
            text = parse_epmc_full_text(self.transport.get(primary_url, {}))
        except Exception as primary_error:
            return self._resolve_bioc(record, pmcid, primary_error)
        artifact = ArtifactRef("oa-" + record.id, pmcid + ".xml", "application/xml", primary_url)
        return FullTextDocument(record.id, artifact, text, "jats")

    def coverage_gap(self, record_id: str) -> str:
        return self._resolution_gaps.pop(record_id, "")

    def _resolve_bioc(self, record: LiteratureRecord, pmcid: str,
                      primary_error: Exception) -> FullTextDocument | None:
        url = f"{self.BIOC_BASE}/{urllib.parse.quote(pmcid, safe='')}/unicode"
        primary = "Europe PMC fullTextXML failed: " + _failure(primary_error)
        try:
            article = parse_bioc_full_text(self.transport.get(url, {}))
        except Exception as fallback_error:
            self._resolution_gaps[record.id] = (
                primary + "; NCBI BioC author_manuscript fallback failed: " + _failure(fallback_error))
            return None
        license_note = f"; license={article.license}" if article.license else ""
        self._resolution_gaps[record.id] = (
            primary + "; NCBI BioC author_manuscript fallback used" + license_note
            + "; open-access and publisher-version status not asserted")
        name = pmcid + ".bioc.xml [author_manuscript" + license_note + "]"
        artifact = ArtifactRef("bioc-author-manuscript-" + record.id, name, "application/xml", url)
        return FullTextDocument(record.id, artifact, article.text, "bioc")

    def related(self, source: str, identifier: str, relation: str = "citations",
                limit: int = 25) -> tuple[str, ...]:
        if relation not in {"citations", "references"}:
            raise ValueError("relation must be citations or references")
        raw = self.transport.get(f"{self.BASE}/{source}/{identifier}/{relation}",
                                 {"format": "json", "pageSize": str(limit)})
        payload = json.loads(raw)
        list_key, item_key = (("citationList", "citation") if relation == "citations"
                              else ("referenceList", "reference"))
        return tuple(str(item.get("id")) for item in payload.get(list_key, {}).get(item_key, [])
                     if item.get("id"))

    def metadata(self, record_id: str) -> Mapping[str, object]:
        return self._metadata.get(record_id, {})

    def _record(self, item: Mapping[str, object], query: LiteratureQuery) -> LiteratureRecord:
        pmid, pmcid, doi = (str(item.get(key) or "") for key in ("pmid", "pmcid", "doi"))
        record_id = pmid or pmcid or doi
        if not record_id:
            raise ValueError("Europe PMC result has no stable identifier")
        identifiers = {key: value for key, value in (("pmid", pmid), ("pmcid", pmcid), ("doi", doi)) if value}
        title = str(item.get("title") or "Untitled Europe PMC record")
        artifact = ArtifactRef("epmc-" + record_id, title, "application/json",
                               f"https://europepmc.org/article/MED/{record_id}")
        self._metadata[record_id] = {"authors": item.get("authorList", {}).get("author", [])
                                     if isinstance(item.get("authorList"), dict) else [],
                                     "author_string": item.get("authorString", "")}
        return LiteratureRecord(record_id, query.plan_id, query.source, title, datetime.now(timezone.utc),
                                identifiers, artifact, _parse_date(item.get("firstPublicationDate")),
                                str(item.get("abstractText") or ""))


@dataclass(frozen=True, slots=True)
class NCBIConfig:
    email: str
    tool: str = "frogent"
    api_key: str = ""

    def __post_init__(self) -> None:
        if not self.email.strip() or "@" not in self.email or not self.tool.strip() or " " in self.tool:
            raise ValueError("NCBI requires a valid email and a tool name without spaces")


class PubMedProvider:
    BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, config: NCBIConfig, transport: HttpTransport | None = None,
                 clock: Callable[[], float] = time.monotonic, sleeper: Callable[[float], None] = time.sleep) -> None:
        self.config, self.transport, self.clock, self.sleeper = config, transport or UrllibTransport(), clock, sleeper
        self._last_request: float | None = None

    def search(self, query: LiteratureQuery, context: ExecutionContext) -> LiteratureBatch:
        search = json.loads(self._get("esearch.fcgi", {"db": "pubmed", "term": query.query,
                            "retmax": str(query.limit), "retmode": "json"}))
        ids = tuple(search.get("esearchresult", {}).get("idlist", ()))
        if not ids:
            return LiteratureBatch(query, (), "ncbi-eutils")
        root = ET.fromstring(self._get("efetch.fcgi", {"db": "pubmed", "id": ",".join(ids),
                                                       "retmode": "xml"}))
        records = tuple(_pubmed_record(article, query) for article in root.findall(".//PubmedArticle"))
        return LiteratureBatch(query, records, "ncbi-eutils")

    def _get(self, endpoint: str, params: Mapping[str, str]) -> bytes:
        interval = 0.1 if self.config.api_key else 1 / 3
        if self._last_request is not None:
            wait = interval - (self.clock() - self._last_request)
            if wait > 0:
                self.sleeper(wait)
        common = {"tool": self.config.tool, "email": self.config.email}
        if self.config.api_key:
            common["api_key"] = self.config.api_key
        raw = self.transport.get(f"{self.BASE}/{endpoint}", {**params, **common})
        self._last_request = self.clock()
        return raw


class OpenAlexProvider:
    BASE = "https://api.openalex.org"

    def __init__(self, api_key: str, transport: HttpTransport | None = None) -> None:
        if not api_key.strip():
            raise ValueError("OpenAlex API key is required for live expansion")
        self.api_key, self.transport = api_key, transport or UrllibTransport()

    @classmethod
    def from_env(cls, transport: HttpTransport | None = None):
        key = os.getenv("OPENALEX_API_KEY", "")
        return ((cls(key, transport), None) if key else
                (None, "OpenAlex author/institution expansion skipped: OPENALEX_API_KEY is unset"))

    def expand_work(self, doi: str) -> Mapping[str, object]:
        raw = self.transport.get(self.BASE + "/works/https://doi.org/" + doi, {"api_key": self.api_key})
        work = json.loads(raw)
        authors = tuple({"author": item.get("author", {}).get("display_name", ""),
                         "orcid": item.get("author", {}).get("orcid", ""),
                         "institutions": tuple(inst.get("display_name", "") for inst in item.get("institutions", []))}
                        for item in work.get("authorships", []))
        return {"work_id": work.get("id", ""), "authors": authors,
                "cited_by_count": work.get("cited_by_count", 0), "watchlist": tuple(authors)}


class UnpaywallFallback:
    BASE = "https://api.unpaywall.org/v2"

    def __init__(self, email: str, transport: HttpTransport | None = None) -> None:
        if not email.strip() or "@" not in email:
            raise ValueError("Unpaywall email is required")
        self.email, self.transport = email, transport or UrllibTransport()

    @classmethod
    def from_env(cls, transport: HttpTransport | None = None):
        email = os.getenv("UNPAYWALL_EMAIL", "")
        return (cls(email, transport), None) if email else (None, "Unpaywall skipped: UNPAYWALL_EMAIL is unset")

    def resolve_link(self, doi: str) -> ArtifactRef | None:
        payload = json.loads(self.transport.get(f"{self.BASE}/{doi}", {"email": self.email}))
        location = payload.get("best_oa_location") or {}
        url = location.get("url_for_pdf") or location.get("url")
        return ArtifactRef("unpaywall-" + doi, doi, "text/html", str(url)) if url else None

    def resolve(self, record: LiteratureRecord, context: ExecutionContext) -> FullTextDocument | None:
        doi = _identifier(record.identifiers, "doi")
        artifact = self.resolve_link(doi) if doi else None
        if artifact is None:
            return None
        raw = self.transport.get(artifact.uri, {}, {"User-Agent": "frogent-oa-reader/1"})
        if len(raw) > 2_000_000:
            raise ValueError("Unpaywall OA document exceeds 2 MB reader limit")
        text = raw.decode("utf-8", errors="replace").strip()
        return FullTextDocument(record.id, artifact, text, "oa_fallback") if text else None


def _pubmed_record(article: ET.Element, query: LiteratureQuery) -> LiteratureRecord:
    pmid = article.findtext(".//MedlineCitation/PMID", "").strip()
    title = "".join(article.find(".//ArticleTitle").itertext()).strip() if article.find(".//ArticleTitle") is not None else "Untitled PubMed record"
    doi = next((item.text or "" for item in article.findall(".//ArticleId") if item.get("IdType") == "doi"), "")
    pmcid = next((item.text or "" for item in article.findall(".//ArticleId") if item.get("IdType") == "pmc"), "")
    identifiers = {key: value for key, value in (("pmid", pmid), ("doi", doi), ("pmcid", pmcid)) if value}
    for index, nct_id in enumerate(_pubmed_nct_ids(article), 1):
        identifiers["nct" if index == 1 else f"nct_{index}"] = nct_id
    abstract = " ".join("".join(item.itertext()).strip() for item in article.findall(".//AbstractText"))
    year = article.findtext(".//PubDate/Year", "")
    artifact = ArtifactRef("pubmed-" + pmid, title, "application/xml", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
    return LiteratureRecord(pmid, query.plan_id, query.source, title, datetime.now(timezone.utc), identifiers,
                            artifact, date(int(year), 1, 1) if year.isdigit() else None, abstract)

def _pubmed_nct_ids(article: ET.Element) -> tuple[str, ...]:
    values = []
    for bank in article.findall(".//DataBank"):
        name = "".join((bank.findtext("DataBankName", "")).split()).casefold()
        if name == "clinicaltrials.gov":
            values.extend((item.text or "").strip().upper()
                          for item in bank.findall(".//AccessionNumber"))
    return tuple(dict.fromkeys(value for value in values
                               if len(value) == 11 and value.startswith("NCT") and value[3:].isdigit()))


def _identifier(values: Mapping[str, str], wanted: str) -> str:
    return next((value for key, value in values.items() if key.casefold() == wanted), "")


def _parse_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _failure(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"
