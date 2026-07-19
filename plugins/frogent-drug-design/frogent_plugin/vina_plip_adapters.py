"""Project-contained AutoDock Vina and PLIP command adapters."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .contracts import ArtifactRef
from .docking_local import (
    CommandRunner, PLIPConfig, PLIPInputPreparer, SubprocessCommandRunner, VinaInputPreparer,
    contained_directory, contained_executable, contained_file,
)
from .docking_types import (
    DockingBatch, DockingConfig, DockingInput, DockingPose, InteractionBatch,
    InteractionEvidence,
)


class VinaDockingAdapter:
    provider_id = "autodock-vina"

    def __init__(self, root: Path, executable: Path, preparer: VinaInputPreparer, *,
                 version: str, runner: CommandRunner | None = None,
                 config: DockingConfig | None = None) -> None:
        self.root = root.resolve(strict=True)
        self.executable = contained_executable(self.root, executable)
        if not version.strip():
            raise ValueError("Vina version must be explicit")
        self.provider_version, self.preparer = version, preparer
        self.runner = runner or SubprocessCommandRunner()
        self.default_config = config or DockingConfig(score_name="vina_affinity_kcal_per_mol",
            score_direction="lower_is_better")
        if (self.default_config.score_name != "vina_affinity_kcal_per_mol"
                or self.default_config.score_direction != "lower_is_better"):
            raise ValueError("Vina adapter config has invalid score semantics")

    def dock(self, value: DockingInput) -> DockingBatch:
        if value.provider != self.provider_id or value.provider_version != self.provider_version:
            raise ValueError("Vina input provider identity mismatch")
        if value.config.score_name != "vina_affinity_kcal_per_mol" \
                or value.config.score_direction != "lower_is_better":
            raise ValueError("Vina score semantics must be explicit")
        prepared = self.preparer.prepare(value)
        if (prepared.molecule_inchikey != value.molecule.inchikey
                or prepared.target_artifact_id != value.target.structure_artifact.id
                or prepared.pocket_artifact_id != value.pocket.artifact.id):
            raise ValueError("prepared Vina artifacts do not match docking lineage")
        receptor = contained_file(self.root, prepared.receptor)
        ligand = contained_file(self.root, prepared.ligand)
        output_dir = contained_directory(self.root, prepared.output_directory)
        output = output_dir / f"{prepared.run_id}.pdbqt"
        if output.exists() or output.is_symlink():
            raise FileExistsError("Vina output path already exists")
        argv = _vina_argv(self.executable, receptor, ligand, output, prepared, value.config)
        result = self.runner.run(argv, output_dir)
        if result.returncode:
            raise RuntimeError(f"Vina exited {result.returncode}: {result.stderr.strip()}")
        poses = _vina_poses(self.root, output, prepared.run_id, value.config.pose_count)
        return DockingBatch(value.molecule.canonical_isomeric_smiles, value.molecule.inchikey,
            value.target.identifier, value.pocket.pocket_id, self.provider_id,
            self.provider_version, value.config.score_name, value.config.score_direction, poses,
            (prepared.receptor, prepared.ligand, value.pocket.artifact), argv,
            prepared.preparation_provenance)


class PLIPInteractionAdapter:
    provider_id = "plip"

    def __init__(self, root: Path, executable: Path, preparer: PLIPInputPreparer, *,
                 version: str, runner: CommandRunner | None = None,
                 config: PLIPConfig | None = None) -> None:
        self.root = root.resolve(strict=True)
        self.executable = contained_executable(self.root, executable)
        if not version.strip():
            raise ValueError("PLIP version must be explicit")
        self.provider_version, self.preparer = version, preparer
        self.runner = runner or SubprocessCommandRunner()
        self.config = config or PLIPConfig()

    def analyze(self, value: DockingInput, pose: DockingPose) -> InteractionBatch:
        prepared = self.preparer.prepare(value, pose)
        if (prepared.source_pose_artifact_id != pose.artifact.id
                or prepared.target_artifact_id != value.target.structure_artifact.id):
            raise ValueError("prepared PLIP complex does not match selected pose lineage")
        complex_path = contained_file(self.root, prepared.complex_artifact)
        output_dir = contained_directory(self.root, prepared.output_directory)
        if any(output_dir.glob("*.xml")):
            raise FileExistsError("PLIP output directory already contains XML")
        argv = (str(self.executable), "-f", str(complex_path), "-x", "-o", str(output_dir),
                "--maxthreads", str(self.config.maxthreads),
                *(() if self.config.add_polar_hydrogens else ("--nohydro",)))
        result = self.runner.run(argv, output_dir)
        if result.returncode:
            raise RuntimeError(f"PLIP exited {result.returncode}: {result.stderr.strip()}")
        reports = tuple(sorted(output_dir.glob("*_report.xml")))
        if len(reports) != 1:
            raise ValueError("PLIP must produce exactly one XML report")
        report = reports[0]
        interactions = _plip_interactions(self.root, report, prepared.ligand_residue_identity)
        return InteractionBatch(pose.pose_id, pose.artifact.id, value.molecule.inchikey,
            value.target.identifier, self.provider_id, self.provider_version, interactions,
            prepared.complex_artifact.id, argv, prepared.ligand_residue_identity)


def _vina_argv(executable, receptor, ligand, output, prepared, config):
    center, size = prepared.center, prepared.size
    return (str(executable), "--receptor", str(receptor), "--ligand", str(ligand),
            "--center_x", str(center[0]), "--center_y", str(center[1]),
            "--center_z", str(center[2]), "--size_x", str(size[0]),
            "--size_y", str(size[1]), "--size_z", str(size[2]),
            "--exhaustiveness", str(config.exhaustiveness), "--cpu", str(config.cpu),
            "--energy_range", str(config.energy_range),
            "--num_modes", str(config.pose_count), *(() if config.seed is None else
            ("--seed", str(config.seed))), "--out", str(output))


def _vina_poses(root, output, run_id, limit):
    resolved = output.resolve(strict=True)
    resolved.relative_to(root)
    text = resolved.read_text(encoding="utf-8")
    blocks = _model_blocks(text)
    if not blocks or len(blocks) > limit:
        raise ValueError("Vina pose count is invalid")
    values = []
    for rank, block in enumerate(blocks, 1):
        match = re.search(r"^REMARK VINA RESULT:\s+(-?\d+(?:\.\d+)?)", block, re.MULTILINE)
        if not match:
            raise ValueError("Vina pose score is missing")
        path = resolved.parent / f"{run_id}-pose-{rank}.pdbqt"
        if path.exists() or path.is_symlink():
            raise FileExistsError("Vina pose artifact already exists")
        path.write_text(block.rstrip() + "\n", encoding="utf-8")
        ref = ArtifactRef(f"{run_id}-pose-{rank}", path.name, "chemical/x-pdbqt", str(path))
        values.append(DockingPose(ref.id, rank, float(match.group(1)), ref))
    return tuple(values)


def _model_blocks(text):
    starts = [match.start() for match in re.finditer(r"^MODEL\s+\d+\s*$", text, re.MULTILINE)]
    if not starts:
        return (text,) if "REMARK VINA RESULT:" in text else ()
    starts.append(len(text))
    return tuple(text[starts[index]:starts[index + 1]] for index in range(len(starts) - 1))


def _plip_interactions(root, report, expected_ligand=""):
    resolved = report.resolve(strict=True)
    resolved.relative_to(root)
    try:
        tree = ET.parse(resolved)
    except ET.ParseError as exc:
        raise ValueError("PLIP XML is malformed") from exc
    sites = tree.findall(".//bindingsite")
    if expected_ligand:
        sites = [site for site in sites if _ligand_identity(site) == expected_ligand]
        if len(sites) != 1:
            raise ValueError("PLIP ligand residue identity is missing or ambiguous")
    values = []
    for site in sites:
        groups = site.find("interactions")
        if groups is None:
            continue
        for group in groups:
            for item in group:
                values.append(_interaction(group.tag, item))
    return tuple(values)


def _ligand_identity(site):
    identifiers = site.find("identifiers")
    if identifiers is None:
        return ""
    return ":".join(_xml_text(identifiers, name) for name in ("hetid", "chain", "position"))


def _interaction(kind, item):
    chain = _xml_text(item, "reschain")
    residue = _xml_text(item, "restype") + _xml_text(item, "resnr")
    feature = _ligand_feature(item)
    if not chain or not residue or not feature:
        raise ValueError("PLIP interaction identity is incomplete")
    distance = _optional_float(item, ("dist", "distance", "dist_h-a", "centdist"))
    angle = _optional_float(item, ("angle", "don_angle"))
    return InteractionEvidence(kind.removesuffix("s"), chain, residue, feature, distance, angle)


def _xml_text(item, name):
    value = item.findtext(name)
    return value.strip() if isinstance(value, str) else ""


def _first_text(item, names):
    return next((value for name in names if (value := _xml_text(item, name))), "")


def _ligand_feature(item):
    direct = _first_text(item, ("ligcarbonidx", "ligatomidx", "lig_idx", "ligandidx"))
    if direct:
        return direct
    indexes = tuple(value.text.strip() for value in item.findall("./lig_idx_list/idx")
                    if isinstance(value.text, str) and value.text.strip())
    if indexes:
        return ",".join(indexes)
    protein_is_donor = _xml_text(item, "protisdon").casefold() == "true"
    return _first_text(item, (("acceptoridx", "donoridx") if protein_is_donor else
                              ("donoridx", "acceptoridx", "lig_group")))


def _optional_float(item, names):
    value = _first_text(item, names)
    return float(value) if value else None
