"""Explicit PDB2PQR/PROPKA receptor pH state preparation."""

import math
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from .contracts import ArtifactRef
from .docking_local import CommandRunner, SubprocessCommandRunner, contained_executable
from .docking_state_types import (ReceptorResidueState, ReceptorStateBinding,
                                  ReceptorStateSettings)
from .docking_types import PocketBinding, VerifiedTargetIdentity
from .dynamic_receptor import ReceptorComponentPolicy, select_receptor
from .rcsb_target import _make_contained_directory
from .receptor_state_validation import (heavy_atoms, pdb_atoms, receptor_state_id,
                                        text_artifact, state_changes, validate_pqr)


@dataclass(frozen=True, slots=True)
class PDB2PQRConfig:
    executable: Path
    propka_executable: Path
    run_root: Path
    version: str
    propka_version: str
    settings: ReceptorStateSettings
    component_policy: ReceptorComponentPolicy = ReceptorComponentPolicy()

    def __post_init__(self) -> None:
        if not all(path.is_absolute() for path in (
                self.executable, self.propka_executable, self.run_root)):
            raise ValueError("PDB2PQR/PROPKA paths must be absolute")
        if not self.version.strip() or not self.propka_version.strip():
            raise ValueError("PDB2PQR/PROPKA versions must be explicit")


class PDB2PQRReceptorStateProvider:
    def __init__(self, root: Path, config: PDB2PQRConfig, *, runner=None,
                 run_id_factory: Callable[[], str] | None = None) -> None:
        self.root, self.config = root.resolve(strict=True), config
        self.executable = contained_executable(self.root, config.executable)
        self.propka = contained_executable(self.root, config.propka_executable)
        if self.executable.parent != self.propka.parent:
            raise ValueError("PDB2PQR and propka3 must share one isolated venv/bin directory")
        config.run_root.relative_to(self.root)
        self.runner = runner or SubprocessCommandRunner()
        self.run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)

    def prepare(self, target: VerifiedTargetIdentity, pocket: PocketBinding):
        if target.kind != "pdb" or pocket.target_artifact_id != target.structure_artifact.id:
            raise ValueError("receptor state requires exact PDB target/pocket lineage")
        placeholder = SimpleNamespace(target=target, pocket=pocket)
        selected, decisions, _ = select_receptor(
            self.root, placeholder, self.config.component_policy)
        run_id, run_dir = self._run_directory()
        source = _write(run_dir / "selected-receptor.pdb", selected)
        prepared, pqr = run_dir / "ph-prepared-receptor.pdb", run_dir / "receptor.pqr"
        settings = self.config.settings
        argv = (str(self.executable), "--titration-state-method", "propka",
                "--with-ph", str(settings.ph), "--keep-chain", "--ff",
                settings.force_field, "--pdb-output", str(prepared),
                str(source), str(pqr))
        result = self.runner.run(argv, run_dir)
        if result.returncode:
            raise RuntimeError(f"PDB2PQR exited {result.returncode}")
        source_atoms = heavy_atoms(source, pocket.chain)
        prepared_atoms = heavy_atoms(prepared, pocket.chain)
        prepared_all = pdb_atoms(prepared, pocket.chain)
        added, moved = state_changes(source_atoms, prepared_atoms, pocket.chain)
        hydrogen_count, zero_radius_count = validate_pqr(
            pqr, pocket.chain, prepared_atoms, prepared_all)
        propka_text = _propka_text(run_dir, pqr, result)
        residues = _residue_states(source_atoms, prepared_atoms, propka_text, pocket.chain)
        state_id = receptor_state_id(target.identifier, pocket.chain, settings.ph,
            settings.force_field, self.config.version, self.config.propka_version,
            str(self.propka), prepared.read_bytes(), pqr.read_bytes())
        prepared_ref = _ref(f"{run_id}-receptor-state", prepared, "chemical/x-pdb")
        pqr_ref = _ref(f"{run_id}-receptor-pqr", pqr, "chemical/x-pqr")
        return ReceptorStateBinding(state_id, target.identifier,
            target.structure_artifact.id, pocket.chain, settings.ph,
            settings.force_field, "pdb2pqr-propka", self.config.version,
            self.config.propka_version, str(self.propka), prepared_ref, pqr_ref, argv, residues,
            len(prepared_atoms), len(source_atoms), added, moved,
            hydrogen_count, zero_radius_count)

    def _run_directory(self):
        run_id = self.run_id_factory()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{7,63}", run_id):
            raise ValueError("receptor state run identity is invalid")
        _make_contained_directory(self.root, self.config.run_root)
        path = self.config.run_root / run_id
        if path.exists() or path.is_symlink():
            raise FileExistsError("receptor state run directory already exists")
        path.mkdir()
        return run_id, path.resolve(strict=True)


