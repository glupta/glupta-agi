from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from glupta_agi.contracts import EvidenceBriefRequest
from glupta_agi.intake import IntakeError, load_request


class IntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "notes").mkdir()
        (self.root / "notes" / "facts.md").write_text("alpha\nbeta\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_canonical_request_is_stable(self) -> None:
        one = load_request(
            input_root=self.root,
            question=" What changed? ",
            selected_paths=["notes/facts.md"],
        )
        two = load_request(
            input_root=self.root,
            question="What changed?",
            selected_paths=["notes/facts.md"],
        )
        self.assertEqual(one.request_digest, two.request_digest)
        self.assertEqual(one.question, "What changed?")
        self.assertEqual(one.sources[0].lines, ("alpha", "beta"))

    def test_removed_artifact_option_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBriefRequest.model_validate(
                {"question": "q", "files": ["notes/facts.md"], "write_artifacts": False}
            )

    def test_legacy_payload_still_matches_for_durable_replay(self) -> None:
        canonical = load_request(
            input_root=self.root,
            question="What changed?",
            selected_paths=["notes/facts.md"],
        )
        legacy = {
            **canonical.workflow_payload(),
            "request_digest": "legacy-0.2.0-digest",
            "write_artifacts": False,
        }

        self.assertTrue(canonical.matches_recorded_payload(legacy))
        self.assertFalse(canonical.matches_recorded_payload({**legacy, "question": "other"}))

    def test_changed_bytes_change_digest(self) -> None:
        before = load_request(input_root=self.root, question="q", selected_paths=["notes/facts.md"])
        (self.root / "notes" / "facts.md").write_text("changed\n", encoding="utf-8")
        after = load_request(input_root=self.root, question="q", selected_paths=["notes/facts.md"])
        self.assertNotEqual(before.request_digest, after.request_digest)

    def test_rejects_traversal_hidden_url_extension_duplicate_and_empty(self) -> None:
        bad_sets = [
            ["../facts.md"],
            [".hidden.md"],
            ["https://example.com/a.md"],
            ["notes/bad\nname.md"],
            ["notes/archive.zip"],
            ["notes/facts.md", "notes/facts.md"],
            [],
        ]
        for paths in bad_sets:
            with self.subTest(paths=paths), self.assertRaises(IntakeError):
                load_request(input_root=self.root, question="q", selected_paths=paths)

    def test_rejects_symlink_file_and_symlink_directory(self) -> None:
        outside = self.root.parent / f"{self.root.name}-outside.md"
        outside.write_text("secret", encoding="utf-8")
        try:
            os.symlink(outside, self.root / "linked.md")
            os.symlink(self.root / "notes", self.root / "linked-dir")
            for path in ["linked.md", "linked-dir/facts.md"]:
                with self.subTest(path=path), self.assertRaises(IntakeError):
                    load_request(input_root=self.root, question="q", selected_paths=[path])
        finally:
            outside.unlink()

    def test_rejects_invalid_utf8(self) -> None:
        (self.root / "bad.txt").write_bytes(b"\xff")
        with self.assertRaisesRegex(IntakeError, "UTF-8"):
            load_request(input_root=self.root, question="q", selected_paths=["bad.txt"])

    def test_enforces_file_count_and_total_bytes(self) -> None:
        for index in range(21):
            (self.root / f"{index}.txt").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(IntakeError, "between 1 and 20"):
            load_request(
                input_root=self.root,
                question="q",
                selected_paths=[f"{index}.txt" for index in range(21)],
            )
        (self.root / "large.txt").write_bytes(b"x" * (256 * 1024 + 1))
        with self.assertRaisesRegex(IntakeError, "byte limit"):
            load_request(input_root=self.root, question="q", selected_paths=["large.txt"])
