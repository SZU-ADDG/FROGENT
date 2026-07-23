import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.core.contracts import ArtifactRef  # noqa: E402
from agent.app.conversation_memory import ConversationMemoryStore  # noqa: E402
from agent.docking.docking_chat import DockingChatHandler, is_clear_docking_intent  # noqa: E402
from agent.docking.docking_chat_plan import DockingChatPlan  # noqa: E402
from agent.docking.docking_types import (  # noqa: E402
    DockingBatch, DockingConfig, DockingPose, PocketRequest, TargetRequest,
)
from agent.molecular.molecular_identity import MolecularIdentity  # noqa: E402
from agent.molecular.pubchem_identity import PubChemResolution  # noqa: E402
from agent.docking.rcsb_pocket import RCSBPocketProvider  # noqa: E402
from agent.docking.rcsb_target import RCSBTargetProvider  # noqa: E402
from agent.app.research_factory import RuntimeConfig, build_research_service  # noqa: E402
from agent.app.research_service import ResearchService  # noqa: E402


class FakeTransport:
    def __init__(self, entry=None, entity=None, coordinates=None):
        self.entry = entry or _entry()
        self.entity = entity or _entity()
        self.coordinates = coordinates or _pdb()
        self.calls = []

    def get(self, url, params, headers={}):
        self.calls.append((url, dict(params), dict(headers)))
        if "/entry/" in url:
            return json.dumps(self.entry).encode()
        if "/polymer_entity/" in url:
            return json.dumps(self.entity).encode()
        if url.endswith(".pdb"):
            return self.coordinates
        raise AssertionError(url)


class DockProvider:
    provider_id = "autodock-vina"
    provider_version = "1.2.7"
    default_config = DockingConfig(score_name="vina_affinity_kcal_per_mol")

    def __init__(self): self.calls = []

    def dock(self, value):
        self.calls.append(value)
        pose = DockingPose("pose-1", 1, -9.0,
                           ArtifactRef("pose-1", "pose.pdbqt", "chemical/x-pdbqt",
                                       "memory://pose-1"))
        return DockingBatch(value.molecule.canonical_isomeric_smiles, value.molecule.inchikey,
            value.target.identifier, value.pocket.pocket_id, self.provider_id,
            self.provider_version, value.config.score_name, value.config.score_direction, (pose,))


class Planner:
    def __init__(self, pocket): self.pocket = pocket
    def plan(self, message):
        return DockingChatPlan("dock", "smiles", "CCO", None, "",
                               TargetRequest("pdb", "1IEP", "A"), self.pocket, "", None, "")


class Normalizer:
    def normalize(self, value):
        return MolecularIdentity(value, "CCO", "CCO", "InChI=1S/C2H6O",
            "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", "C2H6O", 46.0, 0, 3, 1, 1,
            "single", False, 0, 0, "none")


class Resolver:
    normalizer = Normalizer()
    def resolve_binding(self, binding):
        return PubChemResolution(None, None, (), ("PubChem unavailable in fake",))


class NullStore:
    def load(self, *args): return None


class Runner:
    def run(self, *args, **kwargs): raise AssertionError("Codex must not run during factory wiring")


