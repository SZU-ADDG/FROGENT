"""Environment composition for the directly usable Codex research service."""

import os
import math
from dataclasses import dataclass
from pathlib import Path

from .biomedical_providers import (
    EuropePMCProvider, NCBIConfig, OpenAlexProvider, PubMedProvider, UnpaywallFallback,
)
from .codex_client import CodexClient
from .clinical_trials import ClinicalTrialsResolver
from .codex_roles import CodexPlanner, CodexReader, CodexScreener, CodexSynthesizer
from .conversation_memory import ConversationMemoryStore
from .harness import HarnessPolicy
from .research_expansion import ExpansionPolicy, ResearchExpander
from .research_memory import SQLiteResearchStore
from .repository_fulltext import OpenAlexRepositoryLocator, OpenAlexRepositoryResolver
from .memory_answer import CodexMemoryAnswerer
from .admet_ai_adapter import ADMETAIAdapter
from .molecular_chat import MolecularChatHandler
from .molecular_chat_plan import CodexMolecularPlanner
from .design_memory import SQLiteDesignStore
from .design_workflow import QualitativeDesignHandler
from .qualitative_design import CodexDesignStrategist
from .docking_chat import DockingChatHandler
from .docking_chat_plan import CodexDockingPlanner
from .docking_env import (dynamic_plip_from_env, dynamic_vina_from_env,
                          ligand_states_from_env, receptor_states_from_env)
from .docking_microstates import DimorphiteConfig, DimorphiteMicrostateProvider
from .docking_local import PLIPConfig
from .docking_types import DockingConfig
from .dynamic_receptor import ReceptorComponentPolicy
from .dynamic_vina import DynamicVinaConfig, DynamicVinaInputPreparer
from .dynamic_plip import DynamicPLIPConfig, DynamicPLIPInputPreparer
from .receptor_states import PDB2PQRConfig, PDB2PQRReceptorStateProvider
from .vina_plip_adapters import PLIPInteractionAdapter, VinaDockingAdapter
from .pdf_text import PypdfTextExtractor
from .pubchem_identity import PubChemIdentityResolver
from .research_screening import HybridScreener
from .research_service import ResearchService
from .research_workflow import ResearchController
from .rcsb_pocket import RCSBPocketProvider
from .rcsb_target import RCSBTargetProvider


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
    dynamic_vina: DynamicVinaConfig | None = None
    dynamic_plip: DynamicPLIPConfig | None = None
    ligand_states: DimorphiteConfig | None = None
    receptor_states: PDB2PQRConfig | None = None

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
                   int(os.getenv("FROGENT_MAX_MEMORY_PROMPT_CHARS", "8000")),
                   dynamic_vina_from_env(plugin_root), dynamic_plip_from_env(plugin_root),
                   ligand_states_from_env(plugin_root), receptor_states_from_env(plugin_root))


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
    def __init__(self, primary, fallback=None, repository=None) -> None:
        self.primary, self.repository, self.fallback = primary, repository, fallback
        self.failures = {}

    def resolve(self, record, context):
        self.failures.pop(record.id, None)
        gaps = []
        try:
            document = self.primary.resolve(record, context)
        except Exception as exc:
            gaps.append(f"Europe PMC OA failed: {type(exc).__name__}: {exc}")
            document = None
        primary_gap = (self.primary.coverage_gap(record.id) if callable(
            getattr(self.primary, "coverage_gap", None)) else "")
        if primary_gap:
            gaps.append(primary_gap)
        if document:
            return self._finish(record.id, document, gaps)
        if self.repository:
            try:
                document = self.repository.resolve(record, context)
            except Exception as exc:
                gaps.append(f"OpenAlex repository resolver failed: {type(exc).__name__}: {exc}")
                document = None
            repository_gap = (self.repository.coverage_gap(record.id) if callable(
                getattr(self.repository, "coverage_gap", None)) else "")
            if repository_gap:
                gaps.append(repository_gap)
            if document:
                return self._finish(record.id, document, gaps)
        if not self.fallback:
            return self._finish(record.id, None, gaps)
        try:
            document = self.fallback.resolve(record, context)
        except Exception as exc:
            detail = "; ".join(gaps) or "Europe PMC OA unavailable"
            raise RuntimeError(f"{detail}; OA fallback failed: {type(exc).__name__}: {exc}") from exc
        return self._finish(record.id, document, gaps)

    def _finish(self, record_id, document, gaps):
        if gaps:
            self.failures[record_id] = "; ".join(dict.fromkeys(gaps))
        return document

    def coverage_gap(self, record_id: str) -> str:
        return self.failures.pop(record_id, "")


