"""Typed event payloads and deterministic docking answers."""

from .contracts import StreamEvent


def workflow_events(workflow, identity_gaps):
    values = []
    target = workflow.target
    values.append(StreamEvent("tool.completed", {"capability_id": "target.standardize",
        "status": "verified" if target else "blocked",
        "target_identifier": target.identifier if target else "",
        "chains": list(target.chains) if target else [],
        "structure_artifact_id": target.structure_artifact.id if target else "",
        "metadata_url": target.metadata_url if target else "",
        "coordinate_url": target.coordinate_url if target else "",
        "provider": target.provider if target else "",
        "provider_version": target.provider_version if target else ""}, "docking"))
    pocket = workflow.pocket
    values.append(StreamEvent("tool.completed", {"capability_id": "pocket.prepare",
        "status": "verified" if pocket else "blocked", "pocket_id": pocket.pocket_id if pocket else "",
        "target_identifier": pocket.target_identifier if pocket else "",
        "chain": pocket.chain if pocket else "", "provider": pocket.provider if pocket else "",
        "provider_version": pocket.provider_version if pocket else "",
        "source_kind": pocket.source_kind if pocket else "",
        "target_artifact_id": pocket.target_artifact_id if pocket else "",
        "pocket_artifact_id": pocket.artifact.id if pocket else "",
        "residues": list(pocket.residues) if pocket else [],
        "reference_ligand": pocket.reference_ligand if pocket else "",
        "box": (_box_payload(pocket.box) if pocket and pocket.box else {})}, "docking"))
    docking = workflow.docking
    values.append(StreamEvent("tool.completed", {"capability_id": "docking.generate-conformation",
        "status": docking.status, "score_direction": (docking.docking_input.config.score_direction
        if docking.docking_input else ""), "poses": [{"pose_id": pose.pose_id, "rank": pose.rank,
        "score": pose.score, "artifact_id": pose.artifact.id} for pose in docking.poses],
        "provider": docking.provider, "provider_version": docking.provider_version,
        "input_artifact_ids": [item.id for item in docking.input_artifacts],
        "command_argv": list(docking.command_argv),
        "preparation_provenance": [_preparation_payload(item)
                                   for item in docking.preparation_provenance],
        **_state_payload(docking.state_lineage),
        "config": ({"pose_count": docking.docking_input.config.pose_count,
                    "exhaustiveness": docking.docking_input.config.exhaustiveness,
                    "cpu": docking.docking_input.config.cpu,
                    "seed": docking.docking_input.config.seed,
                    "energy_range": docking.docking_input.config.energy_range}
                   if docking.docking_input else {}),
        "warnings": list(docking.warnings), "coverage_gaps": list((*identity_gaps,
        *docking.coverage_gaps))}, "docking"))
    if workflow.interaction:
        item = workflow.interaction
        values.append(StreamEvent("tool.completed", {"capability_id": "sar.analyze",
            "status": item.status, "pose_id": item.pose_id,
            "resolved_pose_rank": item.pose_rank,
            "requested_pose_rank": item.requested_pose_rank,
            "provider": item.provider, "provider_version": item.provider_version,
            "complex_artifact_id": item.complex_artifact_id,
            "ligand_residue_identity": item.ligand_residue_identity,
            "command_argv": list(item.command_argv),
            "preparation_provenance": [_preparation_payload(value)
                                       for value in item.preparation_provenance],
            **_state_payload(item.state_lineage),
            "interactions": [_interaction_payload(value) for value in item.interactions],
            "warnings": list(item.warnings), "coverage_gaps": list(item.coverage_gaps)}, "docking"))
    return values


def plan_payload(plan):
    return {"capability_id": "molecular.plan", "status": "completed",
            "operation": plan.operation, "molecule": plan.molecule_value,
            "target_kind": plan.target.kind, "target_value": plan.target.value,
            "pocket_id": plan.pocket.pocket_id if plan.pocket else "",
            "selected_pose_id": plan.selected_pose_id,
            "selected_pose_rank": plan.selected_pose_rank,
            "pose_selection_text": plan.pose_selection_text,
            "selected_microstate_id": plan.selected_microstate_id,
            "selected_microstate_smiles": plan.selected_microstate_smiles,
            "receptor_ph": plan.receptor_ph}


