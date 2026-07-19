import math
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frogent_plugin.contracts import ArtifactRef  # noqa: E402
from frogent_plugin.docking_execution import run_docking_workflow  # noqa: E402
from frogent_plugin.docking_local import CommandResult  # noqa: E402
from frogent_plugin.docking_pose_complex import (  # noqa: E402
    PoseLigand, RDKitPoseLigandBuilder, _hydrogen_record,
)
from frogent_plugin.docking_types import (  # noqa: E402
    DockingBatch, DockingConfig, DockingInput, DockingPose, PocketBinding,
    PocketRequest, TargetRequest, VerifiedTargetIdentity,
)
from frogent_plugin.dynamic_plip import DynamicPLIPConfig, DynamicPLIPInputPreparer  # noqa: E402
from frogent_plugin.molecular_binding import MolecularInputBinding  # noqa: E402
from frogent_plugin.pocket_geometry import PocketGeometry  # noqa: E402
from frogent_plugin.research_factory import RuntimeConfig, build_research_service  # noqa: E402
from frogent_plugin.vina_plip_adapters import PLIPInteractionAdapter  # noqa: E402


KEY = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"


class FakeLigandBuilder:
    tool, version = "fake-pose-builder", "7"

    def __init__(self): self.calls = []
    def build(self, path, binding, **values):
        self.calls.append((path, binding, values))
        start = values["serial_start"]
        record = _atom("HETATM", start, "C1", "LIG", "Z", 1, 1, 2, 3)
        return PoseLigand((record,), (), binding.canonical_isomeric_smiles,
                          binding.inchikey, 1)


class PLIPRunner:
    def __init__(self, fail=False): self.calls, self.fail = [], fail
    def run(self, argv, cwd):
        self.calls.append((argv, cwd))
        if self.fail:
            return CommandResult(2, "", "synthetic PLIP failure")
        (cwd / "complex_report.xml").write_text(_PLIP_XML)
        return CommandResult(0, "", "")


class DockProvider:
    provider_id, provider_version = "fresh-vina", "1.2.7"
    default_config = DockingConfig(pose_count=3, score_name="vina_affinity_kcal_per_mol")

    def __init__(self): self.calls = []
    def dock(self, value):
        self.calls.append(value)
        poses = tuple(_pose(Path(value.target.structure_artifact.uri).parent, rank,
                            f"fresh-run-pose-{rank}") for rank in (1, 2))
        return DockingBatch(value.molecule.canonical_isomeric_smiles, value.molecule.inchikey,
            value.target.identifier, value.pocket.pocket_id, self.provider_id,
            self.provider_version, value.config.score_name, value.config.score_direction, poses)


