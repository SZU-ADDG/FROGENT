"""Typed heavy-atom changes made during receptor state preparation."""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReceptorAddedHeavyAtom:
    chain: str
    auth_residue_number: str
    insertion_code: str
    residue_name: str
    atom_name: str
    coordinates: tuple[float, float, float]

    def __post_init__(self) -> None:
        if (not self.chain.strip() or not self.auth_residue_number.strip()
                or not self.residue_name.strip() or self.atom_name != "OXT"
                or len(self.coordinates) != 3 or any(not math.isfinite(item)
                for item in self.coordinates)):
            raise ValueError("receptor added heavy atom provenance is invalid")


@dataclass(frozen=True, slots=True)
class ReceptorMovedHeavyAtom:
    chain: str
    auth_residue_number: str
    insertion_code: str
    residue_name: str
    atom_name: str
    source_coordinates: tuple[float, float, float]
    prepared_coordinates: tuple[float, float, float]
    displacement: float
    preparation_reason: str

    def __post_init__(self) -> None:
        coordinates = (*self.source_coordinates, *self.prepared_coordinates)
        actual = math.dist(self.source_coordinates, self.prepared_coordinates)
        if (not self.chain.strip() or not self.auth_residue_number.strip()
                or not self.residue_name.strip() or not self.atom_name.strip()
                or len(self.source_coordinates) != 3 or len(self.prepared_coordinates) != 3
                or any(not math.isfinite(item) for item in coordinates)
                or not math.isfinite(self.displacement) or not 0 < self.displacement <= 4
                or not math.isclose(self.displacement, actual, rel_tol=0, abs_tol=1e-9)
                or self.preparation_reason != "pdb2pqr_normal_sidechain_preparation"):
            raise ValueError("receptor moved heavy atom provenance is invalid")
