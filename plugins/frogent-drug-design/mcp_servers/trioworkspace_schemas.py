"""MCP tool schemas for the five accepted TrioWorkspace engines."""

from __future__ import annotations

from typing import Any


def _object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


TEXT = {"type": "string", "minLength": 1}
TASK_NAME = {"type": "string", "minLength": 1, "maxLength": 120}
NOTES = {"type": "string", "maxLength": 2000}
SEED = {"type": "integer", "minimum": 0, "maximum": 2147483647}
PDB_PATH = {
    "type": "string",
    "minLength": 1,
    "description": "Absolute path to a receptor PDB inside the FROGENT project.",
}


def _submission(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return _object(
        {"task_name": TASK_NAME, **properties, "notes": NOTES},
        ["task_name", *required],
    )


TOOLS = (
    {
        "name": "trio_health",
        "description": "Check the private TrioWorkspace control-plane service through SSH.",
        "inputSchema": _object({}, []),
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    {
        "name": "trio_capabilities",
        "description": "Describe accepted TrioMol2, TrioPep, TrioPROTAC, TrioDNA, and TrioIRES task contracts.",
        "inputSchema": _object({}, []),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "trio_list_tasks",
        "description": "List up to 100 tasks owned by the configured FROGENT Trio identity.",
        "inputSchema": _object({}, []),
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    {
        "name": "trio_get_task",
        "description": "Read one owned TrioWorkspace task, progress event, and artifact metadata.",
        "inputSchema": _object(
            {"task_id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{7,63}$"}},
            ["task_id"],
        ),
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    {
        "name": "trio_download_artifact",
        "description": "Download one verified owned task artifact into FROGENT .runtime and return its local path.",
        "inputSchema": _object(
            {
                "task_id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{7,63}$"},
                "artifact_id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{7,63}$"},
            },
            ["task_id", "artifact_id"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
    },
    {
        "name": "trio_submit_mol2",
        "description": "Submit a bounded TrioMol2 structure-based small-molecule generation task.",
        "inputSchema": _submission(
            {
                "target_name": {"type": "string", "minLength": 1, "maxLength": 120},
                "receptor_pdb_path": PDB_PATH,
                "center": {
                    "type": "array", "items": {"type": "number", "minimum": -10000, "maximum": 10000},
                    "minItems": 3, "maxItems": 3,
                },
                "size": {
                    "type": "array", "items": {"type": "number", "exclusiveMinimum": 0, "maximum": 64},
                    "minItems": 3, "maxItems": 3,
                },
                "candidate_count": {"type": "integer", "minimum": 1, "maximum": 10},
                "search_budget": {"type": "integer", "enum": [100, 200, 500]},
                "seed": SEED,
            },
            ["target_name", "receptor_pdb_path", "center", "size", "candidate_count", "search_budget", "seed"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "trio_submit_peptide",
        "description": "Submit a bounded TrioPep receptor-conditioned peptide design task.",
        "inputSchema": _submission(
            {
                "receptor_pdb_path": PDB_PATH,
                "receptor_chain": {"type": "string", "pattern": "^[A-Za-z0-9]$"},
                "peptide_chain": {"type": "string", "pattern": "^[A-Za-z0-9]$"},
                "peptide_length": {"type": "integer", "minimum": 4, "maximum": 20},
                "search_budget": {"type": "integer", "enum": [4, 8, 16]},
            },
            ["receptor_pdb_path", "receptor_chain", "peptide_chain", "peptide_length", "search_budget"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "trio_submit_protac",
        "description": "Submit the accepted BRD4 8G46 TrioPROTAC design task.",
        "inputSchema": _submission(
            {
                "target_system": {"type": "string", "enum": ["brd4-8g46"]},
                "search_budget": {"type": "integer", "enum": [8, 16, 32]},
                "seed": SEED,
            },
            ["target_system", "search_budget", "seed"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "trio_submit_ires",
        "description": "Submit a bounded TrioIRES CrPV or PSIV RNA design task.",
        "inputSchema": _submission(
            {
                "family": {"type": "string", "enum": ["CrPV", "PSIV"]},
                "search_budget": {"type": "integer", "enum": [1, 2, 4]},
                "seed": SEED,
            },
            ["family", "search_budget", "seed"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "trio_submit_dna",
        "description": "Submit a TrioDNA task for an exact 200-base reference and editable interval.",
        "inputSchema": _submission(
            {
                "cell_context": {"type": "string", "enum": ["HepG2", "K562", "SK-N-SH"]},
                "reference_sequence": {"type": "string", "pattern": "^[ACGTacgt\\s]{200,400}$"},
                "editable_start": {"type": "integer", "minimum": 1, "maximum": 200},
                "editable_end": {"type": "integer", "minimum": 1, "maximum": 200},
                "candidate_count": {"type": "integer", "minimum": 1, "maximum": 10},
                "seed": SEED,
            },
            ["cell_context", "reference_sequence", "editable_start", "editable_end", "candidate_count", "seed"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
)


TOOL_NAMES = frozenset(tool["name"] for tool in TOOLS)
