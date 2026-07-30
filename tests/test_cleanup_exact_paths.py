from __future__ import annotations

import unittest
from pathlib import Path

from scripts.cleanup_exact_paths import PROJECT_ROOT, inventory, remove_inventory


class CleanupExactPathsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.target = (
            PROJECT_ROOT
            / "runtime"
            / "evaluation"
            / "cleanup-exact-paths-test"
            / "nested"
        )
        self.target.mkdir(parents=True, exist_ok=True)
        (self.target / "sample.tmp").write_text("fixture", encoding="utf-8")

    def tearDown(self) -> None:
        test_root = self.target.parent
        if self.target.exists():
            for path in sorted(
                self.target.rglob("*"), key=lambda item: len(item.parts), reverse=True
            ):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            self.target.rmdir()
        if test_root.exists():
            for path in sorted(
                test_root.rglob("*"), key=lambda item: len(item.parts), reverse=True
            ):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            test_root.rmdir()

    def test_inventory_and_apply_remove_only_explicit_target(self) -> None:
        record = inventory(str(self.target))
        self.assertEqual(record["file_count"], 1)
        self.assertEqual(record["total_bytes"], 7)
        remove_inventory(record)
        self.assertFalse(self.target.exists())

    def test_refuses_project_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "protected root"):
            inventory(str(PROJECT_ROOT))

    def test_refuses_relative_target(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            inventory("runtime/evaluation/example")

    def test_refuses_non_cache_source_directory(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowed cleanup roots"):
            inventory(str(PROJECT_ROOT / "agent" / "core"))


if __name__ == "__main__":
    unittest.main()
