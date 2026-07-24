import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.core.contracts import ArtifactRef  # noqa: E402
from agent.docking.docking_conformer import (  # noqa: E402
    ConformerSettings, LigandConformer, RDKitConformerBuilder,
)
from agent.docking.docking_execution import run_docking_workflow  # noqa: E402
from agent.docking.docking_local import CommandResult  # noqa: E402
from agent.docking.docking_types import (  # noqa: E402
    DockingConfig, DockingInput, PocketBinding, PocketRequest, TargetRequest,
    VerifiedTargetIdentity,
)
from agent.docking.dynamic_receptor import ReceptorComponentPolicy  # noqa: E402
from agent.docking.dynamic_receptor_pdbqt import repair_and_validate_receptor  # noqa: E402
from agent.docking.dynamic_vina import DynamicVinaConfig, DynamicVinaInputPreparer  # noqa: E402
from agent.molecular.molecular_binding import MolecularInputBinding  # noqa: E402
from agent.docking.pocket_geometry import PocketGeometry  # noqa: E402
from agent.app.research_factory import RuntimeConfig, build_research_service  # noqa: E402
from agent.docking.vina_plip_adapters import VinaDockingAdapter  # noqa: E402


KEY = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"


class FakeConformer:
    version = "fake-rdkit-1"

    def __init__(self, *, drift=False, failure="", seed=23, max_iterations=321):
        self.drift, self.failure, self.calls = drift, failure, []
        self.settings = ConformerSettings("fake-etkdg-v3", seed, max_iterations)

    def build(self, binding):
        self.calls.append(binding)
        if self.failure:
            raise ValueError(self.failure)
        key = "WRONG-INCHIKEY" if self.drift else binding.inchikey
        return LigandConformer(binding.canonical_isomeric_smiles, key,
                               b"ligand\n$$$$\n", 3)

    def identify_smiles(self, smiles):
        return ("CCO", KEY) if smiles == "CCO" else (smiles, "wrong-key")


class FakeRunner:
    def __init__(self, fail_stage="", malformed=""):
        self.fail_stage, self.malformed, self.calls = fail_stage, malformed, []

    def run(self, argv, cwd):
        self.calls.append((argv, cwd))
        tool = Path(argv[0]).name
        if self.fail_stage and self.fail_stage in tool:
            return CommandResult(2, "", "synthetic tool failure")
        if "ligand" in tool:
            output = Path(argv[argv.index("-o") + 1])
            output.write_text(_ligand_pdbqt(self.malformed))
        elif "receptor" in tool:
            output = Path(argv[argv.index("-p") + 1])
            output.write_text(_receptor_pdbqt(self.malformed))
        elif tool == "vina":
            output = Path(argv[argv.index("--out") + 1])
            output.write_text(_vina_output())
        return CommandResult(0, "ok", "")


