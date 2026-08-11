"""JSON schemas for FROGENT chemistry MCP tools."""

TOOLS = (
    {
        "name": "describe_molecules",
        "description": (
            "Calculate canonical RDKit physicochemical descriptors, QED, Lipinski "
            "violations and the Veber rule for up to 256 SMILES."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "smiles": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                    "maxItems": 256,
                }
            },
            "required": ["smiles"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rank_molecular_similarity",
        "description": (
            "Rank up to 256 candidate SMILES by Morgan-fingerprint Tanimoto "
            "similarity to one query molecule."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query_smiles": {"type": "string", "minLength": 1},
                "candidate_smiles": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                    "maxItems": 256,
                },
                "radius": {"type": "integer", "minimum": 1, "maximum": 4},
                "n_bits": {"type": "integer", "enum": [1024, 2048, 4096]},
            },
            "required": ["query_smiles", "candidate_smiles"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rank_target_active_similarity",
        "description": (
            "Resolve a human protein target in ChEMBL, retrieve curated potent IC50 "
            "actives, and rank candidate SMILES by Morgan-Tanimoto similarity."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "minLength": 1},
                "candidate_smiles": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                    "maxItems": 256,
                },
                "max_unique_actives": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5000,
                },
                "min_pchembl": {"type": "number", "minimum": 0, "maximum": 14},
            },
            "required": ["target", "candidate_smiles"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rank_pdb_ligand_similarity",
        "description": (
            "Retrieve structured non-polymer ligands from an RCSB PDB entry and rank "
            "candidate SMILES by Morgan-Tanimoto similarity."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdb_id": {"type": "string", "minLength": 4, "maxLength": 4},
                "candidate_smiles": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                    "maxItems": 256,
                },
            },
            "required": ["pdb_id", "candidate_smiles"],
            "additionalProperties": False,
        },
    },
)

TOOL_NAMES = frozenset(item["name"] for item in TOOLS)
