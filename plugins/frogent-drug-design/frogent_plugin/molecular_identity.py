"""Typed small-molecule identity normalization and bounded retrieval terms."""

from dataclasses import dataclass
from importlib import import_module
from math import isfinite
from typing import Protocol


FRAGMENT_STATUSES = frozenset({"single", "salt_or_counterion", "multiple_organic_fragments",
                               "mixture"})
STEREO_STATUSES = frozenset({"none", "assigned", "unassigned", "mixed"})


@dataclass(frozen=True, slots=True)
class DerivedMoleculeCandidate:
    canonical_isomeric_smiles: str
    canonical_connectivity_smiles: str
    inchi: str
    inchikey: str
    formula: str
    removed_fragments: tuple[str, ...]

    def __post_init__(self) -> None:
        values = (self.canonical_isomeric_smiles, self.canonical_connectivity_smiles,
                  self.inchi, self.inchikey, self.formula)
        if any(not value.strip() for value in values) or not self.removed_fragments:
            raise ValueError("derived parent identity is incomplete")


@dataclass(frozen=True, slots=True)
class MolecularIdentity:
    original_smiles: str
    canonical_isomeric_smiles: str
    canonical_connectivity_smiles: str
    inchi: str
    inchikey: str
    formula: str
    exact_mass: float
    formal_charge: int
    heavy_atom_count: int
    fragment_count: int
    organic_fragment_count: int
    fragment_status: str
    has_charged_fragments: bool
    assigned_stereocenters: int
    unassigned_stereocenters: int
    stereochemistry_status: str
    parent_candidate: DerivedMoleculeCandidate | None = None

    def __post_init__(self) -> None:
        texts = (self.original_smiles, self.canonical_isomeric_smiles,
                 self.canonical_connectivity_smiles, self.inchi, self.inchikey, self.formula)
        counts = (self.heavy_atom_count, self.fragment_count, self.organic_fragment_count,
                  self.assigned_stereocenters, self.unassigned_stereocenters)
        if any(not value.strip() for value in texts):
            raise ValueError("molecular identity text fields must be non-empty")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts):
            raise ValueError("molecular identity counts must be non-negative integers")
        if self.heavy_atom_count == 0 or self.fragment_count == 0 \
                or self.organic_fragment_count > self.fragment_count:
            raise ValueError("molecular identity must contain atoms and fragments")
        if isinstance(self.exact_mass, bool) or not isinstance(self.exact_mass, (int, float)) \
                or not isfinite(self.exact_mass) or self.exact_mass <= 0:
            raise ValueError("molecular exact mass must be positive and finite")
        if isinstance(self.formal_charge, bool) or not isinstance(self.formal_charge, int):
            raise ValueError("molecular formal charge must be an integer")
        if self.fragment_status not in FRAGMENT_STATUSES:
            raise ValueError("molecular fragment status is invalid")
        if self.stereochemistry_status not in STEREO_STATUSES:
            raise ValueError("molecular stereochemistry status is invalid")
        if not isinstance(self.has_charged_fragments, bool):
            raise ValueError("charged-fragment flag must be boolean")
        if (self.fragment_status == "single") != (self.fragment_count == 1):
            raise ValueError("molecular fragment status conflicts with fragment count")
        expected_stereo = _stereo_status(self.assigned_stereocenters,
                                         self.unassigned_stereocenters)
        if self.stereochemistry_status != expected_stereo:
            raise ValueError("molecular stereochemistry status conflicts with center counts")
        if self.parent_candidate and self.fragment_count == 1:
            raise ValueError("single-fragment identity cannot have a derived parent")


@dataclass(frozen=True, slots=True)
class MolecularSearchTerm:
    kind: str
    value: str
    scope: str
    exact: bool
    provenance: str = "local_rdkit"
    artifact_url: str = ""


class MoleculeNormalizer(Protocol):
    def normalize(self, smiles: str) -> MolecularIdentity: ...


