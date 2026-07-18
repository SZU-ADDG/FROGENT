"""Exact molecular structure selection and executable tool bindings."""

from dataclasses import dataclass

from .molecular_identity import MolecularIdentity


@dataclass(frozen=True, slots=True)
class MolecularInputBinding:
    scope: str
    canonical_isomeric_smiles: str
    inchikey: str
    selection_confirmed: bool
    removed_fragments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.scope not in {"full", "parent_candidate"}:
            raise ValueError("molecular input binding scope is invalid")
        if not self.canonical_isomeric_smiles.strip() or not self.inchikey.strip():
            raise ValueError("molecular input binding identity is incomplete")
        if not isinstance(self.selection_confirmed, bool):
            raise ValueError("molecular input selection flag must be boolean")


@dataclass(frozen=True, slots=True)
class MolecularToolInput:
    candidate: MolecularInputBinding
    baseline: MolecularInputBinding | None
    role_order: tuple[str, ...]
    target_id: str = ""
    pocket_id: str = ""

    def __post_init__(self) -> None:
        if self.role_order not in {("candidate",), ("candidate", "baseline")}:
            raise ValueError("molecular tool role order is invalid")
        if self.role_order == ("candidate",) and self.baseline is not None:
            raise ValueError("non-comparison tool input cannot bind a baseline")


def selected_binding(adapter, identity: MolecularIdentity, scope: str | None,
                     selected_smiles: str) -> MolecularInputBinding:
    if scope not in {None, "full", "parent_candidate"}:
        raise ValueError("structure scope must be full or parent_candidate")
    if scope is None:
        if selected_smiles:
            raise ValueError("selected structure requires an explicit scope")
        return full_binding(identity)
    if scope == "full":
        if selected_smiles and normalized(adapter, selected_smiles).canonical_isomeric_smiles \
                != identity.canonical_isomeric_smiles:
            raise ValueError("selected full structure does not match normalized input")
        return MolecularInputBinding("full", identity.canonical_isomeric_smiles,
                                     identity.inchikey, True)
    if identity.parent_candidate is None:
        raise ValueError("parent_candidate structure is unavailable")
    if identity.organic_fragment_count > 1 and not selected_smiles:
        raise ValueError("multiple organic fragments require an exact selected fragment")
    chosen = normalized(adapter, selected_smiles) if selected_smiles else None
    parent = identity.parent_candidate
    if chosen is None:
        return MolecularInputBinding("parent_candidate", parent.canonical_isomeric_smiles,
                                     parent.inchikey, True, parent.removed_fragments)
    fragments = [parent.canonical_isomeric_smiles, *parent.removed_fragments]
    if chosen.fragment_count != 1 or chosen.organic_fragment_count != 1 \
            or chosen.canonical_isomeric_smiles not in fragments:
        raise ValueError("selected parent structure is not an exact normalized input fragment")
    fragments.remove(chosen.canonical_isomeric_smiles)
    return MolecularInputBinding("parent_candidate", chosen.canonical_isomeric_smiles,
                                 chosen.inchikey, True, tuple(sorted(fragments)))


def full_binding(identity: MolecularIdentity) -> MolecularInputBinding:
    return MolecularInputBinding("full", identity.canonical_isomeric_smiles, identity.inchikey,
                                 identity.fragment_count == 1)


def normalized(adapter, smiles: str) -> MolecularIdentity:
    value = adapter.normalize(smiles)
    if not isinstance(value, MolecularIdentity):
        raise TypeError("molecule normalizer returned an invalid identity")
    return value
