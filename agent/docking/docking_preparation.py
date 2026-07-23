"""Typed provenance for lossless docking artifact preparation."""

from dataclasses import dataclass

from agent.core.contracts import ArtifactRef


@dataclass(frozen=True, slots=True)
class PreparationProvenance:
    tool: str
    version: str
    source_artifacts: tuple[ArtifactRef, ...]
    output_artifacts: tuple[ArtifactRef, ...]
    command_argv: tuple[str, ...]
    operation: str
    lossless: bool
    moved_record_count: int = 0
    dropped_record_count: int = 0
    details: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (self.tool, self.version, self.operation, *self.command_argv)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("preparation provenance text must be non-empty")
        if not self.source_artifacts or not self.output_artifacts:
            raise ValueError("preparation provenance requires sources and outputs")
        if not isinstance(self.lossless, bool):
            raise ValueError("preparation lossless flag must be boolean")
        counts = (self.moved_record_count, self.dropped_record_count)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
               for value in counts):
            raise ValueError("preparation record counts must be non-negative integers")
        if self.lossless and self.dropped_record_count:
            raise ValueError("lossless preparation cannot drop records")
        if any(not isinstance(value, str) or not value.strip() for value in self.details):
            raise ValueError("preparation details must be non-empty strings")
