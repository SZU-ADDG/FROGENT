"""Bounded deterministic author and citation expansion for verified records."""

from dataclasses import dataclass
from typing import Mapping

from .evidence import LiteratureRecord
from .research_types import AuthorLead, ResearchQuery


@dataclass(frozen=True, slots=True)
class ExpansionPolicy:
    max_queries: int = 8
    related_limit: int = 10
    include_authors: bool = True
    include_citations: bool = True
    include_references: bool = True

    def __post_init__(self) -> None:
        if self.max_queries <= 0 or self.related_limit <= 0:
            raise ValueError("expansion limits must be positive")


@dataclass(frozen=True, slots=True)
class ExpansionBatch:
    queries: tuple[ResearchQuery, ...]
    gaps: tuple[str, ...] = ()


class ResearchExpander:
    """Create explicit Europe PMC expansion queries with bounded provenance."""

    def __init__(self, europe_pmc, openalex=None, policy: ExpansionPolicy = ExpansionPolicy()) -> None:
        self.europe, self.openalex, self.policy = europe_pmc, openalex, policy

    def expand(self, records: tuple[LiteratureRecord, ...], leads) -> ExpansionBatch:
        unique, gaps = {}, []
        if self.policy.include_authors:
            _add(unique, self._author_queries(leads), self.policy.max_queries)
        for record in records:
            if len(unique) >= self.policy.max_queries:
                break
            self._bounded_related(record, unique, gaps)
            if len(unique) < self.policy.max_queries:
                _add(unique, self._openalex_queries(record, gaps), self.policy.max_queries)
        return ExpansionBatch(tuple(unique.values()), tuple(gaps))

    def _bounded_related(self, record, unique, gaps) -> None:
        if not self.europe:
            gaps.append("Europe PMC relation expansion unavailable")
            return
        for relation, enabled in (("citations", self.policy.include_citations),
                                  ("references", self.policy.include_references)):
            if enabled and len(unique) < self.policy.max_queries:
                _add(unique, self._one_relation(record, relation, gaps), self.policy.max_queries)

    def _author_queries(self, leads) -> list[ResearchQuery]:
        result = []
        for lead in leads:
            name, orcid = _lead_value(lead, "name"), _lead_value(lead, "orcid")
            query = f'AUTHORID:"{orcid}"' if orcid else f'AUTH:"{name}"'
            if name:
                result.append(_query(query, "verified-author:" + (orcid or name)))
        return result

    def _one_relation(self, record: LiteratureRecord, relation: str,
                      gaps: list[str]) -> list[ResearchQuery]:
        identifier = record.identifiers.get("pmid") or record.id
        try:
            values = self.europe.related("MED", identifier, relation, self.policy.related_limit)
        except Exception as exc:
            gaps.append(f"{record.id} {relation} expansion failed: {type(exc).__name__}: {exc}")
            return []
        return [_query(f"EXT_ID:{value}", f"{relation}:{record.id}") for value in values]

    def _openalex_queries(self, record: LiteratureRecord, gaps: list[str]) -> list[ResearchQuery]:
        doi = record.identifiers.get("doi", "")
        if not self.openalex or not doi:
            return []
        try:
            network = self.openalex.expand_work(doi)
        except Exception as exc:
            gaps.append(f"{record.id} OpenAlex expansion failed: {type(exc).__name__}: {exc}")
            return []
        authors = network.get("authors", ()) if isinstance(network, Mapping) else ()
        return [_query(f'AUTH:"{item.get("author", "")}"', f"openalex-author:{record.id}")
                for item in authors if item.get("author")]


def _query(text: str, provenance: str) -> ResearchQuery:
    return ResearchQuery("europe-pmc.search", "europe_pmc", text, 10, "expansion", provenance)


def _lead_value(lead, field: str) -> str:
    value = lead.get(field, "") if isinstance(lead, Mapping) else getattr(lead, field, "")
    return str(value).strip()


def _add(target, queries, limit: int) -> None:
    for query in queries:
        if len(target) >= limit:
            return
        target.setdefault((query.source, query.query), query)