def answer(binding, workflow, identity_gaps):
    lines = [f"Docking execution status: {workflow.docking.status}",
        f"molecule: scope={binding.scope}; SMILES={binding.canonical_isomeric_smiles}; "
        f"InChIKey={binding.inchikey}"]
    if workflow.target:
        lines.append(f"target: {workflow.target.kind}:{workflow.target.identifier}; "
                     f"chains={','.join(workflow.target.chains)}; "
                     f"artifact={workflow.target.structure_artifact.id}; "
                     f"provider={workflow.target.provider}")
    if workflow.pocket:
        lines.append(f"pocket: {workflow.pocket.pocket_id}; chain={workflow.pocket.chain}; "
                     f"numbering={workflow.pocket.numbering_scheme}; "
                     f"source={workflow.pocket.source_kind}; artifact={workflow.pocket.artifact.id}")
        if workflow.pocket.box:
            box = workflow.pocket.box
            lines.append(f"pocket box: center={box.center}; size={box.size}; units={box.units}; "
                         f"method={box.method}; margin={box.margin}")
    for pose in workflow.docking.poses:
        lines.append(f"pose {pose.pose_id}: rank={pose.rank}; score={pose.score:.12g}; "
                     f"artifact={pose.artifact.id}")
    lineage = workflow.docking.state_lineage
    if lineage.ligand_state_id:
        lines.append(f"ligand microstate: {lineage.ligand_state_id}")
    if lineage.receptor_state_id:
        lines.append(f"receptor state: {lineage.receptor_state_id}; pH={lineage.receptor_ph}; "
                     f"force_field={lineage.receptor_force_field}")
        lines.append("receptor heavy atoms: source="
            f"{lineage.receptor_source_heavy_atom_count}; prepared="
            f"{lineage.receptor_prepared_heavy_atom_count}")
        lines.append("receptor hydrogens: total="
            f"{lineage.receptor_hydrogen_atom_count}; zero_radius="
            f"{lineage.receptor_zero_radius_hydrogen_count}")
        lines.append(f"receptor pKa groups: total={lineage.receptor_pka_group_count}")
        lines.extend("receptor near-pH pKa: " + _pka_text(item)
                     for item in lineage.receptor_near_ph_pka_groups)
        lines.extend("receptor added atom: " + _added_atom_text(item)
                     for item in lineage.receptor_added_heavy_atoms)
        if lineage.receptor_moved_heavy_atom_count:
            lines.append("receptor prepared side-chain moves: count="
                f"{lineage.receptor_moved_heavy_atom_count}; max_displacement_A="
                f"{lineage.receptor_max_displacement:.6g}")
            lines.extend("receptor moved atom: " + _moved_atom_text(item)
                         for item in lineage.receptor_moved_heavy_atoms)
    if workflow.interaction:
        lines.append(f"interaction status: {workflow.interaction.status}; "
                     f"requested_rank={workflow.interaction.requested_pose_rank or 'none'}; "
                     f"resolved_rank={workflow.interaction.pose_rank or 'none'}; "
                     f"resolved_pose={workflow.interaction.pose_id or 'none'}")
        for item in workflow.interaction.interactions:
            lines.append(f"interaction: {item.interaction_type}; {item.protein_chain}:"
                         f"{item.protein_residue}; ligand={item.ligand_feature}")
    lines.extend("Warning: " + item for item in workflow.docking.warnings)
    if workflow.interaction:
        lines.extend("Warning: " + item for item in workflow.interaction.warnings)
    lines.extend("Coverage gap: " + item for item in dict.fromkeys(
        (*identity_gaps, *workflow.coverage_gaps)))
    lines.append("Computational docking evidence only; experimental_evidence=false. No binding "
                 "affinity, validated mechanism, or automatic pose-selection claim is inferred.")
    if lineage.ligand_state_id or lineage.receptor_state_id:
        lines.append("Enumerated ligand and receptor pH states are computational candidates; "
                     "dominant biological microstate and experimental effect are not established.")
    return "\n".join(lines)


