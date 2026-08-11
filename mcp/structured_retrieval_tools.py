"""Typed tool facade for structured biomedical retrieval."""

from __future__ import annotations

from typing import Any

from agent.research.structured_target_evidence import (
    list_target_drugbank_links,
    rank_disease_targets,
)


class StructuredRetrievalTools:
    def call(self, name: str, arguments: Any) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        if name == "rank_disease_targets":
            if set(arguments) - {"disease", "max_results"}:
                raise ValueError("rank_disease_targets arguments are invalid")
            return rank_disease_targets(arguments.get("disease", ""),
                                        max_results=arguments.get("max_results", 10))
        if name == "list_target_drugbank_links":
            if set(arguments) - {"target", "max_results"}:
                raise ValueError("list_target_drugbank_links arguments are invalid")
            return list_target_drugbank_links(arguments.get("target", ""),
                                              max_results=arguments.get("max_results", 100))
        raise ValueError("unknown structured retrieval tool")
