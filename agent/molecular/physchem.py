"""Deterministic molecular descriptors and fingerprint similarity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
from math import isfinite


@dataclass(frozen=True, slots=True)
class PhyschemRecord:
    input_smiles: str
    canonical_smiles: str
    molecular_weight: float
    exact_mass: float
    clogp: float
    tpsa: float
    hydrogen_bond_donors: int
    hydrogen_bond_acceptors: int
    rotatable_bonds: int
    fraction_csp3: float
    aromatic_rings: int
    aliphatic_rings: int
    qed: float
    lipinski_violations: tuple[str, ...]
    veber_pass: bool

    def __post_init__(self) -> None:
        if not self.input_smiles.strip() or not self.canonical_smiles.strip():
            raise ValueError("molecular descriptor identity is incomplete")
        numeric = (
            self.molecular_weight,
            self.exact_mass,
            self.clogp,
            self.tpsa,
            self.fraction_csp3,
            self.qed,
        )
        if any(isinstance(value, bool) or not isfinite(value) for value in numeric):
            raise ValueError("molecular descriptors must be finite numbers")

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SimilarityRecord:
    input_smiles: str
    canonical_smiles: str
    tanimoto: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.tanimoto <= 1.0:
            raise ValueError("Tanimoto similarity must be in [0, 1]")

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def describe_smiles(smiles: str) -> PhyschemRecord:
    molecule, chem = _molecule(smiles)
    descriptors = import_module("rdkit.Chem.Descriptors")
    crippen = import_module("rdkit.Chem.Crippen")
    rdmd = import_module("rdkit.Chem.rdMolDescriptors")
    qed_module = import_module("rdkit.Chem.QED")
    molecular_weight = float(descriptors.MolWt(molecule))
    clogp = float(crippen.MolLogP(molecule))
    tpsa = float(rdmd.CalcTPSA(molecule))
    donors = int(rdmd.CalcNumHBD(molecule))
    acceptors = int(rdmd.CalcNumHBA(molecule))
    rotatable = int(rdmd.CalcNumRotatableBonds(molecule))
    violations = tuple(
        label
        for condition, label in (
            (molecular_weight > 500.0, "molecular_weight>500"),
            (clogp > 5.0, "clogp>5"),
            (donors > 5, "hydrogen_bond_donors>5"),
            (acceptors > 10, "hydrogen_bond_acceptors>10"),
        )
        if condition
    )
    return PhyschemRecord(
        input_smiles=smiles,
        canonical_smiles=chem.MolToSmiles(
            molecule, canonical=True, isomericSmiles=True
        ),
        molecular_weight=molecular_weight,
        exact_mass=float(descriptors.ExactMolWt(molecule)),
        clogp=clogp,
        tpsa=tpsa,
        hydrogen_bond_donors=donors,
        hydrogen_bond_acceptors=acceptors,
        rotatable_bonds=rotatable,
        fraction_csp3=float(rdmd.CalcFractionCSP3(molecule)),
        aromatic_rings=int(rdmd.CalcNumAromaticRings(molecule)),
        aliphatic_rings=int(rdmd.CalcNumAliphaticRings(molecule)),
        qed=float(qed_module.qed(molecule)),
        lipinski_violations=violations,
        veber_pass=rotatable <= 10 and tpsa <= 140.0,
    )


def describe_many(smiles_list: tuple[str, ...]) -> tuple[PhyschemRecord, ...]:
    _bounded_smiles(smiles_list)
    return tuple(describe_smiles(smiles) for smiles in smiles_list)


def rank_similarity(
    query_smiles: str,
    candidate_smiles: tuple[str, ...],
    *,
    radius: int = 2,
    n_bits: int = 2048,
) -> tuple[SimilarityRecord, ...]:
    _bounded_smiles(candidate_smiles)
    if isinstance(radius, bool) or not isinstance(radius, int) or not 1 <= radius <= 4:
        raise ValueError("Morgan radius must be an integer in [1, 4]")
    if isinstance(n_bits, bool) or not isinstance(n_bits, int) or n_bits not in {1024, 2048, 4096}:
        raise ValueError("Morgan fingerprint size must be 1024, 2048 or 4096")
    query, chem = _molecule(query_smiles)
    generator_module = import_module("rdkit.Chem.rdFingerprintGenerator")
    data_structs = import_module("rdkit.DataStructs")
    generator = generator_module.GetMorganGenerator(radius=radius, fpSize=n_bits)
    query_fp = generator.GetFingerprint(query)
    records = []
    for smiles in candidate_smiles:
        molecule, _ = _molecule(smiles)
        similarity = float(
            data_structs.TanimotoSimilarity(
                query_fp, generator.GetFingerprint(molecule)
            )
        )
        records.append(
            SimilarityRecord(
                smiles,
                chem.MolToSmiles(
                    molecule, canonical=True, isomericSmiles=True
                ),
                similarity,
            )
        )
    return tuple(sorted(records, key=lambda item: (-item.tanimoto, item.canonical_smiles)))


def _molecule(smiles: str):
    if not isinstance(smiles, str) or not smiles.strip():
        raise ValueError("SMILES must be non-empty text")
    chem = import_module("rdkit.Chem")
    molecule = chem.MolFromSmiles(smiles, sanitize=True)
    if molecule is None:
        raise ValueError(f"invalid SMILES: {smiles}")
    return molecule, chem


def _bounded_smiles(values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple) or not 1 <= len(values) <= 256:
        raise ValueError("SMILES batch must contain 1 to 256 entries")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("SMILES batch entries must be non-empty text")
