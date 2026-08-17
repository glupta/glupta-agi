from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from glupta_agi.artifacts import persist_artifacts


class ArtifactTests(unittest.TestCase):
    def test_writes_private_deterministic_files_and_allows_exact_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "artifacts"
            result = {"answer": "grounded", "request_digest": "abc"}
            persist_artifacts("workflow-1", str(root), result, "# Brief\n")
            persist_artifacts("workflow-1", str(root), result, "# Brief\n")

            self.assertEqual(
                (root / "workflow-1.json").read_text(encoding="utf-8"),
                '{\n  "answer": "grounded",\n  "request_digest": "abc"\n}\n',
            )
            self.assertEqual((root / "workflow-1.md").read_text(), "# Brief\n")
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            self.assertEqual((root / "workflow-1.json").stat().st_mode & 0o777, 0o600)

    def test_rejects_changed_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "artifacts"
            persist_artifacts("workflow-1", str(root), {"answer": "one"}, "one\n")
            with self.assertRaisesRegex(RuntimeError, "artifact collision"):
                persist_artifacts("workflow-1", str(root), {"answer": "two"}, "two\n")

    def test_rejects_nonprivate_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "artifacts"
            root.mkdir(mode=0o755)
            with self.assertRaisesRegex(RuntimeError, "permissions are not private"):
                persist_artifacts("workflow-1", str(root), {"answer": "one"}, "one\n")

    def test_rejects_symlink_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "artifacts"
            root.mkdir(mode=0o700)
            target = Path(directory) / "outside"
            target.write_text("outside", encoding="utf-8")
            os.symlink(target, root / "workflow-1.json")
            with self.assertRaises(OSError):
                persist_artifacts("workflow-1", str(root), {"answer": "one"}, "one\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "outside")
