"""Additive TrioWorkspace capabilities kept outside frozen eval identity."""

from __future__ import annotations

from .catalog import CAPABILITIES
from .contracts import Capability
from .registry import CapabilityRegistry


def _capability(id: str, tool: str, summary: str) -> Capability:
    return Capability(id=id, server="trio-workspace", tool=tool, summary=summary)


TRIOWORKSPACE_CAPABILITIES = (
    _capability("trio.health", "trio_health", "Check the private TrioWorkspace control plane."),
    _capability("trio.capabilities", "trio_capabilities", "Describe accepted Trio engine contracts."),
    _capability("trio.task.list", "trio_list_tasks", "List owned asynchronous Trio tasks."),
    _capability("trio.task.get", "trio_get_task", "Read one task and artifact metadata."),
    _capability(
        "trio.artifact.download",
        "trio_download_artifact",
        "Download a checksum-verified result artifact.",
    ),
    _capability(
        "trio.mol2.run",
        "trio_submit_mol2",
        "Run bounded structure-based small-molecule generation.",
    ),
    _capability(
        "trio.peptide.run",
        "trio_submit_peptide",
        "Run bounded receptor-conditioned peptide design.",
    ),
    _capability(
        "trio.protac.run",
        "trio_submit_protac",
        "Run the accepted BRD4 TrioPROTAC task.",
    ),
    _capability(
        "trio.ires.run",
        "trio_submit_ires",
        "Run bounded CrPV or PSIV IRES design.",
    ),
    _capability(
        "trio.dna.run",
        "trio_submit_dna",
        "Run bounded exact-context DNA design.",
    ),
)

TRIOWORKSPACE_SERVER_NAMES = frozenset({"trio-workspace"})
CURRENT_CAPABILITIES = (*CAPABILITIES, *TRIOWORKSPACE_CAPABILITIES)
CURRENT_SERVER_NAMES = frozenset(capability.server for capability in CURRENT_CAPABILITIES)


def build_current_registry() -> CapabilityRegistry:
    return CapabilityRegistry(CURRENT_CAPABILITIES)