class RCSBTargetPocketTests(unittest.TestCase):
    def test_exact_target_residue_and_reference_ligand_pockets_are_persisted(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            transport = FakeTransport()
            target = RCSBTargetProvider(root, transport=transport).resolve(
                TargetRequest("pdb", "1iep", "A"))
            self.assertEqual((target.identifier, target.chains), ("1IEP", ("A",)))
            self.assertTrue(Path(target.structure_artifact.uri).is_file())
            self.assertIn("/entry/1IEP", target.metadata_url)
            self.assertTrue(target.coordinate_url.endswith("/1IEP.pdb"))
            self.assertEqual([item[0] for item in transport.calls], [
                "https://data.rcsb.org/rest/v1/core/entry/1IEP",
                "https://data.rcsb.org/rest/v1/core/polymer_entity/1IEP/1",
                "https://files.rcsb.org/download/1IEP.pdb"])
            self.assertTrue(all(item[1] == {} for item in transport.calls))
            self.assertIsNone(RCSBTargetProvider(root).transport.timeout)

            provider = RCSBPocketProvider(root, margin=5.0)
            residues = provider.resolve(target, PocketRequest(
                "residue-site", "A", "pdb_auth", "residues", ("MET318", "ASP381")))
            ligand = provider.resolve(target, PocketRequest(
                "sti-site", "A", "pdb_auth", "reference_ligand",
                reference_ligand="STI:A:999"))
            self.assertEqual(ligand.box.center, (11.0, 22.0, 33.0))
            self.assertEqual(ligand.box.size, (12.0, 14.0, 16.0))
            self.assertEqual((ligand.box.units, ligand.box.margin), ("angstrom", 5.0))
            self.assertEqual(ligand.target_artifact_id, target.structure_artifact.id)
            self.assertEqual(ligand.reference_ligand, "STI:A:999")
            self.assertTrue(Path(residues.artifact.uri).is_file())
            manifest = json.loads(Path(ligand.artifact.uri).read_text())
            self.assertEqual(manifest["target_artifact_id"], "rcsb-pdb-1IEP")
            self.assertEqual(manifest["method"], "verified_reference_ligand_bounding_box")

    def test_reference_ligand_multichain_contact_blocks_one_chain_pocket(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            coordinates = _pdb().decode().replace("END\n", _atom(
                "ATOM", 6, "CA", "GLY", "B", 10, 10.5, 20.5, 30.5) + "\nEND\n").encode()
            target = RCSBTargetProvider(root, transport=FakeTransport(
                coordinates=coordinates)).resolve(TargetRequest("pdb", "1IEP", "A"))
            with self.assertRaisesRegex(ValueError, "multiple polymer chains"):
                RCSBPocketProvider(root).resolve(target, PocketRequest(
                    "sti-site", "A", "pdb_auth", "reference_ligand",
                    reference_ligand="STI:A:999"))

    def test_pocket_manifest_round_trip_revalidates_coordinates_and_source_lineage(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            target = RCSBTargetProvider(root, transport=FakeTransport()).resolve(
                TargetRequest("pdb", "1IEP", "A"))
            provider = RCSBPocketProvider(root)
            residue_original = provider.resolve(target, PocketRequest(
                "residue-site", "A", "pdb_auth", "residues", ("MET318", "ASP381")))
            original = provider.resolve(target, PocketRequest(
                "sti-site", "A", "pdb_auth", "reference_ligand",
                reference_ligand="STI:A:999"))
            residue_reused = provider.resolve(target, PocketRequest(
                "residue-site", "A", "pdb_auth", "artifact",
                artifact=residue_original.artifact))
            reused = provider.resolve(target, PocketRequest(
                "sti-site", "A", "pdb_auth", "artifact", artifact=original.artifact))
            self.assertEqual(residue_reused.residues, ("MET318", "ASP381"))
            self.assertEqual(residue_reused.box, residue_original.box)
            self.assertEqual(reused.box, original.box)
            self.assertEqual(reused.source_kind, "artifact")
            self.assertEqual(reused.reference_ligand, "STI:A:999")
            self.assertEqual(reused.residues, ())
            with self.assertRaisesRegex(ValueError, "source identity mismatch"):
                provider.resolve(target, PocketRequest(
                    "sti-site", "A", "label_seq", "artifact", artifact=original.artifact))

    def test_pocket_manifest_tampering_and_nonfinite_margin_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            target = RCSBTargetProvider(root, transport=FakeTransport()).resolve(
                TargetRequest("pdb", "1IEP", "A"))
            provider = RCSBPocketProvider(root)
            original = provider.resolve(target, PocketRequest(
                "sti-site", "A", "pdb_auth", "reference_ligand",
                reference_ligand="STI:A:999"))
            payload = json.loads(Path(original.artifact.uri).read_text())
            mutations = (
                ("schema", {"schema_version": "pocket-v2"}, "schema version"),
                ("center", {"center": [11.1, 22.0, 33.0]}, "geometry"),
                ("size", {"size": [12.0, 14.1, 16.0]}, "geometry"),
                ("method", {"method": "user_supplied_box"}, "geometry"),
                ("margin", {"margin": 6.0}, "geometry"),
                ("nan-margin", {"margin": float("nan")}, "finite"),
                ("source-kind", {"source_kind": "artifact"}, "source kind"),
                ("numbering", {"numbering_scheme": "label_seq"}, "numbering"),
                ("source-id", {"reference_ligand": "ATP:A:999"}, "absent"),
            )
            for name, change, message in mutations:
                with self.subTest(name=name):
                    changed = {**payload, **change}
                    path = root / f"tampered-{name}.json"
                    path.write_text(json.dumps(changed))
                    artifact = ArtifactRef(f"tampered-{name}", path.name,
                                           "application/json", str(path))
                    with self.assertRaisesRegex(ValueError, message):
                        provider.resolve(target, PocketRequest(
                            "sti-site", "A", "pdb_auth", "artifact", artifact=artifact))
            with self.assertRaisesRegex(ValueError, "finite"):
                RCSBPocketProvider(root, margin=float("nan"))

    def test_target_metadata_coordinate_chain_and_containment_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            provider = RCSBTargetProvider(Path(raw), transport=FakeTransport())
            with self.assertRaisesRegex(ValueError, "malformed"):
                provider.resolve(TargetRequest("pdb", "BAD!", "A"))
            with self.assertRaisesRegex(ValueError, "explicit PDB"):
                provider.resolve(TargetRequest("uniprot", "P00519", "A"))
        cases = (
            (FakeTransport(entry={**_entry(), "rcsb_id": "2XYZ"}), "identity mismatch"),
            (FakeTransport(entity={"unexpected": True}), "identifiers are missing"),
            (FakeTransport(entity={"rcsb_polymer_entity_container_identifiers": {
                "entry_id": "1IEP", "entity_id": "1", "auth_asym_ids": ["A", "A"]}}),
                "ambiguous"),
            (FakeTransport(coordinates=b"<html>not a pdb</html>"), "returned HTML"),
            (FakeTransport(coordinates=_pdb(entry="2XYZ")), "identity does not match"),
        )
        for transport, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory(
                    dir=ROOT / "tests") as raw:
                with self.assertRaisesRegex(ValueError, message):
                    RCSBTargetProvider(Path(raw), transport=transport).resolve(
                        TargetRequest("pdb", "1IEP", "A"))
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw) / "plugin"
            root.mkdir()
            outside = Path(raw) / "outside"
            outside.mkdir()
            (root / "escape").symlink_to(outside, target_is_directory=True)
            provider = RCSBTargetProvider(root, root / "escape", FakeTransport())
            with self.assertRaisesRegex(ValueError, "symlink"):
                provider.resolve(TargetRequest("pdb", "1IEP", "A"))

    def test_wrong_chain_residue_ligand_and_ambiguous_coordinates_never_dock(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, transport = Path(raw), FakeTransport()
            targets, pockets = RCSBTargetProvider(root, transport=transport), RCSBPocketProvider(root)
            dock = DockProvider()
            from agent.docking.docking_execution import run_docking_workflow
            from agent.molecular.molecular_binding import MolecularInputBinding
            molecule = MolecularInputBinding("full", "CCO",
                "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", True)
            requests = (
                (TargetRequest("pdb", "1IEP", "B"), PocketRequest(
                    "site", "B", "pdb_auth", "residues", ("MET318",))),
                (TargetRequest("pdb", "1IEP", "A"), PocketRequest(
                    "site", "A", "pdb_auth", "residues", ("TYR999",))),
                (TargetRequest("pdb", "1IEP", "A"), PocketRequest(
                    "site", "A", "pdb_auth", "reference_ligand",
                    reference_ligand="ATP:A:999")),
            )
            for target, pocket in requests:
                result = run_docking_workflow(molecule, target, pocket,
                    target_provider=targets, pocket_provider=pockets, docking_provider=dock)
                self.assertEqual(result.docking.status, "blocked")
            self.assertEqual(dock.calls, [])

    def test_network_schema_and_pocket_artifact_mismatch_are_local_blockers(self):
        class Offline:
            def get(self, url, params, headers={}): raise OSError("offline")
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, dock = Path(raw), DockProvider()
            from agent.docking.docking_execution import run_docking_workflow
            from agent.molecular.molecular_binding import MolecularInputBinding
            molecule = MolecularInputBinding("full", "CCO",
                "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", True)
            result = run_docking_workflow(molecule, TargetRequest("pdb", "1IEP", "A"),
                PocketRequest("site", "A", "pdb_auth", "residues", ("MET318",)),
                target_provider=RCSBTargetProvider(root, transport=Offline()),
                pocket_provider=RCSBPocketProvider(root), docking_provider=dock)
            self.assertEqual(result.docking.status, "blocked")
            self.assertIn("offline", result.coverage_gaps[0])
            self.assertEqual(dock.calls, [])

            target = RCSBTargetProvider(root, transport=FakeTransport()).resolve(
                TargetRequest("pdb", "1IEP", "A"))
            manifest = root / "wrong-pocket.json"
            manifest.write_text(json.dumps({"schema_version": "pocket-v1", "pocket_id": "site",
                "target_identifier": "1IEP", "target_artifact_id": "wrong-target",
                "chain": "A", "numbering_scheme": "pdb_auth", "source_kind": "residues",
                "residues": ["MET318"], "reference_ligand": "", "center": [0, 0, 0],
                "size": [10, 10, 10], "units": "angstrom", "method": "verified",
                "margin": 5.0}))
            artifact = ArtifactRef("user-pocket", manifest.name, "application/json", str(manifest))
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                RCSBPocketProvider(root).resolve(target, PocketRequest(
                    "site", "A", "pdb_auth", "artifact", artifact=artifact))
            with self.assertRaisesRegex(ValueError, "auth-numbered"):
                RCSBPocketProvider(root).resolve(target, PocketRequest(
                    "site", "A", "label_seq", "residues", ("MET318",)))

    def test_reference_ligand_number_is_exact_and_never_auto_remapped(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root = Path(raw)
            target = RCSBTargetProvider(root, transport=FakeTransport(
                coordinates=_pdb(ligand_number=201))).resolve(TargetRequest("pdb", "1IEP", "A"))
            with self.assertRaisesRegex(ValueError, "exact candidates: STI:A:201"):
                RCSBPocketProvider(root).resolve(target, PocketRequest(
                    "site", "A", "pdb_auth", "reference_ligand",
                    reference_ligand="STI:A:999"))

    def test_app_path_uses_verified_providers_and_excludes_raw_payload(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            root, transport = Path(raw), FakeTransport(entry={**_entry(), "secret": "SECRET_RAW"})
            pocket = PocketRequest("sti-site", "A", "pdb_auth", "reference_ligand",
                                   reference_ligand="STI:A:999")
            dock = DockProvider()
            handler = DockingChatHandler(Planner(pocket), Resolver(),
                target_provider=RCSBTargetProvider(root, transport=transport),
                pocket_provider=RCSBPocketProvider(root), docking_provider=dock)
            memory = ConversationMemoryStore(root / "memory.sqlite3", root)
            service = ResearchService(None, None, NullStore(), root, memory_store=memory,
                                      docking_handler=handler)
            message = "Dock CCO to PDB 1IEP chain A at STI:A:999"
            frames = list(service.stream_payload("user", {"chat_id": "chat", "message": message,
                                                          "mode": "docking"}))
            self.assertIn('"name": "docking"', frames[0])
            self.assertEqual(len(dock.calls), 1)
            audit = json.dumps([item.as_dict() for item in service.typed_events[("user", "chat")]])
            self.assertNotIn("SECRET_RAW", "".join(frames) + audit)
            self.assertIn("rcsb-pdb-1IEP", audit)
            self.assertIn("verified_reference_ligand_bounding_box", audit)
            self.assertEqual(memory.count("user"), 2)
            self.assertFalse(is_clear_docking_intent("Find literature about docking at PDB 1IEP"))

    def test_factory_composes_no_key_rcsb_providers(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as raw:
            config = RuntimeConfig(ROOT, Path(raw) / "memory.sqlite3")
            service = build_research_service(config, runner=Runner(),
                                             rcsb_transport=FakeTransport())
            self.assertIsInstance(service.docking_handler.target_provider, RCSBTargetProvider)
            self.assertIsInstance(service.docking_handler.pocket_provider, RCSBPocketProvider)


def _entry():
    return {"rcsb_id": "1IEP", "rcsb_entry_container_identifiers": {
        "entry_id": "1IEP", "polymer_entity_ids": ["1"]}}


def _entity():
    return {"rcsb_polymer_entity_container_identifiers": {
        "entry_id": "1IEP", "entity_id": "1", "auth_asym_ids": ["A"]}}


def _pdb(entry="1IEP", ligand_number=999):
    lines = ["HEADER" + " " * 56 + entry]
    lines.extend((
        _atom("ATOM", 1, "CA", "MET", "A", 318, 0.0, 0.0, 0.0),
        _atom("ATOM", 2, "CB", "MET", "A", 318, 2.0, 2.0, 2.0),
        _atom("ATOM", 3, "CA", "ASP", "A", 381, 4.0, 5.0, 6.0),
        _atom("HETATM", 4, "C1", "STI", "A", ligand_number, 10.0, 20.0, 30.0),
        _atom("HETATM", 5, "C2", "STI", "A", ligand_number, 12.0, 24.0, 36.0),
        "END",
    ))
    return ("\n".join(lines) + "\n").encode()


def _atom(record, serial, atom, residue, chain, number, x, y, z):
    return (f"{record:<6}{serial:>5} {atom:<4} {residue:>3} {chain}{number:>4}    "
            f"{x:>8.3f}{y:>8.3f}{z:>8.3f}  1.00 20.00           C")


if __name__ == "__main__":
    unittest.main()
