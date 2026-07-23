"""Evidence-bounded ADMET prediction over exact molecular input bindings."""

import math
import numbers
from dataclasses import dataclass
from typing import Mapping, Protocol

from agent.molecular.molecular_binding import MolecularInputBinding, MolecularToolInput
from agent.molecular.molecular_routing import MolecularToolStep


ADMET_PROPERTY_ALLOWLIST = frozenset({
    "HIA_Hou", "Bioavailability_Ma", "Solubility_AqSolDB", "Lipophilicity_AstraZeneca",
    "HydrationFreeEnergy_FreeSolv", "Caco2_Wang", "PAMPA_NCATS", "Pgp_Broccatelli",
    "BBB_Martins", "PPBR_AZ", "VDss_Lombardo", "Half_Life_Obach",
    "Clearance_Hepatocyte_AZ", "Clearance_Microsome_AZ", "CYP1A2_Veith",
    "CYP2C19_Veith", "CYP2C9_Veith", "CYP2D6_Veith", "CYP3A4_Veith",
    "CYP2C9_Substrate_CarbonMangels", "CYP2D6_Substrate_CarbonMangels",
    "CYP3A4_Substrate_CarbonMangels", "hERG", "ClinTox", "AMES", "DILI",
    "Carcinogens_Lagunin", "LD50_Zhu", "Skin_Reaction", "NR-AR", "NR-AR-LBD",
    "NR-AhR", "NR-Aromatase", "NR-ER", "NR-ER-LBD", "NR-PPAR-gamma", "SR-ARE",
    "SR-ATAD5", "SR-HSE", "SR-MMP", "SR-p53",
})
DEFAULT_ADMET_PROPERTIES = (
    "HIA_Hou", "Bioavailability_Ma", "Solubility_AqSolDB", "Caco2_Wang",
    "BBB_Martins", "PPBR_AZ", "Clearance_Hepatocyte_AZ", "CYP3A4_Veith",
    "hERG", "AMES", "DILI",
)


@dataclass(frozen=True, slots=True)
class ADMETBatchPrediction:
    input_smiles: tuple[str, ...]
    rows: tuple[Mapping[str, object], ...]


class ADMETPredictor(Protocol):
    provider_id: str
    model_name: str
    model_version: str

    def predict(self, smiles: tuple[str, ...]) -> ADMETBatchPrediction: ...


@dataclass(frozen=True, slots=True)
class ADMETValue:
    property_id: str
    value: float


@dataclass(frozen=True, slots=True)
class ADMETArmEvidence:
    role: str
    binding: MolecularInputBinding
    values: tuple[ADMETValue, ...]


@dataclass(frozen=True, slots=True)
class ADMETDelta:
    property_id: str
    candidate_minus_baseline: float


@dataclass(frozen=True, slots=True)
class ADMETExecutionResult:
    status: str
    capability_id: str
    provider: str
    model: str
    model_version: str
    requested_properties: tuple[str, ...]
    role_order: tuple[str, ...]
    input_bindings: tuple[MolecularInputBinding, ...]
    arms: tuple[ADMETArmEvidence, ...] = ()
    deltas: tuple[ADMETDelta, ...] = ()
    experimental_evidence: bool = False
    warnings: tuple[str, ...] = ()
    coverage_gaps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"completed", "blocked", "failed"}:
            raise ValueError("ADMET execution status is invalid")
        if self.experimental_evidence is not False:
            raise ValueError("ADMET predictions cannot be experimental evidence")
        if len(self.input_bindings) > len(self.role_order):
            raise ValueError("ADMET input bindings exceed role order")
        if self.status == "completed" and len(self.input_bindings) != len(self.role_order):
            raise ValueError("completed ADMET inputs do not match role order")
        if self.status == "completed" and tuple(item.role for item in self.arms) != self.role_order:
            raise ValueError("ADMET result arms do not match role order")
        if self.status != "completed" and not self.coverage_gaps:
            raise ValueError("incomplete ADMET execution requires a coverage gap")


