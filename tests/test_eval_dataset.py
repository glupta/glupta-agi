from __future__ import annotations

import json
import unittest
from pathlib import Path, PurePosixPath


class EvalDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = Path(__file__).parents[1] / "evals" / "evidence_brief_v1.json"
        cls.dataset = json.loads(path.read_text(encoding="utf-8"))

    def test_dataset_has_exactly_twenty_unique_cases(self) -> None:
        self.assertEqual(self.dataset["schema"], "EvidenceBriefEvalDatasetV1")
        cases = self.dataset["cases"]
        self.assertEqual(len(cases), 20)
        self.assertEqual(len({case["id"] for case in cases}), 20)

    def test_cases_obey_frozen_intake_contract(self) -> None:
        expected = {
            "id",
            "question",
            "files",
            "required_points",
            "required_uncertainties",
            "forbidden_points",
        }
        for case in self.dataset["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(set(case), expected)
                self.assertTrue(case["question"].strip())
                self.assertGreaterEqual(len(case["files"]), 1)
                self.assertLessEqual(len(case["files"]), 20)
                self.assertLessEqual(
                    sum(len(content.encode("utf-8")) for content in case["files"].values()),
                    256 * 1024,
                )
                for name, content in case["files"].items():
                    path = PurePosixPath(name)
                    self.assertFalse(path.is_absolute())
                    self.assertTrue(path.suffix in {".md", ".txt"})
                    self.assertTrue(all(not part.startswith(".") for part in path.parts))
                    content.encode("utf-8")

    def test_dataset_contains_adversarial_and_abstention_cases(self) -> None:
        ids = {case["id"] for case in self.dataset["cases"]}
        self.assertTrue(
            {
                "EV-003-conflict",
                "EV-004-missing-answer",
                "EV-007-indirect-injection",
                "EV-008-tool-injection",
                "EV-009-secret-request-injection",
                "EV-020-no-evidence-command",
            }.issubset(ids)
        )
