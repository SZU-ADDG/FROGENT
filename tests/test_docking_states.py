import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.core.contracts import ArtifactRef  # noqa: E402
from agent.docking.docking_local import CommandResult  # noqa: E402
from agent.docking.docking_microstates import (  # noqa: E402
    DimorphiteConfig, DimorphiteMicrostateProvider, StateDescriptor,
    RDKitStateInspector, _same_parent, binding_for_microstate, select_microstate,
)
from agent.docking.docking_state_runtime import selected_receptor  # noqa: E402
from agent.docking.docking_chat_render import (  # noqa: E402
    _state_payload, answer, workflow_events,
)
from agent.docking.docking_state_lineage import DockingStateLineage, state_lineage  # noqa: E402
from agent.docking.docking_state_types import (  # noqa: E402
    LigandStateSettings, ReceptorMovedHeavyAtom, ReceptorResidueState,
    ReceptorStateSettings,
)
from agent.docking.docking_env import ligand_states_from_env, receptor_states_from_env  # noqa: E402
from agent.app.research_factory import RuntimeConfig, build_research_service  # noqa: E402
from agent.docking.docking_types import (  # noqa: E402
    DockingConfig, DockingInput, PocketBinding, VerifiedTargetIdentity,
)
from agent.docking.dynamic_receptor import ReceptorComponentPolicy  # noqa: E402
from agent.molecular.molecular_binding import MolecularInputBinding  # noqa: E402
from agent.docking.pocket_geometry import PocketGeometry  # noqa: E402
from agent.docking.receptor_states import (  # noqa: E402
    PDB2PQRConfig, PDB2PQRReceptorStateProvider, _residue_states,
)
from agent.docking.receptor_state_validation import (  # noqa: E402
    state_changes, validate_pqr_bytes,
)


class Inspector:
    tool, version = "fake-rdkit-tautomer", "1"

    def __init__(self, drift=False, duplicate=False):
        self.drift, self.duplicate = drift, duplicate

    def inspect(self, smiles):
        stereo = ("2:S", "5:R") if self.drift and smiles != "CCO" else ("2:R", "5:S")
        key = "CONNECTION"
        return StateDescriptor(smiles, "SOURCE-KEY" if smiles == "CCO" else "STATE-KEY",
            0 if smiles == "CCO" else 1, key, stereo, 1)

    def tautomers(self, smiles, limit):
        first = self.inspect(smiles + "-tautomer")
        return (first, first) if self.duplicate else (first,)


class Runner:
    def __init__(self, stdout="CC[OH2+]\n", fail=False):
        self.stdout, self.fail, self.calls = stdout, fail, []

    def run(self, argv, cwd):
        self.calls.append((argv, cwd))
        return CommandResult(2 if self.fail else 0, self.stdout, "synthetic failure" if self.fail else "")


class PDBRunner:
    def __init__(self, mutation="", charge=-0.3,
                 propka="GLY 1 B 3.00\nGLY 1 A 6.50\n"):
        self.mutation, self.charge, self.propka, self.calls = mutation, charge, propka, []

    def run(self, argv, cwd):
        self.calls.append((argv, cwd))
        source, prepared, pqr = Path(argv[-2]), Path(argv[argv.index("--pdb-output") + 1]), Path(argv[-1])
        lines = [line for line in source.read_text().splitlines() if line.startswith("ATOM")]
        if self.mutation == "missing": lines.pop()
        if self.mutation == "terminal_oxt":
            lines.append(_atom("ATOM", 99, "OXT", "ALA", "A", 2, 3, 3, 3))
        if self.mutation == "wrong_oxt":
            lines.append(_atom("ATOM", 99, "OXT", "GLX", "A", 2, 3, 3, 3))
        if self.mutation == "internal_oxt":
            lines.append(_atom("ATOM", 99, "OXT", "GLY", "A", 1, 3, 3, 3))
        if self.mutation == "extra_atom":
            lines.append(_atom("ATOM", 99, "CD", "ALA", "A", 2, 3, 3, 3))
        if self.mutation == "moved":
            lines[0] = lines[0][:30] + f"{9.0:>8.3f}" + lines[0][38:]
        if self.mutation == "sidechain":
            index = next(i for i, line in enumerate(lines) if line[12:16].strip() == "CG")
            value = float(lines[index][30:38]) + 1
            lines[index] = lines[index][:30] + f"{value:>8.3f}" + lines[index][38:]
        prepared.write_text("HEADER    STATE\n" + "\n".join(lines) + "\nEND\n")
        pqr_lines = []
        for line in lines:
            serial, name, residue = int(line[6:11]), line[12:16].strip(), line[17:20].strip()
            chain, number = line[21].strip(), line[22:26].strip()
            xyz = [float(line[a:b]) for a, b in ((30, 38), (38, 46), (46, 54))]
            pqr_lines.append(f"ATOM {serial} {name} {residue} {chain} {number} "
                             f"{xyz[0]:.3f} {xyz[1]:.3f} {xyz[2]:.3f} {self.charge:.4f} 1.5000")
        if self.mutation == "duplicate": pqr_lines.append(pqr_lines[0])
        if self.mutation == "nan": pqr_lines[0] = pqr_lines[0].replace("0.000", "nan", 1)
        pqr.write_text("\n".join(pqr_lines) + "\n")
        if self.mutation in {"log_pka", "log_conflict", "malformed_pka", "unexpected_log"}:
            value = "nan" if self.mutation == "malformed_pka" else "6.50"
            pqr.with_suffix(".log").write_text("SUMMARY OF THIS PREDICTION\n"
                f"   GLY 1 A {value} 3.80\n\nend\n")
            if self.mutation == "unexpected_log":
                (cwd / "other.log").write_text("unexpected")
            stdout = "GLY 1 A 5.00\n" if self.mutation == "log_conflict" else ""
            return CommandResult(0, stdout, "")
        if self.mutation == "stderr_pka":
            return CommandResult(0, "", self.propka)
        return CommandResult(0, self.propka, "")


