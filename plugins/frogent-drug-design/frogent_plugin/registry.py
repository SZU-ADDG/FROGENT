"""Capability lookup with duplicate and configuration checks."""

from collections.abc import Iterable

from .contracts import Capability


class CapabilityRegistry:
    def __init__(self, capabilities: Iterable[Capability] = ()) -> None:
        self._items: dict[str, Capability] = {}
        for capability in capabilities:
            self.register(capability)

    def register(self, capability: Capability) -> None:
        if capability.id in self._items:
            raise ValueError(f"duplicate capability id: {capability.id}")
        self._items[capability.id] = capability

    def get(self, capability_id: str) -> Capability:
        try:
            return self._items[capability_id]
        except KeyError as exc:
            raise KeyError(f"unknown capability: {capability_id}") from exc

    def all(self) -> tuple[Capability, ...]:
        return tuple(self._items[key] for key in sorted(self._items))

    def for_server(self, server: str) -> tuple[Capability, ...]:
        return tuple(item for item in self.all() if item.server == server)

    def require_servers(self, server_names: Iterable[str]) -> None:
        known = set(server_names)
        unknown = sorted({item.server for item in self._items.values()} - known)
        if unknown:
            raise ValueError(f"capabilities reference unknown servers: {', '.join(unknown)}")

    def __contains__(self, capability_id: object) -> bool:
        return capability_id in self._items

    def __len__(self) -> int:
        return len(self._items)
