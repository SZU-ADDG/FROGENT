"""Bounded Dimorphite protomers and app-RDKit tautomers."""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Callable, Protocol

from agent.core.contracts import ArtifactRef
from agent.docking.docking_local import CommandRunner, SubprocessCommandRunner, contained_executable
from agent.docking.docking_state_types import LigandMicrostate, LigandStateSettings
from agent.molecular.molecular_binding import MolecularInputBinding
from agent.docking.rcsb_target import _make_contained_directory


@dataclass(frozen=True, slots=True)
class StateDescriptor:
    smiles: str
    inchikey: str
    formal_charge: int
    connectivity_key: str
    stereo_signature: tuple[str, ...]
    fragment_count: int


class StateInspector(Protocol):
    tool: str
    version: str
    def inspect(self, smiles: str) -> StateDescriptor: ...
    def tautomers(self, smiles: str, limit: int) -> tuple[StateDescriptor, ...]: ...


class MicrostateSelectionRequired(Exception):
    def __init__(self, states):
        super().__init__("one exact ligand microstate selection is required")
        self.states = tuple(states)


@dataclass(frozen=True, slots=True)
class DimorphiteConfig:
    executable: Path
    run_root: Path
    version: str
    settings: LigandStateSettings

    def __post_init__(self) -> None:
        if not self.executable.is_absolute() or not self.run_root.is_absolute():
            raise ValueError("Dimorphite paths must be absolute")
        if not self.version.strip():
            raise ValueError("Dimorphite version must be explicit")


class DimorphiteMicrostateProvider:
    def __init__(self, root: Path, config: DimorphiteConfig, *, inspector=None,
                 runner: CommandRunner | None = None,
                 run_id_factory: Callable[[], str] | None = None) -> None:
        self.root, self.config = root.resolve(strict=True), config
        self.executable = contained_executable(self.root, config.executable)
        config.run_root.relative_to(self.root)
        self.inspector = inspector or RDKitStateInspector()
        self.runner = runner or SubprocessCommandRunner()
        self.run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)

    def enumerate(self, binding: MolecularInputBinding) -> tuple[LigandMicrostate, ...]:
        if not binding.selection_confirmed or binding.canonical_isomeric_smiles.count("."):
            raise ValueError("microstate enumeration requires one confirmed connected molecule")
        source = self.inspector.inspect(binding.canonical_isomeric_smiles)
        if source.inchikey != binding.inchikey or source.fragment_count != 1:
            raise ValueError("microstate source identity mismatch")
        run_id, run_dir = self._run_directory()
        settings = self.config.settings
        argv = (str(self.executable), binding.canonical_isomeric_smiles,
                "--ph_min", str(settings.ph_min), "--ph_max", str(settings.ph_max),
                "--precision", str(settings.precision),
                "--max_variants", str(settings.max_protomers), "--log_level", "none")
        result = self.runner.run(argv, run_dir)
        if result.returncode:
            raise RuntimeError(f"Dimorphite exited {result.returncode}")
        protomers = tuple(line.strip() for line in result.stdout.splitlines() if line.strip())
        if not protomers or len(protomers) > settings.max_protomers:
            raise ValueError("Dimorphite protomer count is empty or exceeds its bound")
        warnings = _warnings(result.stderr)
        source_ref = self._manifest(run_dir, run_id, binding, argv, protomers, warnings)
        states = self._states(source, source_ref, protomers, warnings)
        if len(states) > 64:
            raise ValueError("final ligand microstate count exceeds 64")
        if len({item.state_id for item in states}) != len(states) \
                or len({item.canonical_isomeric_smiles for item in states}) != len(states):
            raise ValueError("microstate enumeration returned duplicate states")
        self._finalize_manifest(source_ref, states)
        return states

    def _states(self, source, artifact, protomers, warnings):
        values = []
        for protomer_index, raw in enumerate(protomers, 1):
            protomer = self.inspector.inspect(raw)
            _same_parent(source, protomer, "protomer")
            protomer_id = _state_id("protomer", protomer.smiles)
            tautomers = self.inspector.tautomers(protomer.smiles,
                                                self.config.settings.max_tautomers)
            if not tautomers or len(tautomers) > self.config.settings.max_tautomers:
                raise ValueError("RDKit tautomer count is empty or exceeds its bound")
            for tautomer in tautomers:
                _same_parent(source, tautomer, "tautomer")
                values.append(_microstate(self.config, self.inspector, source, artifact,
                                          protomer_id, tautomer, warnings))
        return tuple(values)

    def _run_directory(self):
        run_id = self.run_id_factory()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{7,63}", run_id):
            raise ValueError("microstate run identity is invalid")
        _make_contained_directory(self.root, self.config.run_root)
        path = self.config.run_root / run_id
        if path.exists() or path.is_symlink():
            raise FileExistsError("microstate run directory already exists")
        path.mkdir()
        return run_id, path.resolve(strict=True)

    def _manifest(self, run_dir, run_id, binding, argv, protomers, warnings):
        path = run_dir / "dimorphite-output.json"
        payload = {"schema_version": "ligand-protomers-v1", "run_id": run_id,
            "source_smiles": binding.canonical_isomeric_smiles,
            "source_inchikey": binding.inchikey, "argv": list(argv),
            "protomers": list(protomers), "warnings": list(warnings)}
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        return ArtifactRef(f"{run_id}-protomers", path.name, "application/json",
                           str(path.resolve(strict=True)))

    def _finalize_manifest(self, artifact, states):
        path = Path(artifact.uri)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["tautomer"] = {"tool": self.inspector.tool,
            "version": self.inspector.version,
            "max_tautomers": self.config.settings.max_tautomers}
        payload["microstates"] = [{"state_id": item.state_id,
            "protomer_id": item.protomer_id, "smiles": item.canonical_isomeric_smiles,
            "inchikey": item.inchikey, "formal_charge": item.formal_charge}
            for item in states]
        path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
                        encoding="utf-8")


