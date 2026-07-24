"""Stable capability IDs mapped to the current FROGENT MCP tools."""

from agent.core.contracts import Capability
from agent.core.registry import CapabilityRegistry


def _capability(id: str, server: str, tool: str, summary: str) -> Capability:
    return Capability(id=id, server=server, tool=tool, summary=summary)


CAPABILITIES = (
    _capability(
        "target.discover",
        "target-discovery",
        "get_Protein_and_Drugs_from_Disease",
        "Find a disease-associated target and known ligands.",
    ),
    _capability(
        "target.standardize",
        "target-discovery",
        "get_Standardized_Target_Name",
        "Resolve a target name and structure identifier.",
    ),
    _capability(
        "protein.download",
        "target-discovery",
        "download_Protein_File",
        "Download a protein structure for downstream tools.",
    ),
    _capability(
        "target.list-by-disease",
        "target-discovery",
        "get_all_Proteins_from_Disease",
        "List candidate targets associated with a disease.",
    ),
    _capability(
        "drug.list-by-target",
        "target-discovery",
        "get_all_drugs_from_Protein",
        "List known ligands associated with a target.",
    ),
    _capability(
        "pocket.find",
        "pocket-finder",
        "get_Pocket_Location_and_Size_and_Prepare_Pocket",
        "Find and prepare the leading protein pocket.",
    ),
    _capability(
        "pocket.prepare",
        "pocket-finder",
        "Prepare_Pocket",
        "Prepare a pocket from explicit center and size values.",
    ),
    _capability(
        "sar.analyze",
        "plip",
        "get_fragment_SA",
        "Analyze fragment-level protein interactions.",
    ),
    _capability(
        "sar.analyze-with-docking",
        "plip",
        "get_fragments_SA_with_docking",
        "Dock a molecule and analyze fragment interactions.",
    ),
    _capability(
        "fragment.reconstruct",
        "plip",
        "reconstruct_frags",
        "Remove a selected fragment and rebuild attachment points.",
    ),
    _capability(
        "docking.score",
        "dockstring",
        "calculate_qvina_score",
        "Score molecules against a prepared protein pocket.",
    ),
    _capability(
        "docking.generate-conformation",
        "dockstring",
        "generate_docked_conformations",
        "Generate a docked ligand conformation.",
    ),
    _capability(
        "ligand.generate-from-fragments",
        "fraggen",
        "generate_smiles_from_fragments",
        "Generate molecules from one or two prepared fragments.",
    ),
    _capability(
        "retrosynthesis.flash",
        "direct-multistep",
        "generate_routes_flash",
        "Generate a fast, shallow retrosynthetic route set.",
    ),
    _capability(
        "retrosynthesis.explorer",
        "direct-multistep",
        "generate_routes_explorer",
        "Generate a deeper retrosynthetic route set.",
    ),
    _capability(
        "admet.predict",
        "admet-ai",
        "calculate_admet_properties",
        "Predict selected ADMET properties for one molecule.",
    ),
    _capability(
        "admet.compare",
        "admet-ai",
        "compare_admet_properties",
        "Compare selected ADMET properties for two molecules.",
    ),
    _capability(
        "peptide.docking-score",
        "mdockpep",
        "Peptide_protein_docking_vina_score",
        "Estimate a peptide-protein docking score.",
    ),
    _capability(
        "ligand.generate-in-pocket",
        "smiles-generator",
        "Smile_Generation_in_Pocket",
        "Generate ligand candidates inside a prepared pocket.",
    ),
)

SERVER_NAMES = frozenset(capability.server for capability in CAPABILITIES)


def build_registry() -> CapabilityRegistry:
    return CapabilityRegistry(CAPABILITIES)
