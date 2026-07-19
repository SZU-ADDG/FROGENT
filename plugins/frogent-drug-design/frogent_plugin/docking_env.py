"""Explicit project-contained docking tool configuration from environment."""

import os
from pathlib import Path

from .docking_microstates import DimorphiteConfig
from .docking_state_types import LigandStateSettings, ReceptorStateSettings
from .dynamic_plip import DynamicPLIPConfig
from .dynamic_receptor import ReceptorComponentPolicy
from .dynamic_vina import DynamicVinaConfig
from .receptor_states import PDB2PQRConfig


def dynamic_vina_from_env(root):
    names = ("FROGENT_VINA_EXECUTABLE", "FROGENT_MEEKO_LIGAND_EXECUTABLE",
             "FROGENT_MEEKO_RECEPTOR_EXECUTABLE")
    values = tuple(os.getenv(name, "").strip() for name in names)
    if not any(values): return None
    if not all(values):
        raise ValueError("dynamic docking requires all Vina and Meeko executable paths")
    paths = tuple(_path(root, value) for value in values)
    return DynamicVinaConfig(paths[0], paths[1], paths[2],
        root / ".runtime/app-v4/docking-runs", os.getenv("FROGENT_VINA_VERSION", "1.2.7"),
        os.getenv("FROGENT_MEEKO_VERSION", "0.7.1"), component_policy=_components())


def dynamic_plip_from_env(root):
    value = os.getenv("FROGENT_PLIP_EXECUTABLE", "").strip()
    if not value: return None
    return DynamicPLIPConfig(_path(root, value), root / ".runtime/app-v4/plip-runs",
        os.getenv("FROGENT_PLIP_VERSION", "3.0.0"), component_policy=_components())


def ligand_states_from_env(root):
    names = ("FROGENT_DIMORPHITE_EXECUTABLE", "FROGENT_DIMORPHITE_VERSION",
        "FROGENT_LIGAND_PH_MIN", "FROGENT_LIGAND_PH_MAX",
        "FROGENT_LIGAND_PH_PRECISION", "FROGENT_MAX_PROTOMERS",
        "FROGENT_MAX_TAUTOMERS")
    values = _explicit_group(names, "ligand state")
    if values is None:
        return None
    settings = LigandStateSettings(float(values[2]), float(values[3]), float(values[4]),
                                   int(values[5]), int(values[6]))
    return DimorphiteConfig(_path(root, values[0]),
                            root / ".runtime/app-v4/ligand-states", values[1], settings)


def receptor_states_from_env(root):
    names = ("FROGENT_PDB2PQR_EXECUTABLE", "FROGENT_PROPKA_EXECUTABLE",
        "FROGENT_PDB2PQR_VERSION", "FROGENT_PROPKA_VERSION",
        "FROGENT_RECEPTOR_PH", "FROGENT_PDB2PQR_FORCE_FIELD")
    values = _explicit_group(names, "receptor state")
    if values is None:
        return None
    settings = ReceptorStateSettings(float(values[4]), values[5])
    return PDB2PQRConfig(_path(root, values[0]), _path(root, values[1]),
        root / ".runtime/app-v4/receptor-states", values[2], values[3], settings,
        _components())


def _explicit_group(names, label):
    values = tuple(os.getenv(name, "").strip() for name in names)
    if not any(values):
        return None
    missing = tuple(name for name, value in zip(names, values) if not value)
    if missing:
        raise ValueError(f"{label} configuration requires explicit {', '.join(missing)}")
    return values


def _components():
    values = tuple(item.strip() for item in os.getenv(
        "FROGENT_DOCKING_REMOVABLE_COMPONENTS", "").split(",") if item.strip())
    return ReceptorComponentPolicy(removable_components=values)


def _path(root, value):
    path = Path(value)
    return path if path.is_absolute() else root / path