class RDKitStateInspector:
    tool = "rdkit-tautomer-enumerator"

    def __init__(self) -> None:
        self.chem = import_module("rdkit.Chem")
        self.hasher = import_module("rdkit.Chem.rdMolHash")
        self.enumerator_type = import_module("rdkit.Chem.MolStandardize.rdMolStandardize")
        self.version = import_module("rdkit.rdBase").rdkitVersion

    def inspect(self, smiles):
        molecule = self.chem.MolFromSmiles(smiles, sanitize=True)
        if molecule is None:
            raise ValueError("RDKit rejected a ligand state")
        canonical = self.chem.MolToSmiles(molecule, isomericSmiles=True, canonical=True)
        key = self.chem.MolToInchiKey(molecule)
        ranks = _graph_ranks(self.chem, molecule)
        stereo = tuple(sorted(f"{ranks[index]}:{label}" for index, label in
            self.chem.FindMolChiralCenters(molecule, includeUnassigned=True,
                                           useLegacyImplementation=False)))
        heavy_count = sum(atom.GetAtomicNum() > 1 for atom in molecule.GetAtoms())
        graph = self.hasher.MolHash(molecule, self.hasher.HashFunction.ElementGraph)
        connectivity = f"{heavy_count}:{graph}"
        return StateDescriptor(canonical, key, self.chem.GetFormalCharge(molecule),
            connectivity, stereo, len(self.chem.GetMolFrags(molecule)))

    def tautomers(self, smiles, limit):
        molecule = self.chem.MolFromSmiles(smiles, sanitize=True)
        enumerator = self.enumerator_type.TautomerEnumerator()
        enumerator.SetMaxTautomers(limit)
        return tuple(self.inspect(self.chem.MolToSmiles(item, isomericSmiles=True))
                     for item in enumerator.Enumerate(molecule))


def select_microstate(states, *, state_id="", selected_smiles="", evidence="", message=""):
    if bool(state_id) == bool(selected_smiles):
        raise ValueError("select exactly one ligand microstate ID or SMILES")
    if not evidence or evidence not in message:
        raise ValueError("ligand microstate selection requires exact current-message evidence")
    matches = [item for item in states if (item.state_id == state_id if state_id else
                                           item.canonical_isomeric_smiles == selected_smiles)]
    if len(matches) != 1 or (state_id or selected_smiles) not in evidence:
        raise ValueError("selected ligand microstate is missing or ambiguous")
    return matches[0]


def binding_for_microstate(source: MolecularInputBinding, state: LigandMicrostate):
    if state.source_inchikey != source.inchikey or not source.selection_confirmed:
        raise ValueError("selected microstate does not match the confirmed source binding")
    return MolecularInputBinding(source.scope, state.canonical_isomeric_smiles,
        state.inchikey, True, source.removed_fragments)


def _same_parent(source, value, label):
    source_stereo = dict(item.split(":", 1) for item in source.stereo_signature)
    value_stereo = dict(item.split(":", 1) for item in value.stereo_signature)
    stereo_drift = any(value_stereo.get(rank) != stereo
                       for rank, stereo in source_stereo.items())
    stereo_drift |= any(stereo != "?" and rank not in source_stereo
                        for rank, stereo in value_stereo.items())
    if value.fragment_count != 1 or value.connectivity_key != source.connectivity_key \
            or stereo_drift:
        raise ValueError(f"{label} connectivity, fragments, or stereochemistry drifted")


def _graph_ranks(chem, molecule):
    graph = chem.RWMol(molecule)
    for atom in graph.GetAtoms():
        atom.SetFormalCharge(0)
        atom.SetChiralTag(chem.ChiralType.CHI_UNSPECIFIED)
        atom.SetIsAromatic(False)
    for bond in graph.GetBonds():
        bond.SetBondType(chem.BondType.SINGLE)
        bond.SetIsAromatic(False)
        bond.SetStereo(chem.BondStereo.STEREONONE)
    graph.UpdatePropertyCache(strict=False)
    return tuple(chem.CanonicalRankAtoms(graph, breakTies=True, includeChirality=False))


def _state_id(prefix, smiles):
    return prefix + "-" + hashlib.sha256(smiles.encode()).hexdigest()[:16]


def _microstate(config, inspector, source, artifact, protomer_id, value, warnings):
    settings = config.settings
    return LigandMicrostate(_state_id("microstate", value.smiles), protomer_id,
        value.smiles, value.inchikey, value.formal_charge, value.connectivity_key,
        settings.ph_min, settings.ph_max, settings.precision, "dimorphite-dl",
        config.version, inspector.tool, inspector.version, source.inchikey, artifact, warnings)


def _warnings(stderr):
    count = len(tuple(line for line in stderr.splitlines() if line.strip()))
    if not count:
        return ()
    return (f"Dimorphite emitted {count} nonfatal stderr warning line(s); "
            "every accepted stdout state was independently validated",)
