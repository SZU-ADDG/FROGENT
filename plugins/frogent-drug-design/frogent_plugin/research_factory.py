"""Environment composition for the directly usable Codex research service."""

import os
import math
from dataclasses import dataclass
from pathlib import Path

from .biomedical_providers import (
    EuropePMCProvider, NCBIConfig, OpenAlexProvider, PubMedProvider, UnpaywallFallback,
)
from .codex_client import CodexClient
from .codex_roles import CodexPlanner, CodexReader, CodexScreener, CodexSynthesizer
from .conversation_memory import ConversationMemoryStore
from .harness import HarnessPolicy
from .research_expansion import ExpansionPolicy, ResearchExpander
from .research_memory import SQLiteResearchStore
from .memory_answer import CodexMemoryAnswerer
from .research_screening import HybridScreener
from .research_service import ResearchService
from .research_workflow import ResearchController


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    plugin_root: Path
    memory_path: Path
    codex_timeout: float | None = None
    max_readers: int = 4
    max_queries: int = 12
    max_expansion_queries: int = 6
    codex_executable: str = "codex"
    max_results_per_query: int = 10
    max_reader_documents: int = 6
    max_memory_hits: int = 8
    max_memory_prompt_chars: int = 8000

    @classmethod
    def from_env(cls, plugin_root: Path):
        value = os.getenv("FROGENT_MEMORY_DB", "").strip()
        if not value:
            raise ValueError("FROGENT_MEMORY_DB must explicitly configure persistent memory")
        path = Path(value)
        path = path if path.is_absolute() else plugin_root / path
        return cls(plugin_root, path, _optional_timeout(os.getenv("FROGENT_CODEX_TIMEOUT", "")),
                   int(os.getenv("FROGENT_MAX_READERS", "4")),
                   int(os.getenv("FROGENT_MAX_QUERIES", "12")),
                   int(os.getenv("FROGENT_MAX_EXPANSION_QUERIES", "6")),
                   os.getenv("FROGENT_CODEX_EXECUTABLE", "codex").strip() or "codex",
                   int(os.getenv("FROGENT_MAX_RESULTS_PER_QUERY", "10")),
                   int(os.getenv("FROGENT_MAX_READER_DOCUMENTS", "6")),
                   int(os.getenv("FROGENT_MAX_MEMORY_HITS", "8")),
                   int(os.getenv("FROGENT_MAX_MEMORY_PROMPT_CHARS", "8000")))


def _optional_timeout(raw: str) -> float | None:
    text = raw.strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError("FROGENT_CODEX_TIMEOUT must be zero or a positive finite number") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError("FROGENT_CODEX_TIMEOUT must be zero or a positive finite number")
    return None if value == 0 else value


class OAFallbackResolver:
    def __init__(self, primary, fallback=None) -> None:
        self.primary, self.fallback, self.failures = primary, fallback, {}

    def resolve(self, record, context):
        try:
            document = self.primary.resolve(record, context)
        except Exception as exc:
            self.failures[record.id] = f"Europe PMC OA failed: {type(exc).__name__}: {exc}"
            document = None
        primary_gap = (self.primary.coverage_gap(record.id) if callable(
            getattr(self.primary, "coverage_gap", None)) else "")
        if primary_gap:
            self.failures[record.id] = primary_gap
        if document or not self.fallback:
            return document
        try:
            return self.fallback.resolve(record, context)
        except Exception as exc:
            primary = self.failures.pop(record.id, "Europe PMC OA unavailable")
            raise RuntimeError(f"{primary}; OA fallback failed: {type(exc).__name__}: {exc}") from exc

    def coverage_gap(self, record_id: str) -> str:
        return self.failures.pop(record_id, "")


def build_research_service(config: RuntimeConfig, *, runner=None) -> ResearchService:
    root = config.plugin_root.resolve()
    client_args = {"timeout": config.codex_timeout, "executable": config.codex_executable}
    if runner is not None:
        client_args["runner"] = runner
    client = CodexClient(root, **client_args)
    europe = EuropePMCProvider()
    providers, routes, gaps = {"europe-pmc.search": europe}, ["europe_pmc"], []
    email = os.getenv("FROGENT_PUBMED_EMAIL", "").strip()
    if email:
        providers["pubmed.search"] = PubMedProvider(NCBIConfig(
            email, os.getenv("FROGENT_PUBMED_TOOL", "frogent"), os.getenv("NCBI_API_KEY", "")))
        routes.append("pubmed")
    else:
        gaps.append("PubMed unavailable: FROGENT_PUBMED_EMAIL is unset")
    openalex, openalex_gap = OpenAlexProvider.from_env()
    unpaywall, unpaywall_gap = UnpaywallFallback.from_env()
    gaps.extend(item for item in (openalex_gap, unpaywall_gap) if item)
    expander = ResearchExpander(europe, openalex, ExpansionPolicy(config.max_expansion_queries))
    controller = ResearchController(providers, {"europe_pmc": OAFallbackResolver(europe, unpaywall)},
        CodexReader(client), CodexSynthesizer(client), HarnessPolicy(max_tool_calls=32),
        config.max_readers, HybridScreener(CodexScreener(client)), expander, tuple(gaps),
        max_reader_documents=config.max_reader_documents)
    planner = CodexPlanner(client, tuple(routes), config.max_queries, config.max_results_per_query)
    store = SQLiteResearchStore(config.memory_path, root)
    memory_store = ConversationMemoryStore(config.memory_path, root)
    return ResearchService(planner, controller, store, root, memory_store=memory_store,
                           memory_answerer=CodexMemoryAnswerer(client, config.max_memory_prompt_chars),
                           max_memory_hits=config.max_memory_hits,
                           max_memory_prompt_chars=config.max_memory_prompt_chars)