class RDKitMoleculeNormalizer:
    """Load RDKit lazily so the core runtime remains injectable and stdlib-importable."""

    def normalize(self, smiles: str) -> MolecularIdentity:
        if not isinstance(smiles, str) or not smiles.strip():
            raise ValueError("SMILES must be non-empty text")
        chem = import_module("rdkit.Chem")
        descriptors = import_module("rdkit.Chem.Descriptors")
        rdmd = import_module("rdkit.Chem.rdMolDescriptors")
        molecule = chem.MolFromSmiles(smiles, sanitize=True)
        if molecule is None:
            raise ValueError("invalid SMILES: RDKit parse or sanitization failed")
        fragments = tuple(chem.GetMolFrags(molecule, asMols=True, sanitizeFrags=True))
        organic = tuple(item for item in fragments if _organic(item))
        assigned, unassigned = _stereocenters(chem, molecule)
        parent = _parent_candidate(chem, rdmd, fragments, organic)
        return MolecularIdentity(
            smiles, chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True),
            chem.MolToSmiles(molecule, canonical=True, isomericSmiles=False),
            chem.MolToInchi(molecule), chem.MolToInchiKey(molecule), rdmd.CalcMolFormula(molecule),
            float(descriptors.ExactMolWt(molecule)), int(chem.GetFormalCharge(molecule)),
            int(molecule.GetNumHeavyAtoms()), len(fragments), len(organic),
            _fragment_status(fragments, organic),
            any(chem.GetFormalCharge(item) != 0 for item in fragments), assigned, unassigned,
            _stereo_status(assigned, unassigned), parent)


def molecular_search_terms(identity: MolecularIdentity, *, include_formula: bool = False,
                           max_terms: int = 10) -> tuple[MolecularSearchTerm, ...]:
    if isinstance(max_terms, bool) or not isinstance(max_terms, int) or max_terms <= 0:
        raise ValueError("molecular search term limit must be positive")
    values = _identity_terms(identity, "full", False)
    if identity.parent_candidate:
        values += _parent_terms(identity.parent_candidate, False)
    if include_formula:
        values.append(MolecularSearchTerm("formula", identity.formula, "full", False))
        if identity.parent_candidate:
            values.append(MolecularSearchTerm("formula", identity.parent_candidate.formula,
                                              "parent_candidate", False))
    unique = []
    for item in values:
        key = (item.kind, item.value, item.scope)
        if key not in {(row.kind, row.value, row.scope) for row in unique}:
            unique.append(item)
    return tuple(unique[:max_terms])


def _identity_terms(item, scope, formula):
    values = [MolecularSearchTerm("canonical_smiles", item.canonical_isomeric_smiles, scope, True)]
    if item.canonical_connectivity_smiles != item.canonical_isomeric_smiles:
        values.append(MolecularSearchTerm("connectivity_smiles", item.canonical_connectivity_smiles,
                                         scope, True))
    values.extend((MolecularSearchTerm("inchikey", item.inchikey, scope, True),
                   MolecularSearchTerm("inchi", item.inchi, scope, True)))
    if formula:
        values.append(MolecularSearchTerm("formula", item.formula, scope, False))
    return values


def _parent_terms(item, formula):
    return _identity_terms(item, "parent_candidate", formula)


def _organic(molecule) -> bool:
    return any(atom.GetAtomicNum() == 6 for atom in molecule.GetAtoms())


def _fragment_status(fragments, organic) -> str:
    if len(fragments) == 1:
        return "single"
    if len(organic) == 1:
        return "salt_or_counterion"
    return "multiple_organic_fragments" if len(organic) > 1 else "mixture"


def _stereocenters(chem, molecule) -> tuple[int, int]:
    centers = chem.FindMolChiralCenters(molecule, includeUnassigned=True, includeCIP=True)
    return sum(label != "?" for _, label in centers), sum(label == "?" for _, label in centers)


def _stereo_status(assigned, unassigned) -> str:
    if assigned and unassigned:
        return "mixed"
    if assigned:
        return "assigned"
    return "unassigned" if unassigned else "none"


def _parent_candidate(chem, rdmd, fragments, organic):
    if len(fragments) == 1 or not organic:
        return None
    ranked = sorted(organic, key=lambda item: (-item.GetNumHeavyAtoms(),
                    chem.MolToSmiles(item, canonical=True, isomericSmiles=True)))
    parent = ranked[0]
    removed = list(fragments)
    removed.remove(parent)
    removed_smiles = tuple(sorted(chem.MolToSmiles(item, canonical=True, isomericSmiles=True)
                                  for item in removed))
    return DerivedMoleculeCandidate(
        chem.MolToSmiles(parent, canonical=True, isomericSmiles=True),
        chem.MolToSmiles(parent, canonical=True, isomericSmiles=False),
        chem.MolToInchi(parent), chem.MolToInchiKey(parent), rdmd.CalcMolFormula(parent),
        removed_smiles)
