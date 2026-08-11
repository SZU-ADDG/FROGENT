"""JSON schemas for structured biomedical retrieval MCP tools."""

TOOLS = (
    {
        "name": "rank_disease_targets",
        "description": "Resolve a disease in Open Targets and return ranked associated targets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "disease": {"type": "string", "minLength": 1},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["disease"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_target_drugbank_links",
        "description": "Resolve a reviewed human UniProtKB target and list DrugBank cross-references.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "minLength": 1},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 250},
            },
            "required": ["target"],
            "additionalProperties": False,
        },
    },
)

TOOL_NAMES = frozenset(item["name"] for item in TOOLS)
