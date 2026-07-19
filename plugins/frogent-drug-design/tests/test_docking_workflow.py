import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frogent_plugin.contracts import ArtifactRef, ExecutionContext  # noqa: E402
from frogent_plugin.docking_chat import DockingChatHandler, is_clear_docking_intent  # noqa: E402
from frogent_plugin.docking_chat_plan import CodexDockingPlanner  # noqa: E402
from frogent_plugin.docking_execution import run_docking_workflow  # noqa: E402
from frogent_plugin.docking_local import (  # noqa: E402
    BoundPLIPPreparer, BoundVinaPreparer, CommandResult, MeekoPreparationConfig,
    MeekoPreparedVinaPreparer, PLIPConfig, PLIPPreparedInput, VinaPreparedInput,
)
from frogent_plugin.docking_preparation import PreparationProvenance  # noqa: E402
from frogent_plugin.docking_types import (  # noqa: E402
    DockingBatch, DockingConfig, DockingPose, InteractionBatch, InteractionEvidence,
    PocketBinding, PocketRequest, TargetRequest, VerifiedTargetIdentity,
)
from frogent_plugin.docking_state_lineage import state_lineage  # noqa: E402
from frogent_plugin.docking_state_types import (  # noqa: E402
    LigandMicrostate, ReceptorStateSettings,
)
from frogent_plugin.molecular_binding import MolecularInputBinding  # noqa: E402
from frogent_plugin.molecular_identity import MolecularIdentity  # noqa: E402
from frogent_plugin.pubchem_identity import PubChemResolution  # noqa: E402
from frogent_plugin.pocket_geometry import PocketGeometry  # noqa: E402
from frogent_plugin.research_service import ResearchService  # noqa: E402
from frogent_plugin.vina_plip_adapters import (  # noqa: E402
    PLIPInteractionAdapter, VinaDockingAdapter,
)


def artifact(value, media="chemical/x-pdb"): return ArtifactRef(value, value, media, "memory://" + value)


MOLECULE = MolecularInputBinding("full", "CCO", "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", True)
TARGET = VerifiedTargetIdentity("pdb", "1ABC", ("A",), artifact("target-1abc"),
                                "fake-target", "1", "1ABC")
POCKET_REQUEST = PocketRequest("site-1", "A", "pdb_author", "residues", ("ASP25", "GLY27"))
POCKET = PocketBinding("site-1", "1ABC", "A", "pdb_author", "residues",
                       ("ASP25", "GLY27"), artifact("pocket-1"), "fake-pocket", "1")


class TargetProvider:
    calls = 0
    def resolve(self, request):
        self.calls += 1
        return TARGET


class PocketProvider:
    calls = 0
    def resolve(self, target, request):
        self.calls += 1
        return POCKET


class DockProvider:
    provider_id = "fake-dock"
    provider_version = "1"

    def __init__(self, fail=False): self.calls, self.fail = [], fail
    def dock(self, value):
        self.calls.append(value)
        if self.fail:
            raise RuntimeError("engine offline")
        poses = tuple(DockingPose(f"pose-{index}", index, float(-9 + index),
                      artifact(f"pose-artifact-{index}")) for index in (1, 2, 3))
        return DockingBatch(value.molecule.canonical_isomeric_smiles, value.molecule.inchikey,
            value.target.identifier, value.pocket.pocket_id, "fake-dock", "1",
            value.config.score_name, value.config.score_direction, poses)


class PLIPProvider:
    provider_id = "fake-plip"
    provider_version = "2"

    def __init__(self, fail=False): self.calls, self.fail = [], fail
    def analyze(self, value, pose):
        self.calls.append((value, pose))
        if self.fail:
            raise RuntimeError("PLIP failed")
        interaction = InteractionEvidence("hydrogen_bond", "A", "ASP25", "O1", 2.8, 165.0)
        return InteractionBatch(pose.pose_id, pose.artifact.id, value.molecule.inchikey,
                                value.target.identifier, "fake-plip", "2", (interaction,))


class StructuredClient:
    def __init__(self, value): self.value, self.calls = value, []
    def generate(self, role, contract, payload, *, schema):
        self.calls.append((role, contract, payload, schema))
        return self.value


class FakeNormalizer:
    def normalize(self, smiles):
        if smiles != "CCO":
            raise ValueError("unexpected smiles")
        return MolecularIdentity("CCO", "CCO", "CCO", "InChI=1S/C2H6O", MOLECULE.inchikey,
            "C2H6O", 46.0, 0, 3, 1, 1, "single", False, 0, 0, "none")