class DockingStateTests(unittest.TestCase):
    def test_ligand_states_are_bounded_replayable_and_require_exact_selection(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, runner = Path(raw), Runner()
            executable = _tool(root, "dimorphite_dl")
            settings = LigandStateSettings(7.0, 7.8, 0.5, 4, 3)
            provider = DimorphiteMicrostateProvider(root,
                DimorphiteConfig(executable, root / "states", "2.0.2", settings),
                inspector=Inspector(), runner=runner,
                run_id_factory=lambda: "ligand-state-run")
            source = MolecularInputBinding("full", "CCO", "SOURCE-KEY", True)
            states = provider.enumerate(source)
            state = states[0]
            message = f"select {state.state_id} at pH 7.0-7.8"
            selected = select_microstate(states, state_id=state.state_id,
                                         evidence=message, message=message)
            binding = binding_for_microstate(source, selected)
            self.assertEqual((binding.inchikey, selected.formal_charge), ("STATE-KEY", 1))
            manifest = json.loads(Path(state.source_artifact.uri).read_text())
            self.assertEqual(manifest["tautomer"]["max_tautomers"], 3)
            self.assertEqual(manifest["microstates"][0]["state_id"], state.state_id)
            self.assertEqual(runner.calls[0][0][1:7],
                             ("CCO", "--ph_min", "7.0", "--ph_max", "7.8", "--precision"))
            with self.assertRaises(ValueError):
                select_microstate(states, evidence="", message=message)
            with self.assertRaises(ValueError):
                select_microstate(states, state_id=state.state_id,
                                  selected_smiles=state.canonical_isomeric_smiles,
                                  evidence=message, message=message)

    def test_ligand_state_identity_stereo_duplicates_and_setting_types_fail_closed(self):
        with self.assertRaises(ValueError):
            LigandStateSettings(7, 8, 0.5, 2.0, 3)
        with self.assertRaisesRegex(ValueError, "total ligand microstate"):
            LigandStateSettings(7, 8, 0.5, 9, 8)
        for name, inspector, pattern in (
                ("stereo-swap", Inspector(drift=True), "stereochemistry"),
                ("duplicate", Inspector(duplicate=True), "duplicate")):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
                root = Path(raw)
                provider = DimorphiteMicrostateProvider(root,
                    DimorphiteConfig(_tool(root, "dimorphite_dl"), root / "states", "2.0.2",
                                    LigandStateSettings(7, 8, 0.5)),
                    inspector=inspector, runner=Runner(),
                    run_id_factory=lambda: f"state-{name}-run")
                with self.assertRaisesRegex(ValueError, pattern):
                    provider.enumerate(MolecularInputBinding("full", "CCO", "SOURCE-KEY", True))
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            provider = DimorphiteMicrostateProvider(root,
                DimorphiteConfig(_tool(root, "dimorphite_dl"), root / "states", "2.0.2",
                                LigandStateSettings(7, 8, 0.5)),
                inspector=Inspector(), runner=Runner(fail=True),
                run_id_factory=lambda: "state-failure-run")
            with self.assertRaisesRegex(RuntimeError, "Dimorphite exited 2") as caught:
                provider.enumerate(MolecularInputBinding("full", "CCO", "SOURCE-KEY", True))
            self.assertNotIn("synthetic failure", str(caught.exception))

    def test_rdkit_parent_graph_allows_protonation_and_rejects_adjacency_drift(self):
        try:
            inspector = RDKitStateInspector()
        except ModuleNotFoundError:
            self.skipTest("RDKit is unavailable")
        neutral = inspector.inspect("CN1CCNCC1")
        protonated = inspector.inspect("C[NH+]1CC[NH2+]CC1")
        self.assertEqual((neutral.connectivity_key, neutral.stereo_signature),
                         (protonated.connectivity_key, protonated.stereo_signature))
        linear = inspector.inspect("CCCO")
        branched = inspector.inspect("CC(C)O")
        self.assertNotEqual(linear.connectivity_key, branched.connectivity_key)
        left = inspector.inspect("F[C@H](Cl)[C@H](Br)I")
        swapped = inspector.inspect("F[C@@H](Cl)[C@H](Br)I")
        self.assertNotEqual(left.stereo_signature, swapped.stereo_signature)
        chiral = inspector.inspect("NCC[C@H](F)Cl")
        chiral_protonated = inspector.inspect("[NH3+]CC[C@H](F)Cl")
        self.assertEqual((chiral.connectivity_key, chiral.stereo_signature),
                         (chiral_protonated.connectivity_key,
                          chiral_protonated.stereo_signature))
        _same_parent(chiral, chiral_protonated, "legal protonation")
        unassigned = inspector.inspect("NCCC(F)Cl")
        self.assertNotEqual(unassigned.stereo_signature, chiral.stereo_signature)
        with self.assertRaisesRegex(ValueError, "stereochemistry"):
            _same_parent(unassigned, chiral, "assigned drift")
        with self.assertRaisesRegex(ValueError, "connectivity"):
            _same_parent(linear, branched, "constitutional drift")

    def test_receptor_state_binds_ph_charge_artifact_and_deduplicated_residues(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, target, pocket = _target_pocket(Path(raw))
            runner = PDBRunner()
            config = _pdb_config(root)
            state = PDB2PQRReceptorStateProvider(root, config, runner=runner,
                run_id_factory=lambda: "receptor-state-run").prepare(target, pocket)
            self.assertEqual((state.ph, state.force_field, len(state.residue_states)),
                             (7.4, "PARSE", 1))
            self.assertEqual(state.residue_states[0].pka, 6.5)
            self.assertIn("--titration-state-method", state.command_argv)
            self.assertNotIn("--nodebump", state.command_argv)
            self.assertNotIn("--noopt", state.command_argv)
            self.assertTrue(Path(state.charge_artifact.uri).is_file())
            value = DockingInput(MolecularInputBinding("full", "CCO", "KEY", True),
                target, pocket, DockingConfig(), receptor_state=state)
            selected = selected_receptor(root, value, config.component_policy)
            self.assertEqual(selected.pqr, Path(state.charge_artifact.uri))
            self.assertIn(f"receptor_state_id={state.state_id}", selected.details)

    def test_propka_summary_sources_are_bounded_and_fail_closed(self):
        for mutation in ("log_pka", "log_conflict", "stderr_pka"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
                    dir=ROOT / "tests") as raw:
                root, target, pocket = _target_pocket(Path(raw))
                state = PDB2PQRReceptorStateProvider(root, _pdb_config(root),
                    runner=PDBRunner(mutation), run_id_factory=lambda: f"{mutation}-run").prepare(
                        target, pocket)
                self.assertEqual(state.residue_states[0].pka, 6.5)
        for mutation, pattern in (("unexpected_log", "unexpected or ambiguous"),
                                  ("malformed_pka", "finite")):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
                    dir=ROOT / "tests") as raw:
                root, target, pocket = _target_pocket(Path(raw))
                provider = PDB2PQRReceptorStateProvider(root, _pdb_config(root),
                    runner=PDBRunner(mutation), run_id_factory=lambda: f"{mutation}-run")
                with self.assertRaisesRegex(ValueError, pattern):
                    provider.prepare(target, pocket)

    def test_receptor_state_requires_exact_pka_evidence(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, target, pocket = _target_pocket(Path(raw))
            provider = PDB2PQRReceptorStateProvider(root, _pdb_config(root),
                runner=PDBRunner(propka=""), run_id_factory=lambda: "empty-propka-run")
            with self.assertRaisesRegex(ValueError, "at least one exact PROPKA"):
                provider.prepare(target, pocket)
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, target, pocket = _target_pocket(Path(raw))
            state = PDB2PQRReceptorStateProvider(root, _pdb_config(root), runner=PDBRunner(),
                run_id_factory=lambda: "rename-only-run").prepare(target, pocket)
            renamed = ReceptorResidueState("GLY:A:1", "A", "1", "", "GLY",
                                           "GLY", "GLH")
            with self.assertRaisesRegex(ValueError, "at least one exact PROPKA"):
                replace(state, residue_states=(renamed,))

    def test_nearest_ph_pka_lineage_is_bounded_ordered_and_event_equal(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, target, pocket = _target_pocket(Path(raw))
            state = PDB2PQRReceptorStateProvider(root, _pdb_config(root), runner=PDBRunner(),
                run_id_factory=lambda: "pka-lineage-run").prepare(target, pocket)
            groups = tuple(ReceptorResidueState(f"ASP:A:{index:02d}", "A", str(index), "",
                "ASP", "ASP", "ASP", 7.4 + ((-1) ** index) * index / 100)
                for index in range(1, 21))
            state = replace(state, residue_states=groups)
            value = DockingInput(MolecularInputBinding("full", "CCO", "KEY", True),
                target, pocket, DockingConfig(), receptor_state=state)
            lineage = state_lineage(value)
            self.assertEqual(lineage.receptor_pka_group_count, 20)
            self.assertEqual(len(lineage.receptor_near_ph_pka_groups), 16)
            self.assertEqual(tuple(item.residue_id for item in
                lineage.receptor_near_ph_pka_groups),
                tuple(f"ASP:A:{index:02d}" for index in range(1, 17)))
            docking = SimpleNamespace(status="completed", docking_input=value, poses=(),
                provider="fake-vina", provider_version="1", input_artifacts=(),
                command_argv=(), preparation_provenance=(), state_lineage=lineage,
                warnings=(), coverage_gaps=())
            interaction = SimpleNamespace(status="completed", pose_id="pose-1", pose_rank=1,
                requested_pose_rank=1, provider="fake-plip", provider_version="1",
                complex_artifact_id="complex-1", ligand_residue_identity="LIG:Z:1",
                command_argv=(), preparation_provenance=(), state_lineage=lineage,
                interactions=(), warnings=(), coverage_gaps=())
            events = workflow_events(SimpleNamespace(target=target, pocket=pocket,
                docking=docking, interaction=interaction), ())
            vina, plip = events[2].payload, events[3].payload
            self.assertEqual(vina["receptor_near_ph_pka_groups"],
                             plip["receptor_near_ph_pka_groups"])
            self.assertEqual(vina["receptor_pka_group_count"], 20)
            self.assertNotIn("PROPKA", json.dumps(vina["receptor_near_ph_pka_groups"]))
            workflow = SimpleNamespace(target=target, pocket=pocket, docking=docking,
                                       interaction=interaction, coverage_gaps=())
            rendered = answer(value.molecule, workflow, ())
            self.assertIn("receptor pKa groups: total=20", rendered)
            self.assertIn("group=ASP; residue_id=ASP:A:01", rendered)

            near = lineage.receptor_near_ph_pka_groups
            mutations = (
                {"receptor_pka_group_count": 0},
                {"receptor_near_ph_pka_groups": tuple(reversed(near))},
                {"receptor_near_ph_pka_groups": near + (groups[16],)},
                {"receptor_near_ph_pka_groups": (replace(near[0], pka=None),)},
            )
            for mutation in mutations:
                with self.subTest(mutation=tuple(mutation)), self.assertRaisesRegex(
                        ValueError, "pKa"):
                    replace(lineage, **mutation)
            with self.assertRaisesRegex(ValueError, "requires a receptor state"):
                DockingStateLineage(receptor_pka_group_count=1,
                                    receptor_near_ph_pka_groups=(groups[0],))

    def test_receptor_state_atom_charge_and_artifact_drift_fail_closed(self):
        for mutation in ("missing", "duplicate", "nan"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
                root, target, pocket = _target_pocket(Path(raw))
                provider = PDB2PQRReceptorStateProvider(root, _pdb_config(root),
                    runner=PDBRunner(mutation), run_id_factory=lambda: f"receptor-{mutation}-run")
                with self.assertRaises(ValueError): provider.prepare(target, pocket)
        for mutation, pattern in (("internal_oxt", "unsupported heavy atom"),
                                  ("extra_atom", "unsupported heavy atom"),
                                  ("wrong_oxt", "residue identity"),
                                  ("moved", "moved")):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
                    dir=ROOT / "tests") as raw:
                root, target, pocket = _target_pocket(Path(raw))
                provider = PDB2PQRReceptorStateProvider(root, _pdb_config(root),
                    runner=PDBRunner(mutation), run_id_factory=lambda: f"{mutation}-run")
                with self.assertRaisesRegex(ValueError, pattern):
                    provider.prepare(target, pocket)
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, target, pocket = _target_pocket(Path(raw))
            path = Path(target.structure_artifact.uri)
            path.write_text("\n".join(line for line in path.read_text().splitlines()
                if not (line.startswith("ATOM") and line[22:26].strip() == "2"
                        and line[12:16].strip() == "O")) + "\n")
            provider = PDB2PQRReceptorStateProvider(root, _pdb_config(root),
                runner=PDBRunner("terminal_oxt"), run_id_factory=lambda: "missing-backbone-run")
            with self.assertRaisesRegex(ValueError, "unsupported heavy atom"):
                provider.prepare(target, pocket)
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, target, pocket = _target_pocket(Path(raw))
            state = PDB2PQRReceptorStateProvider(root, _pdb_config(root),
                runner=PDBRunner("terminal_oxt"),
                run_id_factory=lambda: "terminal-oxt-run").prepare(target, pocket)
            self.assertEqual((state.added_heavy_atoms[0].chain,
                              state.added_heavy_atoms[0].auth_residue_number,
                              state.added_heavy_atoms[0].residue_name,
                              state.added_heavy_atoms[0].atom_name,
                              state.added_heavy_atoms[0].coordinates),
                             ("A", "2", "ALA", "OXT", (3.0, 3.0, 3.0)))
            value = DockingInput(MolecularInputBinding("full", "CCO", "KEY", True),
                target, pocket, DockingConfig(), receptor_state=state)
            lineage = state_lineage(value)
            self.assertEqual((lineage.receptor_source_heavy_atom_count,
                              lineage.receptor_prepared_heavy_atom_count,
                              lineage.receptor_added_heavy_atoms),
                             (10, 11, state.added_heavy_atoms))
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, target, pocket = _target_pocket(Path(raw))
            config = _pdb_config(root)
            state = PDB2PQRReceptorStateProvider(root, config, runner=PDBRunner(),
                run_id_factory=lambda: "receptor-valid-run").prepare(target, pocket)
            value = DockingInput(MolecularInputBinding("full", "CCO", "KEY", True),
                target, pocket, DockingConfig(), receptor_state=state)
            Path(state.charge_artifact.uri).write_text(
                Path(state.charge_artifact.uri).read_text().replace("-0.3000", "-0.2000", 1))
            with self.assertRaisesRegex(ValueError, "identity"):
                selected_receptor(root, value, config.component_policy)

            state = PDB2PQRReceptorStateProvider(root, config, runner=PDBRunner(),
                run_id_factory=lambda: "receptor-valid-run-2").prepare(target, pocket)
            Path(state.artifact.uri).write_text(Path(state.artifact.uri).read_text().replace(
                "   1.000", "   9.000", 1))
            value = DockingInput(MolecularInputBinding("full", "CCO", "KEY", True),
                target, pocket, DockingConfig(), receptor_state=state)
            with self.assertRaisesRegex(ValueError, "backbone"):
                selected_receptor(root, value, config.component_policy)

            state = PDB2PQRReceptorStateProvider(root, config, runner=PDBRunner(),
                run_id_factory=lambda: "receptor-valid-run-3").prepare(target, pocket)
            wrong = replace(state, state_id="receptor-wrong-state")
            value = DockingInput(MolecularInputBinding("full", "CCO", "KEY", True),
                target, pocket, DockingConfig(), receptor_state=wrong)
            with self.assertRaisesRegex(ValueError, "identity"):
                selected_receptor(root, value, config.component_policy)

    def test_sidechain_moves_are_bounded_typed_and_immutable(self):
        source = _heavy_map(5)
        prepared = dict(source)
        for key, shift in ((('1', '', 'ND1'), 1.0), (('2', '', 'OD1'), 2.0),
                           (('3', '', 'OE1'), 2.3), (('4', '', 'OG1'), 0.5)):
            name, xyz = prepared[key]
            prepared[key] = (name, (xyz[0] + shift, xyz[1], xyz[2]))
        added, moved = state_changes(source, prepared, "A")
        self.assertEqual(added, ())
        self.assertEqual(tuple(item.atom_name for item in moved),
                         ("ND1", "OD1", "OE1", "OG1"))
        self.assertEqual(tuple(item.preparation_reason for item in moved),
            ("pdb2pqr_normal_sidechain_preparation",) * 4)
        with self.assertRaisesRegex(ValueError, "provenance"):
            replace(moved[0], displacement=moved[0].displacement + 0.01)
        backbone = dict(source)
        name, xyz = backbone[('1', '', 'CA')]
        backbone[('1', '', 'CA')] = (name, (xyz[0] + 0.1, xyz[1], xyz[2]))
        with self.assertRaisesRegex(ValueError, "backbone"):
            state_changes(source, backbone, "A")
        excessive = dict(source)
        name, xyz = excessive[('1', '', 'ND1')]
        excessive[('1', '', 'ND1')] = (name, (xyz[0] + 4.1, xyz[1], xyz[2]))
        with self.assertRaisesRegex(ValueError, "provenance"):
            state_changes(source, excessive, "A")
        fraction = dict(prepared)
        name, xyz = fraction[('5', '', 'ND1')]
        fraction[('5', '', 'ND1')] = (name, (xyz[0] + 0.2, xyz[1], xyz[2]))
        with self.assertRaisesRegex(ValueError, "exceeds"):
            state_changes(source, fraction, "A")
        many_source = _heavy_map(322)
        many_prepared = dict(many_source)
        for residue in range(1, 258):
            key = (str(residue), "", "ND1")
            name, xyz = many_prepared[key]
            many_prepared[key] = (name, (xyz[0] + 0.1, xyz[1], xyz[2]))
        with self.assertRaisesRegex(ValueError, "exceeds"):
            state_changes(many_source, many_prepared, "A")

        with self.assertRaisesRegex(ValueError, "inconsistent"):
            DockingStateLineage(receptor_state_id="state", receptor_ph=7.4,
                receptor_force_field="PARSE", receptor_source_heavy_atom_count=40,
                receptor_prepared_heavy_atom_count=40,
                receptor_moved_heavy_atom_count=1, receptor_max_displacement=0)

        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, target, pocket = _target_pocket(Path(raw))
            config = _pdb_config(root)
            state = PDB2PQRReceptorStateProvider(root, config, runner=PDBRunner("sidechain"),
                run_id_factory=lambda: "sidechain-move-run").prepare(target, pocket)
            self.assertEqual(len(state.moved_heavy_atoms), 1)
            value = DockingInput(MolecularInputBinding("full", "CCO", "KEY", True),
                target, pocket, DockingConfig(), receptor_state=state)
            lineage = state_lineage(value)
            self.assertEqual((lineage.receptor_moved_heavy_atom_count,
                              lineage.receptor_max_displacement,
                              lineage.receptor_moved_heavy_atoms),
                             (1, 1.0, state.moved_heavy_atoms))
            payload = _state_payload(lineage)
            self.assertEqual((payload["receptor_moved_heavy_atom_count"],
                              payload["receptor_max_displacement"],
                              payload["receptor_moved_heavy_atoms"][0]["atom_name"]),
                             (1, 1.0, "CG"))
            with self.assertRaisesRegex(ValueError, "bound"):
                replace(state, moved_heavy_atoms=(replace(
                    state.moved_heavy_atoms[0], chain="B"),))
            selected_receptor(root, value, config.component_policy)
            moved_pdb = Path(state.artifact.uri)
            moved_pdb.write_text(moved_pdb.read_text().replace("   4.000", "   4.100", 1))
            with self.assertRaises(ValueError):
                selected_receptor(root, value, config.component_policy)

    def test_pqr_zero_hydrogen_radius_is_finite_and_identity_safe(self):
        expected = {("1", "", "N"): ("GLY", (0.0, 0.0, 0.0))}
        expected_all = {("1", "", "N"): ("GLY", (0.0, 0.0, 0.0), False),
                        ("1", "", "H"): ("GLY", (0.1, 0.0, 0.0), True)}
        heavy = b"ATOM 1 N GLY A 1 0.000 0.000 0.000 -0.3000 1.5000\n"
        hydrogen = b"ATOM 2 H GLY A 1 0.100 0.000 0.000 0.3000 0.0000\n"
        raw = heavy + hydrogen
        self.assertEqual(validate_pqr_bytes(raw, "A", expected, expected_all), (1, 1))
        mutations = {
            "zero heavy": raw.replace(b"1.5000\n", b"0.0000\n", 1),
            "negative radius": raw.replace(b"0.0000\n", b"-0.1000\n", 1),
            "missing hydrogen": heavy,
            "extra hydrogen": raw + b"ATOM 3 H2 GLY A 1 0.200 0.000 0.000 0.0 0.0\n",
            "duplicate hydrogen": raw + hydrogen,
            "hydrogen coordinate": raw.replace(b"0.100 0.000", b"0.200 0.000"),
            "charge nan": raw.replace(b"0.3000 0.0000", b"nan 0.0000"),
            "hydrogen identity": raw.replace(b" 2 H GLY", b" 2 H2 GLY"),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_pqr_bytes(mutation, "A", expected, expected_all)


    def test_propka_identity_binds_regular_and_terminal_groups(self):
        source = {("1", "", "N"): ("MET", (0.0, 0.0, 0.0)),
                  ("2", "", "CA"): ("GLU", (1.0, 0.0, 0.0)),
                  ("3", "", "C"): ("GLN", (2.0, 0.0, 0.0))}
        text = "N+ 1 A 8.10\nGLU 2 A 4.20\nC- 3 A 3.10\nN+ 1 A 8.10\n"
        states = _residue_states(source, source, text, "A")
        self.assertEqual(tuple((item.group_name, item.chain, item.auth_residue_number,
                                item.insertion_code, item.pka) for item in states),
                         (("N+", "A", "1", "", 8.1),
                          ("GLU", "A", "2", "", 4.2),
                          ("C-", "A", "3", "", 3.1)))
        for bad, pattern in (("N+ 2 A 8.1", "terminus"),
                             ("ASP 2 A 4.2", "does not match"),
                             ("GLU 2 A 4.2\nGLU 2 A 4.3", "conflicting")):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, pattern):
                _residue_states(source, source, bad, "A")
        ambiguous = {**source, ("2", "A", "CB"): ("GLU", (1.1, 0.0, 0.0))}
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            _residue_states(ambiguous, ambiguous, "GLU 2 A 4.2", "A")

    def test_state_environment_is_explicit_bounded_and_same_venv(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            bin_dir = root / "venv/bin"; bin_dir.mkdir(parents=True)
            dimorphite = _tool(bin_dir, "dimorphite_dl")
            pdb2pqr = _tool(bin_dir, "pdb2pqr")
            propka = _tool(bin_dir, "propka3")
            memory = root / "memory.sqlite3"
            complete = {"FROGENT_MEMORY_DB": str(memory),
                "FROGENT_DIMORPHITE_EXECUTABLE": str(dimorphite),
                "FROGENT_DIMORPHITE_VERSION": "2.0.2", "FROGENT_LIGAND_PH_MIN": "7.0",
                "FROGENT_LIGAND_PH_MAX": "7.8", "FROGENT_LIGAND_PH_PRECISION": "0.5",
                "FROGENT_MAX_PROTOMERS": "8", "FROGENT_MAX_TAUTOMERS": "8",
                "FROGENT_PDB2PQR_EXECUTABLE": str(pdb2pqr),
                "FROGENT_PROPKA_EXECUTABLE": str(propka),
                "FROGENT_PDB2PQR_VERSION": "3.7.1", "FROGENT_PROPKA_VERSION": "3.5.1",
                "FROGENT_RECEPTOR_PH": "7.4", "FROGENT_PDB2PQR_FORCE_FIELD": "PARSE"}
            with patch.dict("os.environ", {"FROGENT_MEMORY_DB": str(memory)}, clear=True):
                config = RuntimeConfig.from_env(root)
                self.assertIsNone(config.ligand_states)
                self.assertIsNone(config.receptor_states)
            with patch.dict("os.environ", {
                    "FROGENT_DIMORPHITE_EXECUTABLE": str(dimorphite)}, clear=True):
                with self.assertRaisesRegex(ValueError, "explicit"):
                    ligand_states_from_env(root)
            with patch.dict("os.environ", complete, clear=True):
                config = RuntimeConfig.from_env(root)
                service = build_research_service(config, runner=lambda *args, **kwargs: None)
            self.assertIsNotNone(service.docking_handler.microstate_provider)
            receptor = service.docking_handler.receptor_state_provider
            self.assertIsNotNone(receptor)
            self.assertEqual((receptor.config.settings.ph, receptor.propka), (7.4, propka))
            with patch.dict("os.environ", {**complete,
                    "FROGENT_MAX_PROTOMERS": "9"}, clear=True):
                with self.assertRaisesRegex(ValueError, "total ligand microstate"):
                    RuntimeConfig.from_env(root)

    def test_receptor_tools_must_share_one_isolated_environment(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            first = root / "one/bin"; second = root / "two/bin"
            first.mkdir(parents=True); second.mkdir(parents=True)
            config = PDB2PQRConfig(_tool(first, "pdb2pqr"), _tool(second, "propka3"),
                root / "states", "3.7.1", "3.5.1", ReceptorStateSettings(7.4))
            with self.assertRaisesRegex(ValueError, "share one isolated"):
                PDB2PQRReceptorStateProvider(root, config)


def _tool(root, name):
    path = root / name
    path.write_text("tool")
    path.chmod(0o700)
    return path


def _target_pocket(root):
    target_path = root / "1ABC.pdb"
    target_path.write_text("HEADER" + " " * 56 + "1ABC\n"
        + _atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0) + "\n"
        + _atom("ATOM", 2, "CA", "GLY", "A", 1, 1, 0, 0) + "\n"
        + _atom("ATOM", 3, "C", "GLY", "A", 1, 1, 1, 0) + "\n"
        + _atom("ATOM", 4, "O", "GLY", "A", 1, 1, 2, 0) + "\n"
        + _atom("ATOM", 5, "N", "ALA", "A", 2, 2, 1, 0) + "\n"
        + _atom("ATOM", 6, "CA", "ALA", "A", 2, 2, 2, 0) + "\n"
        + _atom("ATOM", 7, "C", "ALA", "A", 2, 2, 3, 0) + "\n"
        + _atom("ATOM", 8, "O", "ALA", "A", 2, 2, 4, 0) + "\n"
        + _atom("ATOM", 9, "CB", "ALA", "A", 2, 3, 2, 0) + "\n"
        + _atom("ATOM", 10, "CG", "ALA", "A", 2, 3, 3, 0) + "\n"
        + _atom("HETATM", 11, "C1", "STI", "A", 999, 2, 2, 2) + "\nEND\n")
    target_ref = ArtifactRef("target", target_path.name, "chemical/x-pdb", str(target_path))
    target = VerifiedTargetIdentity("pdb", "1ABC", ("A",), target_ref,
                                    "rcsb-pdb", "1", "1ABC")
    pocket_path = root / "pocket.json"; pocket_path.write_text("{}")
    pocket = PocketBinding("site", "1ABC", "A", "pdb_auth", "reference_ligand", (),
        ArtifactRef("pocket", pocket_path.name, "application/json", str(pocket_path)),
        "fake", "1", target_ref.id, "STI:A:999",
        PocketGeometry((1, 1, 1), (10, 10, 10), "angstrom", "test", 5))
    return root, target, pocket


def _pdb_config(root):
    return PDB2PQRConfig(_tool(root, "pdb2pqr"), _tool(root, "propka3"),
        root / "receptor-states", "3.7.1", "3.5.1", ReceptorStateSettings(7.4))


def _atom(record, serial, name, residue, chain, number, x, y, z):
    return (f"{record:<6}{serial:>5} {name:^4} {residue:>3} {chain}{number:>4}    "
            f"{x:>8.3f}{y:>8.3f}{z:>8.3f}  1.00  0.00          {name[0]:>2}")


def _heavy_map(residue_count):
    names = ("N", "CA", "C", "O", "ND1", "OD1", "OE1", "OG1")
    residues = ("HIS", "ASN", "GLN", "THR", "SER")
    values = {}
    for residue in range(1, residue_count + 1):
        for offset, atom in enumerate(names):
            values[(str(residue), "", atom)] = (
                residues[(residue - 1) % len(residues)], (float(residue), float(offset), 0.0))
    return values


if __name__ == "__main__":
    unittest.main()