def _state_payload(item):
    return {"ligand_state_id": item.ligand_state_id,
            "receptor_state_id": item.receptor_state_id,
            "receptor_ph": item.receptor_ph,
            "receptor_force_field": item.receptor_force_field,
            "receptor_source_heavy_atom_count": item.receptor_source_heavy_atom_count,
            "receptor_prepared_heavy_atom_count": item.receptor_prepared_heavy_atom_count,
            "receptor_added_heavy_atoms": [_added_atom_payload(value)
                                            for value in item.receptor_added_heavy_atoms],
            "receptor_moved_heavy_atom_count": item.receptor_moved_heavy_atom_count,
            "receptor_max_displacement": item.receptor_max_displacement,
            "receptor_moved_heavy_atoms": [_moved_atom_payload(value)
                                            for value in item.receptor_moved_heavy_atoms],
            "receptor_hydrogen_atom_count": item.receptor_hydrogen_atom_count,
            "receptor_zero_radius_hydrogen_count":
                item.receptor_zero_radius_hydrogen_count,
            "receptor_pka_group_count": item.receptor_pka_group_count,
            "receptor_near_ph_pka_groups": [_pka_payload(value)
                for value in item.receptor_near_ph_pka_groups]}


def _pka_payload(item):
    return {"residue_id": item.residue_id, "chain": item.chain,
        "auth_residue_number": item.auth_residue_number,
        "insertion_code": item.insertion_code, "group_name": item.group_name,
        "source_name": item.source_name, "prepared_name": item.prepared_name,
        "pka": item.pka}


def _pka_text(item):
    return (f"group={item.group_name}; residue_id={item.residue_id}; "
            f"source={item.source_name}; prepared={item.prepared_name}; pKa={item.pka:.6g}")


def _added_atom_payload(item):
    return {"chain": item.chain, "auth_residue_number": item.auth_residue_number,
        "insertion_code": item.insertion_code, "residue_name": item.residue_name,
        "atom_name": item.atom_name, "coordinates": list(item.coordinates)}


def _added_atom_text(item):
    residue = item.auth_residue_number + item.insertion_code
    return (f"{item.residue_name}:{item.chain}:{residue}:{item.atom_name}; "
            f"coordinates={item.coordinates}")


def _moved_atom_payload(item):
    return {"chain": item.chain, "auth_residue_number": item.auth_residue_number,
        "insertion_code": item.insertion_code, "residue_name": item.residue_name,
        "atom_name": item.atom_name, "source_coordinates": list(item.source_coordinates),
        "prepared_coordinates": list(item.prepared_coordinates),
        "displacement": item.displacement, "preparation_reason": item.preparation_reason}


def _moved_atom_text(item):
    residue = item.auth_residue_number + item.insertion_code
    return (f"{item.residue_name}:{item.chain}:{residue}:{item.atom_name}; "
            f"displacement_A={item.displacement:.6g}; reason={item.preparation_reason}")


def _interaction_payload(item):
    return {"interaction_type": item.interaction_type, "protein_chain": item.protein_chain,
            "protein_residue": item.protein_residue, "ligand_feature": item.ligand_feature,
            "distance": item.distance, "angle": item.angle}


def _box_payload(item):
    return {"center": list(item.center), "size": list(item.size), "units": item.units,
            "method": item.method, "margin": item.margin}


def _preparation_payload(item):
    return {"tool": item.tool, "version": item.version, "operation": item.operation,
            "source_artifact_ids": [value.id for value in item.source_artifacts],
            "output_artifact_ids": [value.id for value in item.output_artifacts],
            "command_argv": list(item.command_argv), "lossless": item.lossless,
            "moved_record_count": item.moved_record_count,
            "dropped_record_count": item.dropped_record_count,
            "details": list(item.details)}