class Resolver:
    normalizer = FakeNormalizer()
    def resolve_binding(self, binding):
        return PubChemResolution(None, None, (), ("PubChem unavailable",))


def planner_value(**updates):
    value = {"operation": "dock_and_interactions", "molecule_kind": "smiles",
        "molecule_value": "CCO", "molecule_scope": "unspecified",
        "selected_structure_smiles": "", "molecule_selection_text": "",
        "selected_microstate_id": "", "selected_microstate_smiles": "",
        "microstate_selection_text": "",
        "target_kind": "pdb", "target_value": "1ABC", "target_chain": "A",
        "target_text": "1ABC chain A", "pocket_id": "site-1", "pocket_kind": "residues",
        "pocket_chain": "A", "numbering_scheme": "pdb_author",
        "residue_ids": ["ASP25", "GLY27"], "reference_ligand": "",
        "pocket_artifact_id": "",
        "pocket_artifact_name": "", "pocket_artifact_media_type": "",
        "pocket_artifact_uri": "", "pocket_text": "site-1 ASP25 GLY27",
        "selected_pose_id": "pose-2", "selected_pose_rank": 0,
        "pose_selection_text": "pose-2", "receptor_ph": -1,
        "receptor_state_text": ""}
    value.update(updates)
    return value


MESSAGE = "Dock CCO to 1ABC chain A using site-1 ASP25 GLY27 and analyze pose-2 with PLIP"


class DockingWorkflowTests(unittest.TestCase):
    def test_exact_lineage_pose_order_and_selected_pose_interactions(self):
        dock, plip = DockProvider(), PLIPProvider()
        result = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"),
            POCKET_REQUEST, target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=dock, interaction_provider=plip, want_interactions=True,
            selected_pose_id="pose-2")
        self.assertEqual(result.docking.status, "completed")
        self.assertEqual([item.pose_id for item in result.docking.poses],
                         ["pose-1", "pose-2", "pose-3"])
        self.assertEqual(result.docking.docking_input.molecule, MOLECULE)
        self.assertEqual(result.docking.docking_input.target.identifier, "1ABC")
        self.assertEqual(result.docking.docking_input.pocket.pocket_id, "site-1")
        self.assertEqual(result.docking.docking_input.provider, "fake-dock")
        self.assertEqual(result.docking.docking_input.config.score_direction, "lower_is_better")
        self.assertEqual(plip.calls[0][1].pose_id, "pose-2")
        self.assertEqual(result.interaction.interactions[0].protein_residue, "ASP25")
        ranked = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"),
            POCKET_REQUEST, target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=DockProvider(), interaction_provider=PLIPProvider(),
            want_interactions=True, selected_pose_rank=1)
        self.assertEqual((ranked.interaction.requested_pose_rank,
                          ranked.interaction.pose_rank, ranked.interaction.pose_id),
                         (1, 1, "pose-1"))

    def test_missing_or_unverified_target_and_pocket_are_zero_call(self):
        dock = DockProvider()
        named = run_docking_workflow(MOLECULE, TargetRequest("name_candidate", "kinase"),
                                     None, docking_provider=dock)
        missing = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"), None,
                                       target_provider=TargetProvider(), docking_provider=dock)
        self.assertEqual((named.docking.status, missing.docking.status), ("blocked", "blocked"))
        self.assertEqual(dock.calls, [])
        self.assertIn("unverified candidate", named.coverage_gaps[0])
        self.assertIn("explicit verified pocket", missing.coverage_gaps[0])

    def test_unconfirmed_molecule_and_unreadable_artifact_never_reach_docking(self):
        class BrokenPocket(PocketProvider):
            def resolve(self, target, request): raise ValueError("artifact unreadable")
        dock = DockProvider()
        unconfirmed = replace(MOLECULE, selection_confirmed=False)
        blocked = run_docking_workflow(unconfirmed, TargetRequest("pdb", "1ABC", "A"),
            POCKET_REQUEST, target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=dock)
        request = PocketRequest("artifact-site", "A", "pdb_author", "artifact",
                                artifact=artifact("user-pocket"))
        unreadable = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"), request,
            target_provider=TargetProvider(), pocket_provider=BrokenPocket(), docking_provider=dock)
        self.assertEqual((blocked.docking.status, unreadable.docking.status),
                         ("blocked", "blocked"))
        self.assertEqual(dock.calls, [])
        self.assertIn("not confirmed", blocked.coverage_gaps[-1])
        self.assertIn("artifact unreadable", unreadable.coverage_gaps[-1])

    def test_target_and_pocket_identity_mismatch_fail_closed(self):
        class WrongTarget(TargetProvider):
            def resolve(self, request): return replace(TARGET, identifier="2XYZ")
        class WrongPocket(PocketProvider):
            def resolve(self, target, request): return replace(POCKET, chain="B")
        dock = DockProvider()
        target = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"),
            POCKET_REQUEST, target_provider=WrongTarget(), pocket_provider=PocketProvider(),
            docking_provider=dock)
        pocket = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"),
            POCKET_REQUEST, target_provider=TargetProvider(), pocket_provider=WrongPocket(),
            docking_provider=dock)
        self.assertIn("does not match", target.coverage_gaps[0])
        self.assertIn("lineage", pocket.coverage_gaps[0])
        self.assertEqual(dock.calls, [])

    def test_docking_failure_and_plip_failure_preserve_safe_partial(self):
        failed = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"),
            POCKET_REQUEST, target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=DockProvider(True), want_interactions=True,
            selected_pose_id="pose-1")
        partial = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"),
            POCKET_REQUEST, target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=DockProvider(), interaction_provider=PLIPProvider(True),
            want_interactions=True, selected_pose_id="pose-1")
        self.assertEqual(failed.docking.status, "failed")
        self.assertEqual(partial.docking.status, "completed")
        self.assertEqual(len(partial.docking.poses), 3)
        self.assertEqual(partial.interaction.status, "failed")

    def test_no_explicit_pose_never_auto_selects_best_pose(self):
        plip = PLIPProvider()
        result = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"),
            POCKET_REQUEST, target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=DockProvider(), interaction_provider=plip, want_interactions=True)
        self.assertEqual(result.interaction.status, "blocked")
        self.assertEqual(plip.calls, [])
        self.assertIn("exactly one explicit pose", result.coverage_gaps[-1])

    def test_malformed_provider_output_is_local_failure(self):
        class BadDock(DockProvider):
            def dock(self, value):
                batch = super().dock(value)
                return replace(batch, target_identifier="2XYZ")
        result = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"),
            POCKET_REQUEST, target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=BadDock())
        self.assertEqual(result.docking.status, "failed")
        self.assertIn("do not match", result.coverage_gaps[-1])


