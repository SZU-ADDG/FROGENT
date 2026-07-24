"""Official PubChem identity verification for exact molecular tool inputs."""

import json
import urllib.parse
from dataclasses import dataclass
from typing import Mapping

from agent.research.biomedical_providers import HttpTransport, UrllibTransport
from agent.molecular.molecular_binding import MolecularInputBinding
from agent.molecular.molecular_identity import (
    MolecularIdentity, MolecularSearchTerm, MoleculeNormalizer, RDKitMoleculeNormalizer,
)
from agent.molecular.molecular_routing import MolecularIntakeResult, prepare_molecular_request


PROPERTIES = ("Title,CanonicalSMILES,IsomericSMILES,InChI,InChIKey,"
              "MolecularFormula,Charge")


@dataclass(frozen=True, slots=True)
class PubChemExternalIdentity:
    cid: int
    verified_name: str
    canonical_smiles: str
    isomeric_smiles: str
    inchi: str
    inchikey: str
    formula: str
    charge: int
    artifact_url: str
    resolution_method: str
    requested_value: str
    scope: str

    def __post_init__(self) -> None:
        texts = (self.verified_name, self.canonical_smiles, self.isomeric_smiles, self.inchi,
                 self.inchikey, self.formula, self.artifact_url, self.resolution_method,
                 self.requested_value, self.scope)
        if isinstance(self.cid, bool) or not isinstance(self.cid, int) or self.cid <= 0:
            raise ValueError("PubChem CID must be a positive integer")
        if any(not value.strip() for value in texts):
            raise ValueError("PubChem identity fields must be non-empty")
        if isinstance(self.charge, bool) or not isinstance(self.charge, int):
            raise ValueError("PubChem charge must be an integer")


@dataclass(frozen=True, slots=True)
class PubChemResolution:
    external: PubChemExternalIdentity | None
    normalized_identity: MolecularIdentity | None
    search_terms: tuple[MolecularSearchTerm, ...]
    coverage_gaps: tuple[str, ...]

    def __post_init__(self) -> None:
        if (self.external is None) != (self.normalized_identity is None):
            raise ValueError("PubChem external and normalized identities must resolve together")
        if self.external is None and (self.search_terms or not self.coverage_gaps):
            raise ValueError("failed PubChem resolution requires only coverage gaps")


@dataclass(frozen=True, slots=True)
class VerifiedMolecularRequest:
    intake: MolecularIntakeResult
    candidate: PubChemResolution
    baseline: PubChemResolution | None
    search_terms: tuple[MolecularSearchTerm, ...]
    baseline_search_terms: tuple[MolecularSearchTerm, ...]
    coverage_gaps: tuple[str, ...]


class PubChemIdentityResolver:
    BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"

    def __init__(self, transport: HttpTransport | None = None,
                 normalizer: MoleculeNormalizer | None = None) -> None:
        self.transport = transport or UrllibTransport()
        self.normalizer = normalizer or RDKitMoleculeNormalizer()

    def resolve_binding(self, binding: MolecularInputBinding) -> PubChemResolution:
        result = self._resolve("inchikey", binding.inchikey, "exact_inchikey", binding.scope)
        if result.external and result.external.inchikey != binding.inchikey:
            return _failure("PubChem InChIKey does not match selected molecular input")
        return result

    def resolve_name(self, name: str) -> PubChemResolution:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("chemical name must be non-empty text")
        return self._resolve("name", name.strip(), "verified_name", "resolved_name")

    def _resolve(self, namespace: str, value: str, method: str, scope: str) -> PubChemResolution:
        encoded = urllib.parse.quote(value, safe="")
        url = f"{self.BASE}/{namespace}/{encoded}/property/{PROPERTIES}/JSON"
        try:
            payload = json.loads(self.transport.get(url, {}))
            external = _external_identity(payload, url, method, value, scope)
            normalized = self.normalizer.normalize(external.isomeric_smiles)
            if normalized.inchikey != external.inchikey:
                raise ValueError("PubChem structure and InChIKey disagree after normalization")
            return PubChemResolution(external, normalized, _external_terms(external), ())
        except Exception as error:
            return _failure(f"PubChem {method} resolution failed: {type(error).__name__}: {error}")