class DynamicPLIPTests(unittest.TestCase):
    def test_rank_resolves_fresh_pose_and_dynamic_complex_preserves_lineage(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            value, request = _input(root)
            config, builder, runner = _config(root), FakeLigandBuilder(), PLIPRunner()
            preparer = DynamicPLIPInputPreparer(root, config, ligand_builder=builder,
                run_id_factory=lambda: "dynamic-plip-run-0001")
            plip = PLIPInteractionAdapter(root, config.executable, preparer,
                                          version=config.version, runner=runner)
            dock = DockProvider()
            result = run_docking_workflow(value.molecule, TargetRequest("pdb", "1ABC", "A"),
                request, target_provider=_Target(value.target), pocket_provider=_Pocket(value.pocket),
                docking_provider=dock, interaction_provider=plip, want_interactions=True,
                selected_pose_rank=1)
            item = result.interaction
            self.assertEqual((item.status, item.requested_pose_rank, item.pose_rank, item.pose_id),
                             ("completed", 1, 1, "fresh-run-pose-1"))
            self.assertEqual(len(dock.calls), 1)
            self.assertEqual(builder.calls[0][2]["pose_rank"], 1)
            self.assertEqual(item.ligand_residue_identity, "LIG:Z:1")
            self.assertEqual(item.interactions[0].protein_residue, "ASP25")
            provenance = item.preparation_provenance[0]
            self.assertEqual([entry.id for entry in provenance.source_artifacts],
                             [value.target.structure_artifact.id,
                              value.pocket.artifact.id, "fresh-run-pose-1"])
            complex_path = Path(provenance.output_artifacts[0].uri)
            text = complex_path.read_text()
            self.assertLess(text.index(" GLY A"), text.index(" LIG Z"))
            self.assertNotIn(" STI A 999", text)

    def test_ligand_serials_follow_max_noncontiguous_receptor_serial(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            value, _ = _input(root, polymer_serials=(120, 900))
            builder, config = FakeLigandBuilder(), _config(root)
            prepared = DynamicPLIPInputPreparer(root, config, ligand_builder=builder,
                run_id_factory=lambda: "dynamic-plip-serials").prepare(
                    value, _pose(root, 1, "serial-pose"))
            self.assertEqual(builder.calls[0][2]["serial_start"], 901)
            serials = [int(line[6:11]) for line in Path(prepared.complex_artifact.uri)
                       .read_text().splitlines() if line.startswith(("ATOM", "HETATM"))]
            self.assertEqual(serials, [120, 900, 901])
            self.assertEqual(len(serials), len(set(serials)))

    def test_rank_selection_bounds_missing_provider_and_plip_failure_are_local(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            value, request = _input(root)
            dock = DockProvider()
            missing = run_docking_workflow(value.molecule, TargetRequest("pdb", "1ABC", "A"),
                request, target_provider=_Target(value.target), pocket_provider=_Pocket(value.pocket),
                docking_provider=dock, want_interactions=True, selected_pose_rank=1)
            absent = run_docking_workflow(value.molecule, TargetRequest("pdb", "1ABC", "A"),
                request, target_provider=_Target(value.target), pocket_provider=_Pocket(value.pocket),
                docking_provider=dock, want_interactions=True, selected_pose_rank=3)
            both = run_docking_workflow(value.molecule, TargetRequest("pdb", "1ABC", "A"),
                request, target_provider=_Target(value.target), pocket_provider=_Pocket(value.pocket),
                docking_provider=dock, interaction_provider=object(), want_interactions=True,
                selected_pose_id="fresh-run-pose-1", selected_pose_rank=1)
            config, runner = _config(root), PLIPRunner(True)
            plip = PLIPInteractionAdapter(root, config.executable,
                DynamicPLIPInputPreparer(root, config, ligand_builder=FakeLigandBuilder(),
                    run_id_factory=lambda: "dynamic-plip-run-0002"),
                version=config.version, runner=runner)
            failed = run_docking_workflow(value.molecule, TargetRequest("pdb", "1ABC", "A"),
                request, target_provider=_Target(value.target), pocket_provider=_Pocket(value.pocket),
                docking_provider=dock, interaction_provider=plip, want_interactions=True,
                selected_pose_rank=1)
            self.assertEqual((missing.interaction.status, absent.interaction.status,
                              both.interaction.status, failed.interaction.status),
                             ("blocked", "blocked", "blocked", "failed"))
            self.assertTrue(all(item.docking.status == "completed"
                                for item in (missing, absent, both, failed)))
            self.assertEqual(len(runner.calls), 1)

    def test_dynamic_preparer_rejects_lineage_escape_and_reuse(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            value, _ = _input(root)
            config = _config(root)
            cases = (
                replace(value, pocket=replace(value.pocket, target_artifact_id="wrong")),
                replace(value, target=replace(value.target, chains=("A", "Z"))),
                replace(value, target=replace(value.target, kind="uniprot")),
            )
            for index, item in enumerate(cases):
                builder = FakeLigandBuilder()
                preparer = DynamicPLIPInputPreparer(root, config, ligand_builder=builder,
                    run_id_factory=lambda index=index: f"dynamic-plip-bad-{index:04d}")
                with self.assertRaises((ValueError, FileNotFoundError)):
                    preparer.prepare(item, _pose(root, 1, f"bad-pose-{index}"))
            outside = ArtifactRef("outside", ".env.example", "chemical/x-pdbqt",
                                  str(ROOT / ".env.example"))
            preparer = DynamicPLIPInputPreparer(root, config, ligand_builder=FakeLigandBuilder(),
                run_id_factory=lambda: "dynamic-plip-escape")
            with self.assertRaises((ValueError, FileNotFoundError)):
                preparer.prepare(value, DockingPose("outside", 1, -1.0, outside))
            linked = root / "linked-pose.pdbqt"
            linked.symlink_to(ROOT / ".env.example")
            linked_ref = ArtifactRef("linked", linked.name, "chemical/x-pdbqt", str(linked))
            with self.assertRaises(ValueError):
                preparer.prepare(value, DockingPose("linked", 1, -1.0, linked_ref))
            pocket_path = Path(value.pocket.artifact.uri)
            pocket_path.write_text(pocket_path.read_text().replace(
                '"center":[1.0,2.0,3.0]', '"center":[9.0,2.0,3.0]'))
            with self.assertRaisesRegex(ValueError, "geometry"):
                DynamicPLIPInputPreparer(root, config, ligand_builder=FakeLigandBuilder(),
                    run_id_factory=lambda: "dynamic-plip-tamper").prepare(
                        value, _pose(root, 1, "tampered-pocket-pose"))
            value, _ = _input(root)
            pose = _pose(root, 1, "reused-pose")
            preparer = DynamicPLIPInputPreparer(root, config, ligand_builder=FakeLigandBuilder(),
                run_id_factory=lambda: "dynamic-plip-reused")
            preparer.prepare(value, pose)
            with self.assertRaises(FileExistsError):
                preparer.prepare(value, pose)

    def test_rdkit_pose_parser_fails_closed_on_identity_mapping_and_geometry(self):
        try:
            import rdkit  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("RDKit is optional outside the app runtime")
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            builder = RDKitPoseLigandBuilder()
            binding = MolecularInputBinding("full", "CCO", KEY, True)
            valid = _pose(root, 1, "rdkit-valid")
            result = builder.build(Path(valid.artifact.uri), binding, pose_rank=1,
                serial_start=10, residue_name="LIG", chain="Z", residue_number=1)
            self.assertEqual((result.inchikey, result.heavy_atom_count), (KEY, 3))
            hydrogen = root / "hydrogen.pdbqt"
            hydrogen.write_text(_pose_text("CCO").replace(
                "ENDMDL", "REMARK H PARENT 3 4\n"
                + _atom("ATOM", 4, "H4", "UNL", " ", 1, 4, 5, 6) + "\nENDMDL"))
            hydrated = builder.build(hydrogen, binding, pose_rank=1, serial_start=10,
                residue_name="LIG", chain="Z", residue_number=1)
            self.assertTrue(any(" H1 " in line for line in hydrated.pdb_records))
            self.assertIn("CONECT   12   13", hydrated.conect_records)
            with self.assertRaisesRegex(ValueError, "serial exceeds"):
                builder.build(hydrogen, binding, pose_rank=1, serial_start=99997,
                    residue_name="LIG", chain="Z", residue_number=1)
            with self.assertRaisesRegex(ValueError, "name exceeds"):
                _hydrogen_record(20, ("H", (1.0, 2.0, 3.0)), "LIG", "Z", 1, 1000)
            mutations = {
                "identity": _pose_text("CCN"),
                "bad-index": _pose_text("CCO", index="1 1 1 2 3 3"),
                "out-of-range-index": _pose_text("CCO", index="1 1 2 2 4 3"),
                "missing": _pose_text("CCO", atoms=2),
                "duplicate-atom": _pose_text("CCO").replace(
                    "ENDMDL", _atom("ATOM", 1, "C1", "UNL", " ", 1, 1, 2, 3)
                    + "\nENDMDL"),
                "nonfinite": _pose_text("CCO").replace("   2.000", "     nan", 1),
                "models": _pose_text("CCO") + _pose_text("CCO").replace("MODEL 1", "MODEL 2"),
            }
            for name, text in mutations.items():
                path = root / f"{name}.pdbqt"
                path.write_text(text)
                with self.subTest(name=name), self.assertRaises(ValueError):
                    builder.build(path, binding, pose_rank=1, serial_start=10,
                                  residue_name="LIG", chain="Z", residue_number=1)

    def test_factory_requires_explicit_project_plip_config(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            value, _ = _input(root)
            config, runner, builder = _config(root), PLIPRunner(), FakeLigandBuilder()
            service = build_research_service(RuntimeConfig(root, root / "memory.sqlite3",
                dynamic_plip=config), runner=lambda *args, **kwargs: None,
                plip_runner=runner, plip_ligand_builder=builder)
            provider = service.docking_handler.interaction_provider
            self.assertIsInstance(provider, PLIPInteractionAdapter)
            batch = provider.analyze(value, _pose(root, 1, "factory-pose"))
            self.assertEqual((batch.provider, batch.ligand_residue_identity), ("plip", "LIG:Z:1"))
            no_config = build_research_service(RuntimeConfig(root, root / "memory-2.sqlite3"),
                                               runner=lambda *args, **kwargs: None)
            self.assertIsNone(no_config.docking_handler.interaction_provider)
            with patch.dict("os.environ", {"FROGENT_MEMORY_DB": "memory-3.sqlite3",
                    "FROGENT_PLIP_EXECUTABLE": str(config.executable),
                    "FROGENT_PLIP_VERSION": "3.0.0"}, clear=True):
                loaded = RuntimeConfig.from_env(root)
            self.assertEqual((loaded.dynamic_plip.executable, loaded.dynamic_plip.version),
                             (config.executable, "3.0.0"))


class _Target:
    def __init__(self, value): self.value = value
    def resolve(self, request): return self.value


class _Pocket:
    def __init__(self, value): self.value = value
    def resolve(self, target, request): return self.value


def _config(root):
    executable = root / "plip"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    return DynamicPLIPConfig(executable, root / "plip-runs", "3.0.0")


def _input(root, polymer_serials=(1, 2)):
    pdb = root / "1ABC.pdb"
    pdb.write_text("\n".join((_header("1ABC"),
        _atom("ATOM", polymer_serials[0], "N", "GLY", "A", 1, 0, 0, 0),
        _atom("ATOM", polymer_serials[1], "CA", "GLY", "A", 1, 1, 0, 0),
        _atom("HETATM", 3, "C1", "STI", "A", 999, 1, 2, 3), "END")) + "\n")
    pocket_path = root / "site.json"
    target_ref = ArtifactRef("target-1abc", pdb.name, "chemical/x-pdb", str(pdb))
    pocket_ref = ArtifactRef("pocket-site", pocket_path.name, "application/json",
                             str(pocket_path))
    target = VerifiedTargetIdentity("pdb", "1ABC", ("A",), target_ref,
        "rcsb-pdb", "test", "1ABC", "https://metadata", "https://coordinates")
    pocket_path.write_text('{"center":[1.0,2.0,3.0],"chain":"A","margin":5.0,'
        '"method":"verified_reference_ligand_bounding_box",'
        '"numbering_scheme":"pdb_auth","pocket_id":"site",'
        '"reference_ligand":"STI:A:999","residues":[],"schema_version":"pocket-v1",'
        '"size":[10.0,10.0,10.0],"source_kind":"reference_ligand",'
        '"target_artifact_id":"target-1abc","target_identifier":"1ABC",'
        '"units":"angstrom"}\n')
    pocket = PocketBinding("site", "1ABC", "A", "pdb_auth", "reference_ligand", (),
        pocket_ref, "rcsb-pdb-pocket", "test", target_ref.id, "STI:A:999",
        PocketGeometry((1.0, 2.0, 3.0), (10.0, 10.0, 10.0), "angstrom",
                       "verified_reference_ligand_bounding_box", 5.0))
    value = DockingInput(MolecularInputBinding("full", "CCO", KEY, True), target, pocket,
        DockingConfig(score_name="vina_affinity_kcal_per_mol"), "fresh-vina", "1.2.7")
    request = PocketRequest("site", "A", "pdb_auth", "reference_ligand",
                            reference_ligand="STI:A:999")
    return value, request


def _pose(root, rank, identity):
    path = root / f"{identity}.pdbqt"
    if not path.exists():
        path.write_text(_pose_text("CCO", rank=rank))
    ref = ArtifactRef(identity, path.name, "chemical/x-pdbqt", str(path))
    return DockingPose(identity, rank, -8.0 + rank, ref)


def _pose_text(smiles, *, rank=1, index="1 1 2 2 3 3", atoms=3):
    values = [f"MODEL {rank}", "REMARK VINA RESULT: -8.0 0 0",
              f"REMARK SMILES {smiles}", f"REMARK SMILES IDX {index}"]
    names = ("C1", "C2", "O3")
    values.extend(_atom("ATOM", item, names[item - 1], "UNL", " ", 1,
                        item, item + 1, item + 2) for item in range(1, atoms + 1))
    return "\n".join((*values, "ENDMDL")) + "\n"


def _header(entry): return "HEADER" + " " * 56 + entry


def _atom(record, serial, atom, residue, chain, number, x, y, z):
    return (f"{record:<6}{serial:>5} {atom:^4} {residue:>3} {chain}{number:>4}    "
            f"{x:>8.3f}{y:>8.3f}{z:>8.3f}  1.00 20.00           C")


_PLIP_XML = """<report><bindingsite><identifiers><hetid>LIG</hetid><chain>Z</chain>
<position>1</position></identifiers><interactions><hydrogen_bonds><hydrogen_bond>
<reschain>A</reschain><restype>ASP</restype><resnr>25</resnr><ligatomidx>7</ligatomidx>
<dist_h-a>2.8</dist_h-a><don_angle>165.0</don_angle>
</hydrogen_bond></hydrogen_bonds></interactions></bindingsite></report>"""


if __name__ == "__main__":
    unittest.main()
