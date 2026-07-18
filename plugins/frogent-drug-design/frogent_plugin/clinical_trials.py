"""Bounded ClinicalTrials.gov v2 evidence for publication readers."""

import json
import re
from typing import Mapping

from .biomedical_providers import HttpTransport, UrllibTransport
from .clinical_trial_outcomes import outcome_lines
from .contracts import ExecutionContext
from .evidence import LiteratureRecord

_NCT = re.compile(r"NCT[0-9]{8}\Z")
_LINK_TYPES = {"RESULT", "DERIVED"}
_SECONDARY_LIMIT = 10


class ClinicalTrialsResolver:
    """Resolve exact record identifiers or verified PMID-to-trial links."""

    BASE = "https://clinicaltrials.gov/api/v2"
    SCAN_LIMIT = 25

    def __init__(self, transport: HttpTransport | None = None, max_studies: int = 3) -> None:
        if (isinstance(max_studies, bool) or not isinstance(max_studies, int)
                or not 0 < max_studies <= self.SCAN_LIMIT):
            raise ValueError("ClinicalTrials.gov study bound must be 1..25")
        self.transport = transport or UrllibTransport()
        self.max_studies = max_studies
        self._gaps: dict[str, str] = {}

    def resolve(self, record: LiteratureRecord, context: ExecutionContext) -> str:
        self._gaps.pop(record.id, None)
        try:
            direct = _direct_nct_ids(record.identifiers)
            if len(direct) > self.max_studies:
                raise ValueError("direct NCT identifiers exceed configured study bound")
            if direct:
                return "\n".join(_render(study, "pubmed_accession")
                                 for study in self._direct(direct))
            return "\n".join(_render(study, "ctg_reference", pmid, reference_type)
                             for study, pmid, reference_type in self._by_pmid(record))
        except Exception as exc:
            self._gaps[record.id] = f"ClinicalTrials.gov evidence failed: {type(exc).__name__}: {exc}"
            return ""

    def coverage_gap(self, record_id: str) -> str:
        return self._gaps.pop(record_id, "")

    def _direct(self, nct_ids: tuple[str, ...]) -> tuple[Mapping[str, object], ...]:
        result = []
        for nct_id in nct_ids:
            payload = _json_object(self.transport.get(
                f"{self.BASE}/studies/{nct_id}", {"format": "json"}))
            study_id = _study_id(payload)
            if study_id != nct_id:
                raise ValueError(f"direct study identity mismatch: expected {nct_id}, got {study_id}")
            result.append(payload)
        return tuple(result)

    def _by_pmid(self, record: LiteratureRecord) -> tuple[tuple[Mapping[str, object], str, str], ...]:
        pmid = _identifier(record.identifiers, "pmid")
        if not pmid:
            return ()
        if not pmid.isdigit():
            raise ValueError("record PMID is malformed")
        params = {"query.term": f"AREA[ReferencePMID]{pmid}",
                  "pageSize": str(self.SCAN_LIMIT), "countTotal": "true", "format": "json"}
        payload = _json_object(self.transport.get(f"{self.BASE}/studies", params))
        raw = payload.get("studies")
        if raw is None and payload.get("totalCount") == 0:
            return ()
        if not isinstance(raw, list):
            raise ValueError("ClinicalTrials.gov search studies must be a list")
        linked = [(item, pmid, link_type) for item in raw
                  if (link_type := _publication_link(item, pmid))]
        return _deduplicate(linked)[:self.max_studies]

def _direct_nct_ids(identifiers: Mapping[str, str]) -> tuple[str, ...]:
    result = []
    for key, raw in identifiers.items():
        value = str(raw).strip().upper()
        names_nct = key.casefold().startswith("nct") or "clinicaltrial" in key.casefold()
        if not names_nct:
            continue
        if names_nct and not _NCT.fullmatch(value):
            raise ValueError(f"malformed NCT identifier in {key}")
        result.append(value)
    return tuple(dict.fromkeys(result))


def _publication_link(study: object, pmid: str) -> str:
    protocol = _protocol(study)
    module = protocol.get("referencesModule")
    if module is None:
        return ""
    if not isinstance(module, Mapping):
        raise ValueError("referencesModule must be an object")
    retractions = module.get("retractions", [])
    if not isinstance(retractions, list) or any(not isinstance(item, Mapping) for item in retractions):
        raise ValueError("retractions must be a list of objects")
    if any(str(item.get("pmid") or "").strip() == pmid for item in retractions):
        raise ValueError("linked publication appears in registry retractions")
    references = module.get("references")
    if references is None:
        return ""
    if not isinstance(references, list):
        raise ValueError("references must be a list")
    for item in references:
        if not isinstance(item, Mapping):
            raise ValueError("reference must be an object")
        link_type = str(item.get("type") or "").upper()
        if str(item.get("pmid") or "").strip() == pmid and link_type in _LINK_TYPES:
            return link_type
    return ""


def _deduplicate(studies: list[tuple[object, str, str]]) -> tuple[tuple[Mapping[str, object], str, str], ...]:
    result, identities = [], {}
    for study, pmid, link_type in studies:
        nct_id = _study_id(study)
        canonical = json.dumps(study, sort_keys=True, separators=(",", ":"))
        if nct_id in identities and identities[nct_id] != canonical:
            raise ValueError(f"conflicting duplicate trial identity: {nct_id}")
        if nct_id not in identities:
            identities[nct_id] = canonical
            result.append((study, pmid, link_type))
    return tuple(result)