def verify_molecular_request(smiles: str, intent: str,
                             resolver: PubChemIdentityResolver, *,
                             normalizer: MoleculeNormalizer | None = None,
                             claimed_name: str = "", baseline_claimed_name: str = "",
                             **kwargs) -> VerifiedMolecularRequest:
    intake = prepare_molecular_request(smiles, intent, normalizer, **kwargs)
    candidate = resolver.resolve_binding(intake.selected_input)
    baseline = (resolver.resolve_binding(intake.selected_baseline_input)
                if intake.selected_baseline_input else None)
    gaps = list(candidate.coverage_gaps)
    if baseline:
        gaps.extend(baseline.coverage_gaps)
    gaps.extend(_name_gap(claimed_name, candidate, "candidate"))
    gaps.extend(_name_gap(baseline_claimed_name, baseline, "baseline"))
    return VerifiedMolecularRequest(intake, candidate, baseline,
        _merge_terms(intake.search_terms, candidate.search_terms),
        _merge_terms(intake.baseline_search_terms, baseline.search_terms if baseline else ()),
        tuple(gaps))


def prepare_molecular_request_from_name(name: str, intent: str,
                                        resolver: PubChemIdentityResolver, *,
                                        normalizer: MoleculeNormalizer | None = None,
                                        **kwargs) -> VerifiedMolecularRequest | PubChemResolution:
    resolution = resolver.resolve_name(name)
    if resolution.external is None or resolution.normalized_identity is None:
        return resolution
    adapter = normalizer or resolver.normalizer
    intake = prepare_molecular_request(resolution.normalized_identity.canonical_isomeric_smiles,
                                       intent, adapter, **kwargs)
    terms = _merge_terms(intake.search_terms, resolution.search_terms)
    return VerifiedMolecularRequest(intake, resolution, None, terms, (), ())


def _external_identity(payload, url, method, requested, scope):
    if not isinstance(payload, Mapping):
        raise ValueError("PubChem payload must be an object")
    table = payload.get("PropertyTable")
    values = table.get("Properties") if isinstance(table, Mapping) else None
    if not isinstance(values, list) or not values:
        raise ValueError("PubChem resolution must contain property records")
    item = (_exact_record(values) if method == "exact_inchikey"
            else _single_record(values))
    canonical = _text(item, "ConnectivitySMILES", "CanonicalSMILES")
    isomeric = _text(item, "SMILES", "IsomericSMILES")
    return PubChemExternalIdentity(_integer(item, "CID"), _text(item, "Title"), canonical,
        isomeric, _text(item, "InChI"), _text(item, "InChIKey"),
        _text(item, "MolecularFormula"), _integer(item, "Charge", signed=True),
        url, method, requested, scope)


def _exact_record(values):
    parsed = tuple(_duplicate_record(item) for item in values)
    fingerprints = {item[2] for item in parsed}
    complete = tuple(item for item in parsed if item[1])
    if len(fingerprints) != 1:
        raise ValueError("PubChem exact records contain conflicting structural identities")
    if len(complete) != 1:
        raise ValueError("PubChem exact records require one complete unambiguous identity")
    return complete[0][0]


def _single_record(values):
    if len(values) != 1 or not isinstance(values[0], Mapping):
        raise ValueError("PubChem name resolution must contain exactly one property record")
    _text(values[0], "Title")
    return values[0]


def _duplicate_record(item):
    if not isinstance(item, Mapping):
        raise ValueError("PubChem property record must be an object")
    cid = _integer(item, "CID")
    title = item.get("Title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ValueError("PubChem Title must be non-empty text when present")
    fingerprint = (_text(item, "ConnectivitySMILES", "CanonicalSMILES"),
        _text(item, "SMILES", "IsomericSMILES"), _text(item, "InChI"),
        _text(item, "InChIKey"), _text(item, "MolecularFormula"),
        _integer(item, "Charge", signed=True))
    return item, str(title or ""), (cid > 0 and fingerprint)


def _external_terms(item):
    provenance = "pubchem_pug_rest"
    return (MolecularSearchTerm("pubchem_cid", str(item.cid), item.scope, True,
                                provenance, item.artifact_url),
            MolecularSearchTerm("verified_name", item.verified_name, item.scope, False,
                                provenance, item.artifact_url))


def _name_gap(claimed, resolution, role):
    if not claimed or resolution is None or resolution.external is None:
        return ()
    if claimed.strip().casefold() == resolution.external.verified_name.casefold():
        return ()
    return (f"{role} supplied name rejected: verified PubChem name is "
            f"{resolution.external.verified_name}",)


def _merge_terms(local, external):
    return tuple(dict.fromkeys((*local, *external)))


def _failure(message):
    return PubChemResolution(None, None, (), (message,))


def _text(item, *keys):
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(f"PubChem field is missing: {'/'.join(keys)}")


def _integer(item, key, signed=False):
    value = item.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not signed and value <= 0:
        raise ValueError(f"PubChem integer field is invalid: {key}")
    return value
