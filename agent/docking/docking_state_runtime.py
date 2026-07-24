"""Revalidate and expose the selected receptor state to Vina and PLIP."""

from dataclasses import dataclass
from pathlib import Path

from agent.docking.docking_state_types import ReceptorStateBinding
from agent.docking.docking_types import DockingInput
from agent.docking.dynamic_receptor import ReceptorComponentPolicy, select_receptor
from agent.docking.receptor_state_validation import revalidate_receptor_state


@dataclass(frozen=True, slots=True)
class SelectedReceptor:
    pdb: bytes
    pqr: Path | None
    details: tuple[str, ...]
    dropped_records: int


def selected_receptor(root: Path, value: DockingInput,
                      policy: ReceptorComponentPolicy) -> SelectedReceptor:
    source, decisions, dropped = select_receptor(root, value, policy)
    state = value.receptor_state
    if state is None:
        return SelectedReceptor(source, None, decisions, dropped)
    expected = (value.target.identifier, value.target.structure_artifact.id,
                value.pocket.chain)
    if (state.target_identifier, state.target_artifact_id, state.chain) != expected:
        raise ValueError("selected receptor state lineage mismatch")
    prepared, pqr_path = revalidate_receptor_state(root, state, source)
    details = (*decisions, f"receptor_state_id={state.state_id}",
               f"receptor_ph={state.ph:g}", f"receptor_force_field={state.force_field}",
               f"receptor_state_artifact_id={state.artifact.id}")
    return SelectedReceptor(prepared, pqr_path, details, dropped)


def prepare_receptor_state(target, pocket, provider, ph, gaps):
    if ph is None:
        gaps.append("pH-aware docking requires an explicit current-message receptor pH")
        return None
    try:
        configured = getattr(getattr(provider, "config", None), "settings", None)
        if configured is not None and configured.ph != ph:
            raise ValueError("configured receptor state pH does not match selected pH")
        state = provider.prepare(target, pocket)
        if not isinstance(state, ReceptorStateBinding) or state.ph != ph:
            raise ValueError("prepared receptor state does not match selected pH")
        return state
    except Exception as exc:
        gaps.append(f"receptor state preparation failed: {type(exc).__name__}: {exc}")
        return None