def _render(study: Mapping[str, object], link_method: str, pmid: str = "",
            reference_type: str = "") -> str:
    protocol, nct_id = _protocol(study), _study_id(study)
    identification = _module(protocol, "identificationModule", required=True)
    status = _module(protocol, "statusModule")
    design = _module(protocol, "designModule")
    arms = _module(protocol, "armsInterventionsModule")
    outcomes = _module(protocol, "outcomesModule")
    sponsor = _module(protocol, "sponsorCollaboratorsModule")
    provenance = f"link_method={link_method}"
    if pmid:
        provenance += f"; inputPMID={pmid}; reference_type={reference_type}"
    lines = [f"[REGISTRY SOURCE {nct_id}] https://clinicaltrials.gov/study/{nct_id}; "
             f"{provenance}; snapshot=current_mutable; historical_as_of_reconstruction=not_established"]
    title = identification.get("officialTitle") or identification.get("briefTitle")
    if title:
        lines.append(f"[REGISTRY {nct_id} TITLE] {_clean(title)}")
    lines.append(f"[REGISTRY {nct_id} STATUS] overallStatus={_field(status, 'overallStatus')}; "
                 f"startDate={_date_field(status, 'startDateStruct')}; "
                 f"completionDate={_date_field(status, 'completionDateStruct')}; "
                 f"lastUpdatePostDate={_date_field(status, 'lastUpdatePostDateStruct')}; "
                 f"lastUpdatePostType={_field(_mapping(status.get('lastUpdatePostDateStruct'), 'lastUpdatePostDateStruct'), 'type')}")
    info = _mapping(design.get("designInfo"), "designInfo")
    masking = _mapping(info.get("maskingInfo"), "maskingInfo")
    lines.append(f"[REGISTRY {nct_id} DESIGN] studyType={_field(design, 'studyType')}; "
                 f"phase={_joined(design.get('phases'))}; allocation={_field(info, 'allocation')}; "
                 f"masking={_field(masking, 'masking')}")
    enrollment = _mapping(design.get("enrollmentInfo"), "enrollmentInfo")
    lines.append(f"[REGISTRY {nct_id} ENROLLMENT] count={_field(enrollment, 'count')}; "
                 f"type={_field(enrollment, 'type')}")
    lead = _mapping(sponsor.get("leadSponsor"), "leadSponsor")
    responsible = _mapping(sponsor.get("responsibleParty"), "responsibleParty")
    lines.append(f"[REGISTRY {nct_id} SPONSOR] lead={_field(lead, 'name')}; "
                 f"class={_field(lead, 'class')}; responsible={_field(responsible, 'investigatorFullName')}")
    for index, arm in enumerate(_objects(arms.get("armGroups"), "armGroups"), 1):
        interventions = _joined(arm.get("interventionNames"))
        lines.append(f"[REGISTRY {nct_id} ARM {index}] label={_field(arm, 'label')}; "
                     f"type={_field(arm, 'type')}; interventions={interventions}")
    lines.extend(outcome_lines(nct_id, outcomes.get("primaryOutcomes"),
                              "PLANNED PRIMARY OUTCOME", include_description=True))
    secondary = outcome_lines(nct_id, outcomes.get("secondaryOutcomes"),
                              "PLANNED SECONDARY OUTCOME")
    lines.extend(secondary[:_SECONDARY_LIMIT])
    if len(secondary) > _SECONDARY_LIMIT:
        lines.append(f"[REGISTRY {nct_id} SECONDARY OUTCOMES OMITTED] count={len(secondary) - _SECONDARY_LIMIT}")
    posted = _date_field(status, "resultsFirstPostDateStruct")
    observed = ("posted; resultsSection values not extracted" if study["hasResults"] else
                "none; registry supplies no observed efficacy/safety result")
    lines.append(f"[REGISTRY {nct_id} RESULTS] hasResults={str(study['hasResults']).lower()}; "
                 f"resultsFirstPosted={posted}; observedResults={observed}")
    return "\n".join(lines)
def _study_id(study: object) -> str:
    protocol = _protocol(study)
    value = str(_module(protocol, "identificationModule", required=True).get("nctId") or "").upper()
    if not _NCT.fullmatch(value):
        raise ValueError("study has malformed NCT identity")
    if not isinstance(study.get("hasResults"), bool):
        raise ValueError("study hasResults must be boolean")
    return value


def _protocol(study: object) -> Mapping[str, object]:
    if not isinstance(study, Mapping):
        raise ValueError("study must be an object")
    protocol = study.get("protocolSection")
    if not isinstance(protocol, Mapping):
        raise ValueError("study protocolSection must be an object")
    return protocol


def _module(protocol, key, required=False) -> Mapping[str, object]:
    value = protocol.get(key)
    if value is None and not required:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value


def _objects(value, name) -> tuple[Mapping[str, object], ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{name} must be a list of objects")
    return tuple(value)


def _mapping(value, name) -> Mapping[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _json_object(raw: bytes) -> Mapping[str, object]:
    value = json.loads(raw)
    if not isinstance(value, Mapping):
        raise ValueError("ClinicalTrials.gov response must be an object")
    return value


def _identifier(values, wanted) -> str:
    return next((str(value).strip() for key, value in values.items()
                 if key.casefold() == wanted), "")


def _field(values, key) -> str:
    value = values.get(key)
    return _clean(value) if value not in (None, "") else "not_reported"


def _date_field(values, key) -> str:
    return _field(_mapping(values.get(key), key), "date")


def _joined(value) -> str:
    if value is None:
        return "not_reported"
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("registry list field must contain strings")
    return " | ".join(_clean(item) for item in value) or "not_reported"


def _clean(value) -> str:
    return " ".join(str(value).split()).replace(";", ",")