def _residue_states(source, prepared, stdout, chain):
    pka = {}
    pattern = r"(?m)^\s*([A-Z]{3}|N\+|C-)\s+(-?\d+)\s+([A-Za-z0-9])\s+(\S+)"
    for group, number, parsed_chain, raw_value in re.findall(pattern, stdout):
        if parsed_chain == chain:
            value = float(raw_value)
            if not math.isfinite(value):
                raise ValueError("PROPKA residue pKa must be finite")
            key = (group, parsed_chain, number)
            if key in pka and pka[key] != value:
                raise ValueError("PROPKA residue pKa is conflicting")
            pka[key] = value
    residue_names = {}
    for key in source:
        residue_key = (key[0], key[1])
        names = (source[key][0], prepared[key][0])
        if residue_key in residue_names and residue_names[residue_key] != names:
            raise ValueError("receptor residue naming is internally inconsistent")
        residue_names[residue_key] = names
    order = tuple(residue_names)
    values, represented = [], set()
    for group, parsed_chain, number in sorted(pka, key=lambda item: (int(item[2]), item[0])):
        candidates = tuple(key for key in order if key[0] == number)
        if len(candidates) != 1:
            raise ValueError("PROPKA residue identity is absent or insertion-code ambiguous")
        key = candidates[0]
        source_name, prepared_name = residue_names[key]
        if group == "N+" and key != order[0] or group == "C-" and key != order[-1]:
            raise ValueError("PROPKA terminal group does not match the source terminus")
        if group not in {"N+", "C-"} and (source_name != group or prepared_name != group):
            raise ValueError("PROPKA group does not match the receptor residue identity")
        residue_id = f"{group}:{parsed_chain}:{number}{key[1]}"
        values.append(ReceptorResidueState(residue_id, parsed_chain, number, key[1], group,
                                           source_name, prepared_name,
                                           pka[(group, parsed_chain, number)]))
        represented.add(key)
    for key in order:
        source_name, prepared_name = residue_names[key]
        if source_name != prepared_name and key not in represented:
            group = source_name
            values.append(ReceptorResidueState(f"{group}:{chain}:{key[0]}{key[1]}", chain,
                key[0], key[1], group, source_name, prepared_name))
    return tuple(values)


def _propka_text(run_dir, pqr, result):
    expected = pqr.with_suffix(".log")
    artifacts = tuple(run_dir.glob("*.log"))
    if any(item != expected for item in artifacts) or tuple(run_dir.glob("*.propka")):
        raise ValueError("PROPKA produced an unexpected or ambiguous pKa artifact")
    if expected.exists() or expected.is_symlink():
        text = text_artifact(expected, "PROPKA pKa artifact")
        marker = "SUMMARY OF THIS PREDICTION"
        if marker not in text:
            raise ValueError("PROPKA pKa summary is missing")
        summary = text.split(marker, 1)[1].split("\n\n", 1)[0]
        return summary
    return "\n".join(item for item in (result.stdout, result.stderr) if item)


def _write(path, raw):
    with path.open("xb") as handle:
        handle.write(raw)
    return path.resolve(strict=True)


def _ref(identity, path, media):
    return ArtifactRef(identity, path.name, media, str(path.resolve(strict=True)))
