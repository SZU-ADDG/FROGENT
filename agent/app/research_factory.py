"""Environment composition for the directly usable Codex research service."""

import os
import math
from dataclasses import dataclass
from pathlib import Path

from agent.research.biomedical_providers import (
    EuropePMCProvider, NCBIConfig, OpenAlexProvider, PubMedProvider, UnpaywallFallback,
)
from agent.llm.client_factory import build_llm_client, llm_settings_from_env
from agent.research.clinical_trials import ClinicalTrialsResolver
from agent.llm.codex_roles import CodexPlanner, CodexReader, CodexScreener, CodexSynthesizer
from agent.app.conversation_memory import ConversationMemoryStore
from agent.core.harness import HarnessPolicy
from agent.research.research_expansion import ExpansionPolicy, ResearchExpander
from agent.research.research_memory import SQLiteResearchStore
from agent.research.repository_fulltext import OpenAlexRepositoryLocator, OpenAlexRepositoryResolver
from agent.app.memory_answer import CodexMemoryAnswerer
from agent.molecular.admet_ai_adapter import ADMETAIAdapter
from agent.molecular.molecular_chat import MolecularChatHandler
from agent.molecular.molecular_chat_plan import CodexMolecularPlanner
from agent.design.design_memory import SQLiteDesignStore
from agent.design.design_workflow import QualitativeDesignHandler
from agent.design.qualitative_design import CodexDesignStrategist
from agent.docking.docking_chat import DockingChatHandler
from agent.docking.docking_chat_plan import CodexDockingPlanner
from agent.docking.docking_env import (dynamic_plip_from_env, dynamic_vina_from_env,
                          ligand_states_from_env, receptor_states_from_env)
from agent.docking.docking_microstates import DimorphiteConfig, DimorphiteMicrostateProvider
from agent.docking.docking_local import PLIPConfig
from agent.docking.docking_types import DockingConfig
from agent.docking.dynamic_receptor import ReceptorComponentPolicy
from agent.docking.dynamic_vina import DynamicVinaConfig, DynamicVinaInputPreparer
from agent.docking.dynamic_plip import DynamicPLIPConfig, DynamicPLIPInputPreparer
from agent.docking.receptor_states import PDB2PQRConfig, PDB2PQRReceptorStateProvider
from agent.docking.vina_plip_adapters import PLIPInteractionAdapter, VinaDockingAdapter
from agent.research.pdf_text import PypdfTextExtractor
from agent.molecular.pubchem_identity import PubChemIdentityResolver
from agent.research.research_screening import HybridScreener
from agent.app.research_service import ResearchService
from agent.research.research_workflow import ResearchController
from agent.docking.rcsb_pocket import RCSBPocketProvider
from agent.docking.rcsb_target import RCSBTargetProvider


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    project_root: Path
    memory_path: Path
    codex_timeout: float | None = None
    max_readers: int = 4
    max_queries: int = 12
    max_expansion_queries: int = 6
    codex_executable: str = "/Applications/ChatGPT.app/Contents/Resources/codex"
    max_results_per_query: int = 10
    max_reader_documents: int = 6
    max_memory_hits: int = 8
    max_memory_prompt_chars: int = 8000
    dynamic_vina: DynamicVinaConfig | None = None
    dynamic_plip: DynamicPLIPConfig | None = None
    ligand_states: DimorphiteConfig | None = None
    receptor_states: PDB2PQRConfig | None = None
    llm_backend: str = "deepseek"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_timeout: float | None = None
    codex_model: str = "gpt-5.6-luna"
    codex_reasoning_effort: str = "max"
    openrouter_model: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout: float | None = None

    @classmethod
    def from_env(cls, project_root: Path):
        value = os.getenv("FROGENT_MEMORY_DB", "").strip()
        if not value:
            raise ValueError("FROGENT_MEMORY_DB must explicitly configure persistent memory")
        path = Path(value)
        path = path if path.is_absolute() else project_root / path
        return cls(
            project_root=project_root,
            memory_path=path,
            codex_timeout=_optional_timeout(os.getenv("FROGENT_CODEX_TIMEOUT", "")),
            max_readers=int(os.getenv("FROGENT_MAX_READERS", "4")),
            max_queries=int(os.getenv("FROGENT_MAX_QUERIES", "12")),
            max_expansion_queries=int(os.getenv("FROGENT_MAX_EXPANSION_QUERIES", "6")),
            max_results_per_query=int(os.getenv("FROGENT_MAX_RESULTS_PER_QUERY", "10")),
            max_reader_documents=int(os.getenv("FROGENT_MAX_READER_DOCUMENTS", "6")),
            max_memory_hits=int(os.getenv("FROGENT_MAX_MEMORY_HITS", "8")),
            max_memory_prompt_chars=int(os.getenv("FROGENT_MAX_MEMORY_PROMPT_CHARS", "8000")),
            dynamic_vina=dynamic_vina_from_env(project_root),
            dynamic_plip=dynamic_plip_from_env(project_root),
            ligand_states=ligand_states_from_env(project_root),
            receptor_states=receptor_states_from_env(project_root),
            deepseek_timeout=_optional_timeout(os.getenv("FROGENT_DEEPSEEK_TIMEOUT", "")),
            openrouter_timeout=_optional_timeout(os.getenv("FROGENT_OPENROUTER_TIMEOUT", "")),
            **llm_settings_from_env(),
        )


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
                           design_calibrator=None, llm_client=None) -> ResearchService:
    root = config.project_root.resolve()
    client = llm_client
    if client is None:
        client = build_llm_client(
            root, backend=config.llm_backend, deepseek_model=config.deepseek_model,
            deepseek_base_url=config.deepseek_base_url, deepseek_timeout=config.deepseek_timeout,
            codex_model=config.codex_model, codex_reasoning_effort=config.codex_reasoning_effort,
            codex_executable=config.codex_executable,
            codex_timeout=config.codex_timeout, runner=runner,
            openrouter_model=config.openrouter_model,
            openrouter_base_url=config.openrouter_base_url,
            openrouter_timeout=config.openrouter_timeout)
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
                                     ADMETAIAdapter(matplotlib_cache=root / "runtime" / "app" /
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
    root = config.project_root.resolve(strict=True)
    vina = VinaDockingAdapter(root, vina_executable, vina_preparer, version=vina_version,
                              config=vina_config, runner=vina_runner)
    plip = PLIPInteractionAdapter(root, plip_executable, plip_preparer,
                                  version=plip_version, config=plip_config,
                                  runner=plip_runner)
    return vina, plip