def build_research_service(config: RuntimeConfig, *, runner=None, pdf_extractor=None,
                           target_provider=None, pocket_provider=None, docking_provider=None,
                           interaction_provider=None, rcsb_transport=None,
                           docking_runner=None, docking_conformer=None,
                           plip_runner=None, plip_ligand_builder=None,
                           design_calibrator=None) -> ResearchService:
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
    pdf_gap = None
    if pdf_extractor is None:
        try:
            pdf_extractor = PypdfTextExtractor()
        except ModuleNotFoundError as exc:
            pdf_gap = f"Repository PDF extraction unavailable: pypdf>=6,<7 is not installed ({exc})"
    repository = OpenAlexRepositoryResolver(OpenAlexRepositoryLocator(api_key=os.getenv(
        "OPENALEX_API_KEY", "")), pdf_extractor)
    unpaywall, unpaywall_gap = UnpaywallFallback.from_env()
    gaps.extend(item for item in (openalex_gap, unpaywall_gap, pdf_gap) if item)
    expander = ResearchExpander(europe, openalex, ExpansionPolicy(config.max_expansion_queries))
    controller = ResearchController(providers, {"europe_pmc": OAFallbackResolver(
        europe, unpaywall, repository)},
        CodexReader(client), CodexSynthesizer(client), HarnessPolicy(max_tool_calls=32),
        config.max_readers, HybridScreener(CodexScreener(client)), expander, tuple(gaps),
        max_reader_documents=config.max_reader_documents,
        registry_resolver=ClinicalTrialsResolver())
    planner = CodexPlanner(client, tuple(routes), config.max_queries, config.max_results_per_query)
    store = SQLiteResearchStore(config.memory_path, root)
    memory_store = ConversationMemoryStore(config.memory_path, root)
    molecular = MolecularChatHandler(CodexMolecularPlanner(client), PubChemIdentityResolver(),
                                     ADMETAIAdapter(matplotlib_cache=root / ".runtime" / "app-v4" /
                                                    "matplotlib"))
    design = QualitativeDesignHandler(CodexDesignStrategist(client),
                                      SQLiteDesignStore(config.memory_path, root),
                                      design_calibrator)
    target_provider = target_provider or RCSBTargetProvider(root, transport=rcsb_transport)
    pocket_provider = pocket_provider or RCSBPocketProvider(root)
    if docking_provider is None and config.dynamic_vina:
        preparer = DynamicVinaInputPreparer(root, config.dynamic_vina,
            runner=docking_runner, conformer=docking_conformer)
        docking_provider = VinaDockingAdapter(root, config.dynamic_vina.vina_executable,
            preparer, version=config.dynamic_vina.vina_version,
            config=config.dynamic_vina.docking_config, runner=docking_runner)
    if interaction_provider is None and config.dynamic_plip:
        preparer = DynamicPLIPInputPreparer(root, config.dynamic_plip,
            ligand_builder=plip_ligand_builder)
        interaction_provider = PLIPInteractionAdapter(root, config.dynamic_plip.executable,
            preparer, version=config.dynamic_plip.version,
            config=config.dynamic_plip.plip_config, runner=plip_runner)
    microstates = (DimorphiteMicrostateProvider(root, config.ligand_states)
                   if config.ligand_states else None)
    receptor_states = (PDB2PQRReceptorStateProvider(root, config.receptor_states)
                       if config.receptor_states else None)
    docking = DockingChatHandler(CodexDockingPlanner(client), PubChemIdentityResolver(),
        target_provider=target_provider, pocket_provider=pocket_provider,
        docking_provider=docking_provider, interaction_provider=interaction_provider,
        microstate_provider=microstates, receptor_state_provider=receptor_states)
    return ResearchService(planner, controller, store, root, memory_store=memory_store,
                           memory_answerer=CodexMemoryAnswerer(client, config.max_memory_prompt_chars),
                           max_memory_hits=config.max_memory_hits,
                           max_memory_prompt_chars=config.max_memory_prompt_chars,
                           design_handler=design, molecular_handler=molecular,
                           docking_handler=docking)


def build_local_docking_adapters(config: RuntimeConfig, *, vina_executable: Path,
                                 plip_executable: Path, vina_preparer, plip_preparer,
                                 vina_version: str, plip_version: str,
                                 vina_config: DockingConfig | None = None,
                                 plip_config: PLIPConfig | None = None,
                                 vina_runner=None, plip_runner=None):
    """Construct contained real-tool adapters after exact prepared inputs are bound."""
    root = config.plugin_root.resolve(strict=True)
    vina = VinaDockingAdapter(root, vina_executable, vina_preparer, version=vina_version,
                              config=vina_config, runner=vina_runner)
    plip = PLIPInteractionAdapter(root, plip_executable, plip_preparer,
                                  version=plip_version, config=plip_config,
                                  runner=plip_runner)
    return vina, plip
