"""Bounded Agent-visible ligand and receptor state lineage."""

import math
from dataclasses import dataclass

from agent.docking.docking_state_types import ReceptorResidueState
from agent.docking.receptor_atom_types import ReceptorAddedHeavyAtom, ReceptorMovedHeavyAtom


@dataclass(frozen=True, slots=True)
class DockingStateLineage:
    ligand_state_id: str = ""
    receptor_state_id: str = ""
    receptor_ph: float | None = None
    receptor_force_field: str = ""
    receptor_source_heavy_atom_count: int = 0
    receptor_prepared_heavy_atom_count: int = 0
    receptor_added_heavy_atoms: tuple[ReceptorAddedHeavyAtom, ...] = ()
    receptor_moved_heavy_atom_count: int = 0
    receptor_max_displacement: float = 0.0
    receptor_moved_heavy_atoms: tuple[ReceptorMovedHeavyAtom, ...] = ()
    receptor_hydrogen_atom_count: int = 0
    receptor_zero_radius_hydrogen_count: int = 0
    receptor_pka_group_count: int = 0
    receptor_near_ph_pka_groups: tuple[ReceptorResidueState, ...] = ()

    def __post_init__(self) -> None:
        present = bool(self.receptor_state_id)
        if present != (self.receptor_ph is not None) or present != bool(
                self.receptor_force_field):
            raise ValueError("docking receptor state lineage must be complete")
        self._validate_counts(present)
        self._validate_moves(present)
        self._validate_pka(present)

    def _validate_counts(self, present):
        counts = (self.receptor_source_heavy_atom_count,
                  self.receptor_prepared_heavy_atom_count)
        hydrogens = (self.receptor_hydrogen_atom_count,
                     self.receptor_zero_radius_hydrogen_count)
        if present and any(isinstance(item, bool) or not isinstance(item, int) or item <= 0
                           for item in counts):
            raise ValueError("docking receptor state atom counts must be positive integers")
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0
               for item in hydrogens) or hydrogens[1] > hydrogens[0]:
            raise ValueError("docking receptor hydrogen summary is invalid")
        if not present and (any(counts) or any(hydrogens) or self.receptor_added_heavy_atoms):
            raise ValueError("docking receptor atom lineage requires a receptor state")

    def _validate_moves(self, present):
        identities = tuple((item.chain, item.auth_residue_number, item.insertion_code,
            item.residue_name, item.atom_name) for item in self.receptor_moved_heavy_atoms)
        invalid = (self.receptor_moved_heavy_atom_count < 0
            or not math.isfinite(self.receptor_max_displacement)
            or self.receptor_max_displacement < 0 or len(identities) > 16
            or self.receptor_moved_heavy_atom_count < len(identities)
            or len(identities) != len(set(identities)))
        if present and invalid:
            raise ValueError("docking receptor move summary is invalid")
        empty = self.receptor_moved_heavy_atom_count == 0
        if empty != (self.receptor_max_displacement == 0
                     and not self.receptor_moved_heavy_atoms):
            raise ValueError("docking receptor move summary is inconsistent")
        if not present and not empty:
            raise ValueError("docking receptor move lineage requires a receptor state")
        if identities:
            self._validate_move_order()

    def _validate_move_order(self):
        summary_max = max(item.displacement for item in self.receptor_moved_heavy_atoms)
        expected = tuple(sorted(self.receptor_moved_heavy_atoms, key=_move_key))
        if expected != self.receptor_moved_heavy_atoms \
                or self.receptor_max_displacement < summary_max \
                or (self.receptor_moved_heavy_atom_count <= 16 and not math.isclose(
                    self.receptor_max_displacement, summary_max, rel_tol=0, abs_tol=1e-9)):
            raise ValueError("docking receptor maximum displacement is inconsistent")

    def _validate_pka(self, present):
        groups = self.receptor_near_ph_pka_groups
        identities = tuple(item.residue_id for item in groups)
        if isinstance(self.receptor_pka_group_count, bool) \
                or not isinstance(self.receptor_pka_group_count, int):
            raise ValueError("docking receptor pKa group count must be an integer")
        if not present and (self.receptor_pka_group_count or groups):
            raise ValueError("docking receptor pKa lineage requires a receptor state")
        if present and (self.receptor_pka_group_count < 1 or not groups
                or len(groups) > 16 or self.receptor_pka_group_count < len(groups)
                or len(identities) != len(set(identities))
                or any(item.pka is None for item in groups)):
            raise ValueError("docking receptor pKa summary is invalid")
        if present and tuple(sorted(groups, key=lambda item: _pka_key(
                item, self.receptor_ph))) != groups:
            raise ValueError("docking receptor pKa summary order is invalid")


def state_lineage(value) -> DockingStateLineage:
    ligand, receptor = value.ligand_state, value.receptor_state
    moved = tuple(sorted(receptor.moved_heavy_atoms, key=_move_key)) if receptor else ()
    pka = tuple(sorted((item for item in receptor.residue_states if item.pka is not None),
                       key=lambda item: _pka_key(item, receptor.ph))) if receptor else ()
    return DockingStateLineage(ligand.state_id if ligand else "",
        receptor.state_id if receptor else "", receptor.ph if receptor else None,
        receptor.force_field if receptor else "",
        receptor.source_polymer_heavy_atom_count if receptor else 0,
        receptor.polymer_heavy_atom_count if receptor else 0,
        receptor.added_heavy_atoms if receptor else (), len(moved),
        max((item.displacement for item in moved), default=0.0), moved[:16],
        receptor.hydrogen_atom_count if receptor else 0,
        receptor.zero_radius_hydrogen_count if receptor else 0, len(pka), pka[:16])


def validate_input_states(value) -> None:
    if value.ligand_state and (value.ligand_state.canonical_isomeric_smiles,
            value.ligand_state.inchikey) != (value.molecule.canonical_isomeric_smiles,
                                             value.molecule.inchikey):
        raise ValueError("docking molecule does not match selected ligand state")
    if value.receptor_state and (value.receptor_state.target_identifier,
            value.receptor_state.target_artifact_id, value.receptor_state.chain) != (
            value.target.identifier, value.target.structure_artifact.id, value.pocket.chain):
        raise ValueError("docking receptor state does not match target/pocket lineage")


def _move_key(item):
    return (-item.displacement, item.chain, item.auth_residue_number,
            item.insertion_code, item.residue_name, item.atom_name)


def _pka_key(item, ph):
    return (abs(item.pka - ph), item.residue_id)
