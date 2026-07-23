"""Deterministic, exact-identity ligand conformers for local docking tools."""

import math
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol

from agent.molecular.molecular_binding import MolecularInputBinding


@dataclass(frozen=True, slots=True)
class ConformerSettings:
    method: str
    seed: int
    max_iterations: int
    threads: int = 1

    def __post_init__(self) -> None:
        if not self.method.strip():
            raise ValueError("conformer method must be explicit")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("conformer seed must be an integer")
        if (isinstance(self.max_iterations, bool)
                or not 1 <= self.max_iterations <= 5000):
            raise ValueError("conformer optimization limit is invalid")
        if isinstance(self.threads, bool) or self.threads != 1:
            raise ValueError("deterministic conformer generation requires one thread")

    @property
    def command_argv(self) -> tuple[str, ...]:
        return (self.method, f"seed={self.seed}",
                f"max_iterations={self.max_iterations}", f"threads={self.threads}")


@dataclass(frozen=True, slots=True)
class LigandConformer:
    canonical_isomeric_smiles: str
    inchikey: str
    sdf: bytes
    heavy_atom_count: int

    def __post_init__(self) -> None:
        if (not self.canonical_isomeric_smiles.strip() or not self.inchikey.strip()
                or not self.sdf or self.heavy_atom_count <= 0):
            raise ValueError("ligand conformer is incomplete")


class ConformerBuilder(Protocol):
    version: str
    settings: ConformerSettings

    def build(self, binding: MolecularInputBinding) -> LigandConformer: ...
    def identify_smiles(self, smiles: str) -> tuple[str, str]: ...


class RDKitConformerBuilder:
    """Lazy RDKit boundary with a fixed ETKDG seed and bounded optimization."""

    def __init__(self, seed: int = 20260719, max_iterations: int = 500) -> None:
        self.settings = ConformerSettings("rdkit-etkdg-v3", seed, max_iterations)
        self.version = ""

    def build(self, binding: MolecularInputBinding) -> LigandConformer:
        if not binding.selection_confirmed:
            raise ValueError("docking conformer requires a confirmed molecular selection")
        chem, all_chem, version = _rdkit()
        self.version = version
        molecule = chem.MolFromSmiles(binding.canonical_isomeric_smiles, sanitize=True)
        if molecule is None or len(chem.GetMolFrags(molecule)) != 1:
            raise ValueError("dynamic Vina preparation supports one connected molecule")
        canonical = chem.MolToSmiles(molecule, isomericSmiles=True, canonical=True)
        inchikey = chem.MolToInchiKey(molecule)
        if (canonical, inchikey) != (binding.canonical_isomeric_smiles, binding.inchikey):
            raise ValueError("RDKit ligand identity or stereochemistry drifted")
        hydrated = chem.AddHs(molecule)
        params = all_chem.ETKDGv3()
        params.randomSeed = self.settings.seed
        params.useRandomCoords, params.numThreads = False, self.settings.threads
        if all_chem.EmbedMolecule(hydrated, params) != 0:
            raise ValueError("RDKit conformer embedding failed")
        status = _optimize(all_chem, hydrated, self.settings.max_iterations)
        if status != 0:
            raise ValueError("RDKit conformer force-field optimization failed")
        coordinates = hydrated.GetConformer().GetPositions()
        if any(not math.isfinite(float(value)) for row in coordinates for value in row):
            raise ValueError("RDKit conformer contains non-finite coordinates")
        hydrated.SetProp("_Name", binding.inchikey)
        sdf = (chem.MolToMolBlock(hydrated) + "\n>  <FROGENT_INCHIKEY>\n"
               + binding.inchikey + "\n\n$$$$\n").encode()
        return LigandConformer(canonical, inchikey, sdf, molecule.GetNumHeavyAtoms())

    def identify_smiles(self, smiles: str) -> tuple[str, str]:
        chem, _, version = _rdkit()
        self.version = version
        molecule = chem.MolFromSmiles(smiles, sanitize=True)
        if molecule is None:
            raise ValueError("Meeko PDBQT SMILES is invalid")
        return (chem.MolToSmiles(molecule, isomericSmiles=True, canonical=True),
                chem.MolToInchiKey(molecule))


def _rdkit():
    try:
        chem = import_module("rdkit.Chem")
        all_chem = import_module("rdkit.Chem.AllChem")
        rd_base = import_module("rdkit.rdBase")
    except ModuleNotFoundError as exc:
        raise RuntimeError("RDKit is unavailable for dynamic ligand preparation") from exc
    return chem, all_chem, rd_base.rdkitVersion


def _optimize(all_chem, molecule, iterations):
    if all_chem.MMFFHasAllMoleculeParams(molecule):
        return all_chem.MMFFOptimizeMolecule(molecule, maxIters=iterations)
    if all_chem.UFFHasAllMoleculeParams(molecule):
        return all_chem.UFFOptimizeMolecule(molecule, maxIters=iterations)
    raise ValueError("RDKit has no supported force field for the selected molecule")