class DynamicVinaTests(unittest.TestCase):
    def test_meeko_terminal_oxygen_permutation_is_exactly_normalized(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            source = root / "prepared.pdb"
            output = root / "receptor.pdbqt"
            source.write_text("\n".join((
                _atom("ATOM", 1, "N", "GLN", "A", 498, 0, 0, 0),
                _atom("ATOM", 2, "O", "GLN", "A", 498, 1, 0, 0),
                _atom("ATOM", 3, "OXT", "GLN", "A", 498, 2, 0, 0), "END")) + "\n")
            output.write_text("\n".join((
                _pdbqt_atom(1, "N", 0, 0, 0, "N"),
                _pdbqt_atom(2, "O", 2, 0, 0, "OA"),
                _pdbqt_atom(3, "OXT", 1, 0, 0, "OA"))) + "\n")
            details = repair_and_validate_receptor(output, source, "A")
            self.assertEqual(details,
                ("normalized:meeko_terminal_O_OXT_name_permutation=A:GLN498",))
            lines = output.read_text().splitlines()
            coordinates = {line[12:16].strip(): float(line[30:38]) for line in lines}
            self.assertEqual((coordinates["O"], coordinates["OXT"]), (1.0, 2.0))

    def test_dynamic_preparation_preserves_identity_components_box_and_command_lineage(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            value = _input(root, extra_components=("CL:A:1",))
            runner, conformer = FakeRunner(), FakeConformer()
            config = _config(root, ReceptorComponentPolicy(
                removable_components=("CL:A:1",)))
            preparer = DynamicVinaInputPreparer(root, config, conformer=conformer,
                runner=runner, run_id_factory=lambda: "dynamic-run-0001")
            adapter = VinaDockingAdapter(root, config.vina_executable, preparer,
                version=config.vina_version, runner=runner, config=config.docking_config)
            batch = adapter.dock(_with_provider(value, adapter))
            self.assertEqual([item.score for item in batch.poses], [-8.1, -7.4])
            self.assertEqual([Path(call[0][0]).name for call in runner.calls],
                             ["mk_prepare_ligand.py", "mk_prepare_receptor.py", "vina"])
            self.assertEqual((batch.molecule_inchikey, batch.target_identifier), (KEY, "1ABC"))
            self.assertEqual(len(batch.preparation_provenance), 4)
            self.assertEqual(batch.preparation_provenance[0].command_argv,
                             ("fake-etkdg-v3", "seed=23", "max_iterations=321", "threads=1"))
            selection = batch.preparation_provenance[1]
            self.assertIn("selected_chain=A", selection.details)
            self.assertIn("removed:reference_ligand:STI:A:999=1", selection.details)
            self.assertIn("removed:configured_component:CL:A:1=1", selection.details)
            self.assertEqual(selection.source_artifacts[0], value.target.structure_artifact)
            vina_argv = runner.calls[-1][0]
            self.assertEqual(vina_argv[vina_argv.index("--center_x") + 1], "1.0")
            self.assertEqual(vina_argv[vina_argv.index("--size_z") + 1], "20.0")
            self.assertEqual(_option(vina_argv, "--num_modes"), "9")
            self.assertEqual(_option(vina_argv, "--exhaustiveness"), "8")
            self.assertEqual(_option(vina_argv, "--cpu"), "4")
            self.assertEqual(_option(vina_argv, "--seed"), "20260719")
            self.assertEqual(_option(vina_argv, "--energy_range"), "10.0")
            self.assertTrue(all(Path(item.uri).resolve().is_relative_to(root)
                                for item in batch.input_artifacts))
            calls = len(runner.calls)
            with self.assertRaisesRegex(FileExistsError, "run directory"):
                adapter.dock(_with_provider(value, adapter))
            self.assertEqual(len(runner.calls), calls)

    def test_unknown_components_chain_identity_and_tool_failures_stop_before_vina(self):
        cases = (
            ("unknown", {"components": ("ZN:A:2",)}, FakeConformer(), FakeRunner(),
             "unapproved receptor"),
            ("identity-drift", {}, FakeConformer(drift=True), FakeRunner(), "identity"),
            ("nonfinite", {}, FakeConformer(failure="non-finite coordinates"), FakeRunner(),
             "non-finite"),
            ("ligand-tool", {}, FakeConformer(), FakeRunner("ligand"), "exited 2"),
            ("ligand-identity", {}, FakeConformer(), FakeRunner(malformed="identity"),
             "identity"),
            ("malformed-receptor", {}, FakeConformer(), FakeRunner(malformed="receptor"),
             "identity is malformed"),
            ("dropped-heavy-atom", {}, FakeConformer(), FakeRunner(malformed="dropped-heavy"),
             "preserve selected polymer heavy atoms"),
        )
        for name, options, conformer, runner, message in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
                root = Path(raw)
                value = _input(root, extra_components=options.get("components", ()))
                config = _config(root)
                preparer = DynamicVinaInputPreparer(root, config, conformer=conformer,
                    runner=runner, run_id_factory=lambda: "dynamic-run-0002")
                adapter = VinaDockingAdapter(root, config.vina_executable, preparer,
                    version=config.vina_version, runner=runner, config=config.docking_config)
                with self.assertRaisesRegex((ValueError, RuntimeError), message):
                    adapter.dock(_with_provider(value, adapter))
                self.assertNotIn("vina", [Path(call[0][0]).name for call in runner.calls])
                if name == "unknown":
                    self.assertEqual(runner.calls, [])

    def test_polymer_altloc_and_unattested_conformer_fail_before_tools(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            value = _input(root, polymer_altloc=True)
            runner, config = FakeRunner(), _config(root)
            preparer = DynamicVinaInputPreparer(root, config, conformer=FakeConformer(),
                runner=runner, run_id_factory=lambda: "dynamic-run-altloc")
            with self.assertRaisesRegex(ValueError, "alternate locations"):
                preparer.prepare(value)
            self.assertEqual(runner.calls, [])

            class UnattestedConformer:
                version = "fake"
            with self.assertRaisesRegex(ValueError, "cannot be attested"):
                DynamicVinaInputPreparer(root, config, conformer=UnattestedConformer())

    def test_preparation_failure_is_a_typed_partial_with_target_and_pocket_lineage(self):
        class TargetProvider:
            def __init__(self, value): self.value = value
            def resolve(self, request): return self.value
        class PocketProvider:
            def __init__(self, value): self.value = value
            def resolve(self, target, request): return self.value
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            value = _input(root, extra_components=("ZN:A:2",))
            runner, config = FakeRunner(), _config(root)
            preparer = DynamicVinaInputPreparer(root, config, conformer=FakeConformer(),
                runner=runner, run_id_factory=lambda: "dynamic-run-0004")
            adapter = VinaDockingAdapter(root, config.vina_executable, preparer,
                version=config.vina_version, runner=runner, config=config.docking_config)
            result = run_docking_workflow(value.molecule, TargetRequest("pdb", "1ABC", "A"),
                PocketRequest("site", "A", "pdb_auth", "reference_ligand",
                              reference_ligand="STI:A:999"),
                target_provider=TargetProvider(value.target),
                pocket_provider=PocketProvider(value.pocket), docking_provider=adapter)
            self.assertEqual(result.docking.status, "failed")
            self.assertEqual((result.target.identifier, result.pocket.pocket_id), ("1ABC", "site"))
            self.assertIn("unapproved receptor", result.coverage_gaps[-1])
            self.assertEqual(runner.calls, [])

    def test_disconnected_molecule_path_escape_and_missing_config_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            value = _input(root)
            config = _config(root)
            disconnected = MolecularInputBinding("full", "CCO.[Na+]", "salt-key", True)
            preparer = DynamicVinaInputPreparer(root, config, conformer=FakeConformer(),
                runner=FakeRunner(), run_id_factory=lambda: "dynamic-run-0003")
            with self.assertRaisesRegex(ValueError, "disconnected"):
                preparer.prepare(DockingInput(disconnected, value.target, value.pocket,
                    config.docking_config, "autodock-vina", config.vina_version))
            wrong_chain = replace(value.pocket, chain="B", reference_ligand="STI:B:202")
            with self.assertRaisesRegex(ValueError, "reference ligand or chain"):
                preparer.prepare(DockingInput(value.molecule, value.target, wrong_chain,
                    config.docking_config, "autodock-vina", config.vina_version))
            outside = root.parent / "outside-runs"
            escape = DynamicVinaConfig(config.vina_executable, config.ligand_executable,
                config.receptor_executable, outside, config.vina_version, config.meeko_version)
            with self.assertRaises(ValueError):
                DynamicVinaInputPreparer(root, escape, conformer=FakeConformer())
            service = build_research_service(RuntimeConfig(root, root / "memory.sqlite3"),
                                             runner=lambda *args, **kwargs: None)
            self.assertIsNone(service.docking_handler.docking_provider)

    def test_factory_composes_dynamic_preparer_only_from_explicit_config(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            config = _config(root)
            runner = FakeRunner()
            runtime = RuntimeConfig(root, root / "memory.sqlite3", dynamic_vina=config)
            service = build_research_service(runtime, runner=lambda *args, **kwargs: None,
                docking_runner=runner, docking_conformer=FakeConformer())
            provider = service.docking_handler.docking_provider
            self.assertIsInstance(provider, VinaDockingAdapter)
            self.assertIsInstance(provider.preparer, DynamicVinaInputPreparer)
            self.assertEqual(provider.default_config, config.docking_config)
            value = _with_provider(_input(root), provider)
            provider.dock(value)
            argv = runner.calls[-1][0]
            self.assertEqual((_option(argv, "--num_modes"), _option(argv, "--exhaustiveness"),
                              _option(argv, "--cpu"), _option(argv, "--seed"),
                              _option(argv, "--energy_range")),
                             ("9", "8", "4", "20260719", "10.0"))

    def test_real_rdkit_builder_is_deterministic_when_available(self):
        try:
            import rdkit  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("RDKit is optional outside the app runtime")
        binding = MolecularInputBinding("full", "CCO", KEY, True)
        builder = RDKitConformerBuilder(seed=17, max_iterations=500)
        first, second = builder.build(binding), builder.build(binding)
        self.assertEqual((first.inchikey, first.heavy_atom_count), (KEY, 3))
        self.assertEqual(first.sdf, second.sdf)
        with self.assertRaisesRegex(ValueError, "connected molecule"):
            builder.build(MolecularInputBinding("full", "CCO.[Na+]", "salt", True))


def _config(root, policy=ReceptorComponentPolicy()):
    tools = root / "tools"
    tools.mkdir(exist_ok=True)
    vina = _executable(tools / "vina")
    ligand = _executable(tools / "mk_prepare_ligand.py")
    receptor = _executable(tools / "mk_prepare_receptor.py")
    return DynamicVinaConfig(vina, ligand, receptor, root / "runs", "1.2.7", "0.7.1",
                             component_policy=policy)


def _input(root, extra_components=(), polymer_altloc=False):
    pdb = root / "1ABC.pdb"
    lines = [_header("1ABC"), _atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0),
             _atom("ATOM", 2, "CA", "GLY", "A", 1, 1, 0, 0),
             _atom("ATOM", 3, "N", "ALA", "B", 1, 5, 0, 0),
             _atom("HETATM", 4, "C1", "STI", "A", 999, 1, 2, 3),
             _atom("HETATM", 5, "O", "HOH", "A", 4, 2, 2, 3)]
    for index, component in enumerate(extra_components, 6):
        residue, chain, number = component.split(":")
        lines.append(_atom("HETATM", index, residue, residue, chain, int(number), 3, 3, 3))
    if polymer_altloc:
        lines[1] = lines[1][:16] + "A" + lines[1][17:]
    pdb.write_text("\n".join((*lines, "END")) + "\n")
    pocket_path = root / "site.json"
    pocket_path.write_text("{}\n")
    target_ref = ArtifactRef("rcsb-pdb-1ABC", pdb.name, "chemical/x-pdb", str(pdb))
    pocket_ref = ArtifactRef("rcsb-pocket-site", pocket_path.name, "application/json",
                             str(pocket_path))
    target = VerifiedTargetIdentity("pdb", "1ABC", ("A", "B"), target_ref,
        "rcsb-pdb", "test", "1ABC", "https://metadata", "https://coordinates")
    pocket = PocketBinding("site", "1ABC", "A", "pdb_auth", "reference_ligand", (),
        pocket_ref, "rcsb-pdb-pocket", "test", target_ref.id, "STI:A:999",
        PocketGeometry((1.0, 2.0, 3.0), (20.0, 20.0, 20.0), "angstrom",
                       "verified_reference_ligand_bounding_box", 5.0))
    return DockingInput(MolecularInputBinding("full", "CCO", KEY, True), target, pocket,
                        DockingConfig(score_name="vina_affinity_kcal_per_mol"),
                        "autodock-vina", "1.2.7")


def _with_provider(value, adapter):
    return DockingInput(value.molecule, value.target, value.pocket, adapter.default_config,
                        adapter.provider_id, adapter.provider_version)


def _executable(path):
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


def _header(entry):
    return "HEADER" + " " * 56 + entry


def _atom(record, serial, atom, residue, chain, number, x, y, z):
    return (f"{record:<6}{serial:>5} {atom:^4} {residue:>3} {chain}{number:>4}    "
            f"{x:>8.3f}{y:>8.3f}{z:>8.3f}  1.00 20.00           C")


def _ligand_pdbqt(malformed=""):
    if malformed == "ligand":
        return "REMARK SMILES wrong\n"
    smiles = "CCN" if malformed == "identity" else "CCO"
    return (f"REMARK SMILES {smiles}\nROOT\n"
            "ATOM      1  C   UNL     1       0.000   0.000   0.000  1.00  0.00 0.0 C\n"
            "ENDROOT\nTORSDOF 0\n")


def _receptor_pdbqt(malformed=""):
    chain = "B" if malformed == "receptor" else "A"
    atoms = [_atom("ATOM", 1, "N", "GLY", chain, 1, 0, 0, 0)]
    if malformed != "dropped-heavy":
        atoms.append(_atom("ATOM", 2, "CA", "GLY", chain, 1, 1, 0, 0))
    atoms.append(_atom("ATOM", 3, "H", "GLY", chain, 1, 0, 1, 0))
    return "\n".join(atoms) + "\n"


def _pdbqt_atom(serial, atom, x, y, z, atom_type):
    base = _atom("ATOM", serial, atom, "GLN", "A", 498, x, y, z)
    return base[:68] + f"{-0.55:>8.3f} {atom_type}"


def _option(argv, name):
    return argv[argv.index(name) + 1]


def _vina_output():
    atom = _atom("ATOM", 1, "C", "UNL", "A", 1, 0, 0, 0)
    return (f"MODEL 1\nREMARK VINA RESULT: -8.1 0 0\n{atom}\nENDMDL\n"
            f"MODEL 2\nREMARK VINA RESULT: -7.4 0 0\n{atom}\nENDMDL\n")


if __name__ == "__main__":
    unittest.main()
