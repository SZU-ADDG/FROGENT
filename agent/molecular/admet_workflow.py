"""Direct molecular intake, identity verification, and ADMET execution workflow."""

from dataclasses import dataclass

from agent.molecular.admet_ai_adapter import ADMETAIAdapter
from agent.molecular.admet_execution import (
    ADMETExecutionResult, ADMETPredictor, DEFAULT_ADMET_PROPERTIES, execute_admet_step,
)
from agent.molecular.molecular_identity import MoleculeNormalizer
from agent.molecular.molecular_routing import MolecularIntakeResult, prepare_molecular_request
from agent.molecular.pubchem_identity import (
    PubChemIdentityResolver, PubChemResolution, VerifiedMolecularRequest,
    prepare_molecular_request_from_name, verify_molecular_request,
)


@dataclass(frozen=True, slots=True)
class ADMETWorkflowResult:
    intake: MolecularIntakeResult | None
    verification: VerifiedMolecularRequest | PubChemResolution | None
    execution: ADMETExecutionResult | None
    coverage_gaps: tuple[str, ...]


def run_admet_workflow(smiles: str, intent: str, predictor: ADMETPredictor | None = None, *,
                       normalizer: MoleculeNormalizer | None = None,
                       pubchem_resolver: PubChemIdentityResolver | None = None,
                       claimed_name: str = "", requested_properties=DEFAULT_ADMET_PROPERTIES,
                       **request_kwargs) -> ADMETWorkflowResult:
    if pubchem_resolver:
        verified = verify_molecular_request(smiles, intent, pubchem_resolver,
            normalizer=normalizer, claimed_name=claimed_name, **request_kwargs)
        return _run(verified.intake, predictor or ADMETAIAdapter(), requested_properties, verified,
                    verified.coverage_gaps)
    intake = prepare_molecular_request(smiles, intent, normalizer, **request_kwargs)
    return _run(intake, predictor or ADMETAIAdapter(), requested_properties, None, ())


def run_admet_name_workflow(name: str, intent: str, resolver: PubChemIdentityResolver,
                            predictor: ADMETPredictor | None = None, *,
                            normalizer: MoleculeNormalizer | None = None,
                            requested_properties=DEFAULT_ADMET_PROPERTIES,
                            **request_kwargs) -> ADMETWorkflowResult:
    verified = prepare_molecular_request_from_name(name, intent, resolver,
        normalizer=normalizer, **request_kwargs)
    if isinstance(verified, PubChemResolution):
        return ADMETWorkflowResult(None, verified, None, verified.coverage_gaps)
    return _run(verified.intake, predictor or ADMETAIAdapter(), requested_properties, verified,
                verified.coverage_gaps)


def run_prepared_admet(intake: MolecularIntakeResult, predictor: ADMETPredictor,
                       requested_properties=DEFAULT_ADMET_PROPERTIES, *,
                       coverage_gaps: tuple[str, ...] = ()) -> ADMETWorkflowResult:
    return _run(intake, predictor, requested_properties, None, coverage_gaps)


def _run(intake, predictor, properties, verification, gaps):
    steps = tuple(item for item in intake.tool_plan.steps
                  if item.capability_id in {"admet.predict", "admet.compare"})
    if len(steps) != 1:
        return ADMETWorkflowResult(intake, verification, None,
                                   (*gaps, "request did not select one ADMET capability"))
    execution = execute_admet_step(steps[0], predictor, properties)
    merged = tuple(dict.fromkeys((*gaps, *intake.tool_plan.blockers,
                                  *execution.coverage_gaps)))
    return ADMETWorkflowResult(intake, verification, execution, merged)