class LocalToolAdapterTests(unittest.TestCase):
    def test_meeko_prepared_artifacts_require_lossless_receptor_provenance(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            ligand_tool = _executable(root, "mk_prepare_ligand.py")
            receptor_tool = _executable(root, "mk_prepare_receptor.py")
            ligand_sdf = _local_artifact(root, "ligand.sdf")
            receptor_raw = _local_artifact(root, "receptorH.pdb")
            receptor_ordered = _local_artifact(root, "receptorH_ordered.pdb")
            ligand_pdbqt = _local_artifact(root, "ligand.pdbqt")
            receptor_pdbqt = _local_artifact(root, "receptor.pdbqt")
            provenance = _meeko_provenance(
                ligand_tool, receptor_tool, ligand_sdf, receptor_raw, receptor_ordered,
                ligand_pdbqt, receptor_pdbqt)
            prepared = VinaPreparedInput(receptor_pdbqt, ligand_pdbqt, root, "meeko-run",
                (1.0, 2.0, 3.0), (20.0, 20.0, 20.0), MOLECULE.inchikey,
                TARGET.structure_artifact.id, POCKET.artifact.id, provenance)
            config = MeekoPreparationConfig(ligand_tool, receptor_tool, "0.7.1", "0.7.5")
            preparer = MeekoPreparedVinaPreparer(root, config, prepared,
                molecule_inchikey=MOLECULE.inchikey, target_identifier="1ABC",
                pocket_id="site-1")
            self.assertIs(preparer.prepare(_docking_input(None)), prepared)
            self.assertEqual(provenance[0].moved_record_count, 1)
            self.assertEqual(provenance[0].dropped_record_count, 0)
            adapter = VinaDockingAdapter(root, _executable(root, "vina"), preparer,
                                         version="1.2.7", runner=ToolRunner("vina"))
            batch = adapter.dock(_docking_input(adapter))
            self.assertEqual(batch.preparation_provenance, provenance)

            lossy = replace(provenance[0], lossless=False, dropped_record_count=1)
            with self.assertRaisesRegex(ValueError, "preserve every record"):
                MeekoPreparedVinaPreparer(root, config,
                    replace(prepared, preparation_provenance=(lossy, *provenance[1:])),
                    molecule_inchikey=MOLECULE.inchikey, target_identifier="1ABC",
                    pocket_id="site-1")

    def test_vina_adapter_uses_exact_prepared_lineage_and_splits_stable_poses(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            executable = _executable(root, "vina")
            receptor = _local_artifact(root, "receptor.pdbqt")
            ligand = _local_artifact(root, "ligand.pdbqt")
            output = root / "vina-output"
            output.mkdir()
            prepared = VinaPreparedInput(receptor, ligand, output, "run-1",
                (1.0, 2.0, 3.0), (20.0, 20.0, 20.0), MOLECULE.inchikey,
                TARGET.structure_artifact.id, POCKET.artifact.id)
            runner = ToolRunner("vina")
            preparer = BoundVinaPreparer(prepared, MOLECULE.inchikey, "1ABC", "site-1")
            adapter = VinaDockingAdapter(root, executable, preparer,
                                         version="1.2.7", runner=runner)
            result = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"),
                POCKET_REQUEST, target_provider=TargetProvider(), pocket_provider=PocketProvider(),
                docking_provider=adapter)
            self.assertEqual(result.docking.status, "completed")
            self.assertEqual([pose.score for pose in result.docking.poses], [-8.1, -7.4])
            self.assertEqual([pose.pose_id for pose in result.docking.poses],
                             ["run-1-pose-1", "run-1-pose-2"])
            self.assertEqual(result.docking.docking_input.provider, "autodock-vina")
            self.assertEqual(result.docking.docking_input.config.score_name,
                             "vina_affinity_kcal_per_mol")
            self.assertTrue(all(Path(pose.artifact.uri).read_text().startswith("MODEL")
                                for pose in result.docking.poses))
            self.assertEqual(runner.calls[0][0][0], str(executable))
            self.assertIn("--num_modes", runner.calls[0][0])
            self.assertIn("--energy_range", runner.calls[0][0])

    def test_plip_adapter_parses_selected_pose_and_rejects_lineage_mismatch(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            executable = _executable(root, "plip")
            complex_ref = _local_artifact(root, "complex.pdb")
            output = root / "plip-output"
            output.mkdir()
            pose = DockingPose("pose-2", 2, -7.4, artifact("pose-artifact-2"))
            prepared = PLIPPreparedInput(complex_ref, output, "plip-run",
                pose.artifact.id, TARGET.structure_artifact.id, "LIG:A:1")
            runner = ToolRunner("plip")
            preparer = BoundPLIPPreparer(prepared, MOLECULE.inchikey, "1ABC", "pose-2")
            adapter = PLIPInteractionAdapter(root, executable, preparer,
                                             version="2.4.0", runner=runner)
            value = _docking_input(adapter=None)
            batch = adapter.analyze(value, pose)
            self.assertEqual(batch.pose_artifact_id, "pose-artifact-2")
            self.assertEqual((batch.provider, batch.ligand_residue_identity), ("plip", "LIG:A:1"))
            self.assertIn("--nohydro", batch.command_argv)
            self.assertEqual(batch.interactions[0], InteractionEvidence(
                "hydrogen_bond", "A", "ASP25", "7", 2.8, 165.0))
            wrong = replace(prepared, source_pose_artifact_id="other-pose")
            wrong_preparer = BoundPLIPPreparer(wrong, MOLECULE.inchikey, "1ABC", "pose-2")
            mismatch = PLIPInteractionAdapter(root, executable, wrong_preparer,
                                              version="2.4.0", runner=runner)
            with self.assertRaisesRegex(ValueError, "selected pose lineage"):
                mismatch.analyze(value, pose)
            self.assertEqual(len(runner.calls), 1)

    def test_local_adapter_paths_fail_closed_and_subprocess_timeout_defaults_none(self):
        from frogent_plugin.docking_local import SubprocessCommandRunner
        self.assertIsNone(SubprocessCommandRunner().timeout)
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            executable = _executable(root, "vina")
            outside = artifact("outside")
            prepared = VinaPreparedInput(outside, outside, root, "run", (0.0, 0.0, 0.0),
                (1.0, 1.0, 1.0), MOLECULE.inchikey, TARGET.structure_artifact.id,
                POCKET.artifact.id)
            runner = ToolRunner("vina")
            preparer = BoundVinaPreparer(prepared, MOLECULE.inchikey, "1ABC", "site-1")
            adapter = VinaDockingAdapter(root, executable, preparer,
                                         version="1", runner=runner)
            with self.assertRaisesRegex(ValueError, "absolute non-symlink"):
                adapter.dock(_docking_input(adapter))
            self.assertEqual(runner.calls, [])

    def test_vina_prepared_box_must_equal_verified_pocket_geometry(self):
        from frogent_plugin.docking_types import DockingInput
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            executable = _executable(root, "vina")
            receptor = _local_artifact(root, "receptor.pdbqt")
            ligand = _local_artifact(root, "ligand.pdbqt")
            prepared = VinaPreparedInput(receptor, ligand, root, "run", (1.0, 2.0, 3.0),
                (20.0, 20.0, 20.0), MOLECULE.inchikey, TARGET.structure_artifact.id,
                POCKET.artifact.id)
            runner = ToolRunner("vina")
            adapter = VinaDockingAdapter(root, executable,
                BoundVinaPreparer(prepared, MOLECULE.inchikey, "1ABC", "site-1"),
                version="1.2.7", runner=runner)
            pocket = replace(POCKET, box=PocketGeometry((1.0, 2.0, 3.0),
                             (18.0, 18.0, 18.0), "angstrom", "verified_residue_box", 5.0))
            with self.assertRaisesRegex(ValueError, "verified pocket geometry"):
                adapter.dock(DockingInput(MOLECULE, TARGET, pocket, adapter.default_config,
                                          adapter.provider_id, adapter.provider_version))
            self.assertEqual(runner.calls, [])


class DockingChatTests(unittest.TestCase):
    def handler(self, value=None, *, plip=None, docking=None):
        planner = CodexDockingPlanner(StructuredClient(value or planner_value()))
        return DockingChatHandler(planner, Resolver(), target_provider=TargetProvider(),
            pocket_provider=PocketProvider(), docking_provider=docking or DockProvider(),
            interaction_provider=plip or PLIPProvider())

    def test_chat_uses_configured_vina_provider_defaults(self):
        class VinaShapedProvider(DockProvider):
            provider_id = "autodock-vina"
            provider_version = "1.2.7"
            default_config = DockingConfig(pose_count=9,
                score_name="vina_affinity_kcal_per_mol", exhaustiveness=8, cpu=4,
                seed=20260719, energy_range=10.0)

            def dock(self, value):
                self.calls.append(value)
                pose = DockingPose("pose-1", 1, -13.2, artifact("pose-artifact-1"))
                return DockingBatch(value.molecule.canonical_isomeric_smiles,
                    value.molecule.inchikey, value.target.identifier, value.pocket.pocket_id,
                    self.provider_id, self.provider_version, value.config.score_name,
                    value.config.score_direction, (pose,))

        provider = VinaShapedProvider()
        result = self.handler(docking=provider).run(
            MESSAGE, ExecutionContext("u", "c", "j", ROOT.resolve()))
        config = provider.calls[0].config
        self.assertEqual((config.score_name, config.pose_count, config.exhaustiveness,
                          config.cpu, config.seed, config.energy_range),
                         ("vina_affinity_kcal_per_mol", 9, 8, 4, 20260719, 10.0))
        event = next(item for item in result.events if item.payload.get("capability_id") ==
                     "docking.generate-conformation")
        self.assertEqual(event.payload["config"]["energy_range"], 10.0)

    def test_native_plan_requires_exact_user_spans(self):
        client = StructuredClient(planner_value())
        plan = CodexDockingPlanner(client).plan(MESSAGE)
        self.assertEqual(plan.target, TargetRequest("pdb", "1ABC", "A"))
        self.assertEqual(plan.pocket.residues, ("ASP25", "GLY27"))
        self.assertFalse(client.calls[0][3]["additionalProperties"])
        with self.assertRaisesRegex(ValueError, "exact user-text span"):
            CodexDockingPlanner(StructuredClient(planner_value(target_value="2XYZ"))).plan(MESSAGE)

    def test_native_plan_requires_one_exact_pose_id_or_rank_evidence(self):
        message = ("Dock CCO to 1ABC chain A using site-1 ASP25 GLY27; "
                   "select pose rank 1 for PLIP")
        value = planner_value(selected_pose_id="", selected_pose_rank=1,
                              pose_selection_text="select pose rank 1 for PLIP")
        plan = CodexDockingPlanner(StructuredClient(value)).plan(message)
        self.assertEqual((plan.selected_pose_rank, plan.selected_pose_id), (1, ""))
        for mutation, expected in (
            ({"selected_pose_rank": 0, "pose_selection_text": ""}, "exactly one"),
            ({"selected_pose_id": "pose-2", "selected_pose_rank": 1}, "exactly one"),
            ({"pose_selection_text": ""}, "current-message evidence"),
            ({"pose_selection_text": "select pose rank 2 for PLIP"}, "current-message evidence"),
        ):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, expected):
                CodexDockingPlanner(StructuredClient({**value, **mutation})).plan(message)

    def test_native_plan_requires_exact_ligand_state_and_receptor_ph_evidence(self):
        message = (MESSAGE + "; select microstate-abc and receptor pH 7.4")
        value = planner_value(selected_microstate_id="microstate-abc",
            microstate_selection_text="select microstate-abc", receptor_ph=7.4,
            receptor_state_text="receptor pH 7.4")
        plan = CodexDockingPlanner(StructuredClient(value)).plan(message)
        self.assertEqual((plan.selected_microstate_id, plan.receptor_ph),
                         ("microstate-abc", 7.4))
        for mutation in ({"microstate_selection_text": ""},
                         {"receptor_state_text": ""},
                         {"selected_microstate_smiles": "CCO"}):
            with self.assertRaises(ValueError):
                CodexDockingPlanner(StructuredClient({**value, **mutation})).plan(message)
        for literal, expected in (("pH 7", 7.0), ("pH 7.0", 7.0),
                                  ("酸碱度 7.40", 7.4)):
            current = MESSAGE + "; receptor " + literal
            planned = planner_value(receptor_ph=expected, receptor_state_text=literal)
            self.assertEqual(CodexDockingPlanner(StructuredClient(planned)).plan(
                current).receptor_ph, expected)
        with self.assertRaisesRegex(ValueError, "current-message evidence"):
            CodexDockingPlanner(StructuredClient(planner_value(
                receptor_ph=7.4, receptor_state_text="dose 7.4"))).plan(MESSAGE + "; dose 7.4")

    def test_microstate_selection_response_is_actionable_and_second_turn_executes_once(self):
        state = LigandMicrostate("microstate-abc", "protomer-1", "CC[OH2+]",
            "STATE-KEY", 1, "SOURCE", 7.0, 7.8, 0.5, "dimorphite-dl", "2.0.2",
            "fake-tautomer", "1", MOLECULE.inchikey, artifact("state-manifest"))
        class States:
            def __init__(self): self.calls = 0
            def enumerate(self, binding): self.calls += 1; return (state,)
        class StateDock(DockProvider):
            def dock(self, value):
                batch = super().dock(value)
                return replace(batch, state_lineage=state_lineage(value))
        states, dock = States(), StateDock()
        first = DockingChatHandler(CodexDockingPlanner(StructuredClient(planner_value(
            operation="dock", selected_pose_id="", pose_selection_text=""))), Resolver(),
            target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=dock, microstate_provider=states).run(
                MESSAGE, ExecutionContext("u", "c", "first", ROOT.resolve()))
        self.assertIn("microstate-abc | CC[OH2+] | charge=1 | pH=7-7.8", first.answer)
        self.assertIn(f"scope=full; SMILES=CCO; InChIKey={MOLECULE.inchikey}", first.answer)
        self.assertEqual(dock.calls, [])
        second_message = MESSAGE + "; select microstate-abc"
        second_plan = planner_value(operation="dock", selected_pose_id="",
            pose_selection_text="", selected_microstate_id="microstate-abc",
            microstate_selection_text="select microstate-abc")
        second = DockingChatHandler(CodexDockingPlanner(StructuredClient(second_plan)), Resolver(),
            target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=dock, microstate_provider=states).run(
                second_message, ExecutionContext("u", "c", "second", ROOT.resolve()))
        self.assertEqual(second.workflow.docking.status, "completed")
        self.assertEqual(len(dock.calls), 1)
        self.assertEqual(second.workflow.docking.state_lineage.ligand_state_id,
                         "microstate-abc")
        wrong = DockingChatHandler(CodexDockingPlanner(StructuredClient(second_plan)), Resolver(),
            target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=DockProvider(), microstate_provider=states).run(
                second_message, ExecutionContext("u", "c", "wrong", ROOT.resolve()))
        self.assertEqual(wrong.workflow.docking.status, "failed")
        self.assertIn("state lineage", wrong.workflow.coverage_gaps[-1])

    def test_receptor_configured_ph_mismatch_is_zero_tool_call(self):
        class ReceptorProvider:
            config = type("Config", (), {"settings": ReceptorStateSettings(7.4)})()
            def __init__(self): self.calls = 0
            def prepare(self, target, pocket): self.calls += 1; raise AssertionError("called")
        receptor, dock = ReceptorProvider(), DockProvider()
        result = run_docking_workflow(MOLECULE, TargetRequest("pdb", "1ABC", "A"),
            POCKET_REQUEST, target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=dock, receptor_state_provider=receptor, receptor_ph=6.5)
        self.assertEqual((receptor.calls, dock.calls), (0, []))
        self.assertIn("configured receptor state pH", result.coverage_gaps[-1])

    def test_state_tool_failure_does_not_surface_raw_stderr(self):
        class FailingStates:
            def enumerate(self, binding): raise RuntimeError("Dimorphite exited 7")
        handler = DockingChatHandler(CodexDockingPlanner(StructuredClient(planner_value())),
            Resolver(), target_provider=TargetProvider(), pocket_provider=PocketProvider(),
            docking_provider=DockProvider(), microstate_provider=FailingStates())
        result = handler.run(MESSAGE, ExecutionContext("u", "c", "j", ROOT.resolve()))
        serialized = result.answer + json.dumps([item.payload for item in result.events])
        self.assertIn("Dimorphite exited 7", serialized)
        self.assertNotIn("SECRET_SENTINEL", serialized)

    def test_native_plan_binds_exact_reference_ligand_identity(self):
        message = "Dock CCO to 1ABC chain A using pocket-site STI:A:999"
        value = planner_value(operation="dock", pocket_id="pocket-site",
            pocket_kind="reference_ligand", residue_ids=[], reference_ligand="STI:A:999",
            pocket_text="pocket-site STI:A:999", selected_pose_id="",
            selected_pose_rank=0, pose_selection_text="")
        plan = CodexDockingPlanner(StructuredClient(value)).plan(message)
        self.assertEqual(plan.pocket.reference_ligand, "STI:A:999")
        self.assertEqual(plan.pocket.source_kind, "reference_ligand")
        with self.assertRaisesRegex(ValueError, "exact user-text span"):
            CodexDockingPlanner(StructuredClient({**value,
                "reference_ligand": "ATP:A:999"})).plan(message)

    def test_chat_answer_and_events_preserve_evidence_boundaries(self):
        result = self.handler().run(MESSAGE, ExecutionContext("u", "c", "j", ROOT.resolve()))
        self.assertIn("pose pose-2", result.answer)
        self.assertIn("experimental_evidence=false", result.answer)
        self.assertIn("No binding affinity", result.answer)
        capabilities = [event.payload.get("capability_id") for event in result.events]
        self.assertIn("target.standardize", capabilities)
        self.assertIn("pocket.prepare", capabilities)
        self.assertIn("docking.generate-conformation", capabilities)
        self.assertIn("sar.analyze", capabilities)

    def test_chat_rank_policy_reports_requested_and_resolved_dynamic_pose(self):
        message = ("Dock CCO to 1ABC chain A using site-1 ASP25 GLY27; "
                   "select pose rank 1 for PLIP")
        plan = planner_value(selected_pose_id="", selected_pose_rank=1,
                             pose_selection_text="select pose rank 1 for PLIP")
        result = self.handler(plan).run(message,
            ExecutionContext("u", "c", "j", ROOT.resolve()))
        event = next(item for item in result.events
                     if item.payload.get("capability_id") == "sar.analyze")
        self.assertEqual((event.payload["requested_pose_rank"],
                          event.payload["resolved_pose_rank"], event.payload["pose_id"]),
                         (1, 1, "pose-1"))
        self.assertIn("requested_rank=1; resolved_rank=1; resolved_pose=pose-1", result.answer)

    def test_english_chinese_routing_and_research_protection(self):
        self.assertTrue(is_clear_docking_intent("Run docking for ligand CCO at PDB 1ABC"))
        self.assertTrue(is_clear_docking_intent("请运行分子对接并分析相互作用"))
        self.assertFalse(is_clear_docking_intent("Find literature about molecular docking"))
        self.assertFalse(is_clear_docking_intent("检索分子对接论文"))
        self.assertFalse(is_clear_docking_intent("This compound has a docking score"))

    def test_service_sse_and_memory_failure_keep_completed_docking(self):
        class Null:
            def load(self, *args): return None
        class FailingMemory:
            def ingest_session(self, *args): raise RuntimeError("sqlite unavailable")
        service = ResearchService(None, None, Null(), ROOT, memory_store=FailingMemory(),
                                  docking_handler=self.handler())
        frames = list(service.stream_payload("u", {"chat_id": "c", "message": MESSAGE,
                                                    "mode": "docking"}))
        payloads = [json.loads(item[6:]) for item in frames if item.startswith("data: {")]
        self.assertEqual(payloads[0]["name"], "docking")
        self.assertIn("pose pose-2", payloads[0]["content"])
        self.assertIn("memory persistence failed", payloads[0]["content"])
        self.assertTrue(payloads[1]["stop"])
        self.assertEqual(frames[-1], "data: [DONE]\n\n")
        events = service.typed_events[("u", "c")]
        self.assertEqual(sum(event.kind == "tool.completed" and
                         event.payload.get("capability_id") == "docking.generate-conformation"
                         for event in events), 1)
        self.assertTrue(any(event.kind == "error" and
                            event.payload.get("stage") == "memory_persistence" for event in events))


class ToolRunner:
    def __init__(self, kind): self.kind, self.calls = kind, []
    def run(self, argv, cwd):
        self.calls.append((argv, cwd))
        if self.kind == "vina":
            output = Path(argv[argv.index("--out") + 1])
            output.write_text("MODEL 1\nREMARK VINA RESULT: -8.1 0.0 0.0\nENDMDL\n"
                              "MODEL 2\nREMARK VINA RESULT: -7.4 1.0 2.0\nENDMDL\n")
        else:
            (cwd / "complex_report.xml").write_text(_PLIP_XML)
        return CommandResult(0, "", "")


def _executable(root, name):
    value = root / name
    value.write_text("fake executable\n")
    value.chmod(0o700)
    return value


def _local_artifact(root, name):
    value = root / name
    value.write_text("artifact\n")
    return ArtifactRef(name, name, "chemical/x-pdbqt", str(value))


def _meeko_provenance(ligand_tool, receptor_tool, ligand_sdf, receptor_raw,
                      receptor_ordered, ligand_pdbqt, receptor_pdbqt):
    normalize = PreparationProvenance("gemmi-lossless-pdb-normalizer", "0.7.5",
        (receptor_raw,), (receptor_ordered,),
        ("move-record", "SER A:438 HB2", str(receptor_raw), str(receptor_ordered)),
        "lossless_receptor_normalization", True, moved_record_count=1)
    ligand = PreparationProvenance("meeko-ligand", "0.7.1", (ligand_sdf,),
        (ligand_pdbqt,), (str(ligand_tool), "-i", ligand_sdf.uri, "-o", ligand_pdbqt.uri),
        "meeko_ligand_preparation", True)
    receptor = PreparationProvenance("meeko-receptor", "0.7.1", (receptor_ordered,),
        (receptor_pdbqt,), (str(receptor_tool), "--read_pdb", receptor_ordered.uri,
        "-o", receptor_pdbqt.uri), "meeko_receptor_preparation", True)
    return normalize, ligand, receptor


def _docking_input(adapter):
    from frogent_plugin.docking_types import DockingInput
    provider = adapter.provider_id if adapter else "autodock-vina"
    version = adapter.provider_version if adapter else "1.2.7"
    config = getattr(adapter, "default_config", DockingConfig())
    return DockingInput(MOLECULE, TARGET, POCKET, config, provider, version)


_PLIP_XML = """<report><bindingsite><identifiers><hetid>LIG</hetid><chain>A</chain>
<position>1</position></identifiers><interactions><hydrogen_bonds><hydrogen_bond>
<reschain>A</reschain><restype>ASP</restype><resnr>25</resnr><ligatomidx>7</ligatomidx>
<dist_h-a>2.8</dist_h-a><don_angle>165.0</don_angle>
</hydrogen_bond></hydrogen_bonds></interactions></bindingsite></report>"""


if __name__ == "__main__":
    unittest.main()
