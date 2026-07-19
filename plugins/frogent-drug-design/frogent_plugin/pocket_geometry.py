"""Verified pocket geometry derived from an exact structure artifact."""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PocketGeometry:
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    units: str
    method: str
    margin: float

    def __post_init__(self) -> None:
        values = (*self.center, *self.size, self.margin)
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) for value in values):
            raise ValueError("pocket geometry values must be finite numbers")
        if any(value <= 0 for value in self.size) or self.margin <= 0:
            raise ValueError("pocket size and margin must be positive")
        if self.units != "angstrom" or not self.method.strip():
            raise ValueError("pocket geometry units or method are invalid")