def execute_admet_step(step: MolecularToolStep, predictor: ADMETPredictor,
                       requested_properties=DEFAULT_ADMET_PROPERTIES) -> ADMETExecutionResult:
    properties, error = _properties(requested_properties)
    if error:
        return _failure(step, predictor, properties, "failed", error)
    if step.capability_id not in {"admet.predict", "admet.compare"}:
        return _failure(step, predictor, properties, "blocked", "step is not an ADMET capability")
    if step.status != "ready":
        gaps = step.status.replace("_", " ")
        return _failure(step, predictor, properties, "blocked", f"ADMET tool step is {gaps}")
    binding_error = _binding_error(step)
    if binding_error:
        return _failure(step, predictor, properties, "blocked", binding_error)
    try:
        bindings = _bindings(step.tool_input)
        inputs = tuple(item.canonical_isomeric_smiles for item in bindings)
        prediction = predictor.predict(inputs)
        arms = _arms(step.tool_input.role_order, bindings, inputs, prediction, properties)
        deltas = _deltas(arms, properties)
        return ADMETExecutionResult("completed", step.capability_id, predictor.provider_id,
            predictor.model_name, predictor.model_version, properties,
            step.tool_input.role_order, bindings, arms, deltas, False,
            ("ADMET-AI values are model predictions, separate from experimental evidence",
             "this adapter exposes no calibrated per-prediction uncertainty; interpretation is endpoint-specific",
             "model applicability domain and cross-endpoint score comparability are not established"), ())
    except Exception as exc:
        message = f"ADMET prediction failed: {type(exc).__name__}: {exc}"
        return _failure(step, predictor, properties, "failed", message)


def _properties(values):
    if not isinstance(values, (tuple, list)):
        return (), "requested ADMET properties must be a sequence"
    if any(not isinstance(value, str) or not value.strip() for value in values):
        return (), "requested ADMET properties must be non-empty strings"
    properties = tuple(values)
    if len(set(properties)) != len(properties) or not properties:
        return properties, "requested ADMET properties must be non-empty and unique"
    unknown = tuple(value for value in properties if value not in ADMET_PROPERTY_ALLOWLIST)
    return (properties, f"unknown ADMET properties: {', '.join(unknown)}") if unknown \
        else (properties, "")


def _binding_error(step):
    tool_input = step.tool_input
    bindings = _bindings(tool_input)
    if any(not item.selection_confirmed for item in bindings):
        return "ADMET execution requires confirmed exact molecular inputs"
    if step.capability_id == "admet.compare" and tool_input.role_order != ("candidate", "baseline"):
        return "ADMET comparison requires candidate then baseline role order"
    if step.capability_id == "admet.predict" and tool_input.role_order != ("candidate",):
        return "ADMET prediction requires one candidate input"
    if len(bindings) == 2 and bindings[0].inchikey == bindings[1].inchikey:
        return "ADMET comparison requires distinct molecular identities"
    return ""


def _bindings(tool_input):
    return ((tool_input.candidate, tool_input.baseline) if tool_input.baseline
            else (tool_input.candidate,))


def _arms(roles, bindings, inputs, prediction, properties):
    if not isinstance(prediction, ADMETBatchPrediction):
        raise TypeError("predictor returned an invalid batch")
    if prediction.input_smiles != inputs or len(prediction.rows) != len(inputs):
        raise ValueError("prediction rows do not preserve exact molecular input order")
    arms = []
    for role, binding, row in zip(roles, bindings, prediction.rows, strict=True):
        if not isinstance(row, Mapping):
            raise TypeError("ADMET prediction row must be an object")
        values = tuple(ADMETValue(name, _number(row, name)) for name in properties)
        arms.append(ADMETArmEvidence(role, binding, values))
    return tuple(arms)


def _number(row, name):
    value = row.get(name)
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"ADMET property is missing or non-numeric: {name}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"ADMET property is non-finite: {name}")
    return number


def _deltas(arms, properties):
    if len(arms) != 2:
        return ()
    candidate = dict((item.property_id, item.value) for item in arms[0].values)
    baseline = dict((item.property_id, item.value) for item in arms[1].values)
    return tuple(ADMETDelta(name, candidate[name] - baseline[name]) for name in properties)


def _failure(step, predictor, properties, status, message):
    return ADMETExecutionResult(status, step.capability_id, predictor.provider_id,
        predictor.model_name, predictor.model_version, properties, step.tool_input.role_order,
        _bindings(step.tool_input), coverage_gaps=(message,))
