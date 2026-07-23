"""Typed ligand and receptor protonation state lineage."""

import math
from dataclasses import dataclass

from agent.core.contracts import ArtifactRef
from agent.docking.receptor_atom_types import ReceptorAddedHeavyAtom, ReceptorMovedHeavyAtom


@dataclass(frozen=True, slots=True)
class LigandStateSettings:
    ph_min: float
    ph_max: float
    precision: float
    max_protomers: int = 8
    max_tautomers: int = 8

    def __post_init__(self) -> None:
        values = (self.ph_min, self.ph_max, self.precision)
        if any(isinstance(item, bool) or not isinstance(item, (int, float))
               or not math.isfinite(item) for item in values):
            raise ValueError("ligand state pH settings must be finite numbers")
        if not 0 <= self.ph_min <= self.ph_max <= 14 or self.precision <= 0:
            raise ValueError("ligand state pH window or precision is invalid")
        if any(isinstance(item, bool) or not isinstance(item, int) or not 1 <= item <= 64
               for item in (self.max_protomers, self.max_tautomers)):
            raise ValueError("ligand state bounds must be integers between 1 and 64")
        if self.max_protomers * self.max_tautomers > 64:
            raise ValueError("total ligand microstate bound must not exceed 64")


@dataclass(frozen=True, slots=True)
class LigandMicrostate:
    state_id: str
    protomer_id: str
    canonical_isomeric_smiles: str
    inchikey: str
    formal_charge: int
    parent_connectivity_key: str
    ph_min: float
    ph_max: float
    precision: float
    protomer_tool: str
    protomer_version: str
    tautomer_tool: str
    tautomer_version: str
    source_inchikey: str
    source_artifact: ArtifactRef
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        texts = (self.state_id, self.protomer_id, self.canonical_isomeric_smiles,
                 self.inchikey, self.parent_connectivity_key, self.protomer_tool,
                 self.protomer_version, self.tautomer_tool, self.tautomer_version,
                 self.source_inchikey)
        if any(not item.strip() for item in texts):
            raise ValueError("ligand microstate identity or provenance is incomplete")
        if isinstance(self.formal_charge, bool) or not isinstance(self.formal_charge, int):
            raise ValueError("ligand microstate charge must be an integer")
        if (any(isinstance(item, bool) or not isinstance(item, (int, float))
                or not math.isfinite(item) for item in (self.ph_min, self.ph_max, self.precision))
                or not 0 <= self.ph_min <= self.ph_max <= 14 or self.precision <= 0):
            raise ValueError("ligand microstate pH settings are invalid")
        if any(not isinstance(item, str) or not item.strip() for item in self.warnings):
            raise ValueError("ligand microstate warnings must be nonempty strings")


@dataclass(frozen=True, slots=True)
class ReceptorResidueState:
    residue_id: str
    chain: str
    auth_residue_number: str
    insertion_code: str
    group_name: str
    source_name: str
    prepared_name: str
    pka: float | None = None

    def __post_init__(self) -> None:
        if any(not item.strip() for item in (
                self.residue_id, self.chain, self.auth_residue_number,
                self.group_name, self.source_name, self.prepared_name)):
            raise ValueError("receptor residue state is incomplete")
        if self.pka is not None and (isinstance(self.pka, bool)
                or not isinstance(self.pka, (int, float)) or not math.isfinite(self.pka)):
            raise ValueError("receptor residue pKa must be finite")


@dataclass(frozen=True, slots=True)
class ReceptorStateSettings:
    ph: float
    force_field: str = "PARSE"

    def __post_init__(self) -> None:
        if isinstance(self.ph, bool) or not isinstance(self.ph, (int, float)) \
                or not math.isfinite(self.ph) or not 0 <= self.ph <= 14:
            raise ValueError("receptor pH must be finite and between 0 and 14")
        if self.force_field not in {"AMBER", "CHARMM", "PARSE", "TYL06", "PEOEPB", "SWANSON"}:
            raise ValueError("receptor force field is unsupported")


@dataclass(frozen=True, slots=True)
class ReceptorStateBinding:
    state_id: str
    target_identifier: str
    target_artifact_id: str
    chain: str
    ph: float
    force_field: str
    provider: str
    provider_version: str
    propka_version: str
    propka_executable: str
    artifact: ArtifactRef
    charge_artifact: ArtifactRef
    command_argv: tuple[str, ...]
    residue_states: tuple[ReceptorResidueState, ...]
    polymer_heavy_atom_count: int
    source_polymer_heavy_atom_count: int
    added_heavy_atoms: tuple[ReceptorAddedHeavyAtom, ...] = ()
    moved_heavy_atoms: tuple[ReceptorMovedHeavyAtom, ...] = ()
    hydrogen_atom_count: int = 0
    zero_radius_hydrogen_count: int = 0

    def __post_init__(self) -> None:
        texts = (self.state_id, self.target_identifier, self.target_artifact_id,
                 self.chain, self.force_field, self.provider, self.provider_version,
                 self.propka_version, self.propka_executable)
        if any(not item.strip() for item in texts):
            raise ValueError("receptor state identity or provenance is incomplete")
        if isinstance(self.ph, bool) or not isinstance(self.ph, (int, float)) \
                or not math.isfinite(self.ph) or not 0 <= self.ph <= 14:
            raise ValueError("receptor state pH must be finite and between 0 and 14")
        counts = (self.polymer_heavy_atom_count, self.source_polymer_heavy_atom_count)
        if any(isinstance(item, bool) or not isinstance(item, int) or item <= 0
               for item in counts):
            raise ValueError("receptor state heavy atom count is invalid")
        hydrogen_counts = (self.hydrogen_atom_count, self.zero_radius_hydrogen_count)
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0
               for item in hydrogen_counts) or self.zero_radius_hydrogen_count > \
                self.hydrogen_atom_count:
            raise ValueError("receptor state hydrogen counts are invalid")
        if self.force_field not in {"AMBER", "CHARMM", "PARSE", "TYL06", "PEOEPB", "SWANSON"}:
            raise ValueError("receptor state force field is unsupported")
        if not self.command_argv or any(not item.strip() for item in self.command_argv):
            raise ValueError("receptor state command provenance is incomplete")
        residue_ids = tuple(item.residue_id for item in self.residue_states)
        if len(residue_ids) != len(set(residue_ids)):
            raise ValueError("receptor residue state IDs must be unique")
        if not any(item.pka is not None for item in self.residue_states):
            raise ValueError("receptor state requires at least one exact PROPKA pKa group")
        added_ids = tuple((item.chain, item.auth_residue_number, item.insertion_code,
                           item.residue_name, item.atom_name)
                          for item in self.added_heavy_atoms)
        if len(added_ids) != len(set(added_ids)):
            raise ValueError("receptor added heavy atom IDs must be unique")
        moved_ids = tuple((item.chain, item.auth_residue_number, item.insertion_code,
                           item.residue_name, item.atom_name) for item in self.moved_heavy_atoms)
        if len(moved_ids) != len(set(moved_ids)) or len(moved_ids) > 256 \
                or len(moved_ids) * 10 > self.source_polymer_heavy_atom_count \
                or any(item.chain != self.chain for item in self.moved_heavy_atoms):
            raise ValueError("receptor moved heavy atom set exceeds its bound")
        if (self.artifact.id == self.charge_artifact.id
                or self.artifact.uri == self.charge_artifact.uri):
            raise ValueError("receptor structure and charge artifacts must be distinct")
