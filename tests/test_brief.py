from __future__ import annotations

import unittest

from glupta_agi.brief import SYSTEM_PROMPT, resolve_citations
from glupta_agi.contracts import Citation, EvidenceBrief


class CitationResolutionTests(unittest.TestCase):
    def test_resolves_quote_from_selected_line_range(self) -> None:
        brief = EvidenceBrief(
            answer="Grounded answer.",
            citations=[Citation(path="source.md", line_start=2, line_end=3, quote="paraphrase")],
            uncertainties=[],
            next_decisions=[],
        )

        resolved = resolve_citations(
            brief,
            [{"path": "source.md", "content": "first\nsecond\nthird"}],
        )

        self.assertEqual(resolved.citations[0].quote, "second\nthird")

    def test_rejects_unknown_source_and_invalid_range(self) -> None:
        sources = [{"path": "source.md", "content": "only line"}]
        for citation in (
            Citation(path="other.md", line_start=1, line_end=1, quote="x"),
            Citation(path="source.md", line_start=1, line_end=2, quote="x"),
        ):
            with self.subTest(citation=citation):
                brief = EvidenceBrief(
                    answer="Answer.",
                    citations=[citation],
                    uncertainties=[],
                    next_decisions=[],
                )
                with self.assertRaises(ValueError):
                    resolve_citations(brief, sources)


class SystemPromptTests(unittest.TestCase):
    def test_requires_decision_relevant_coverage_and_progressive_actions(self) -> None:
        prompt = " ".join(SYSTEM_PROMPT.split())

        self.assertIn("address every explicit requested item", prompt)
        self.assertIn(
            "report every mismatch or unproven prerequisite that could change the requested "
            "decision",
            prompt,
        )
        self.assertIn(
            "do not exhaustively list satisfied requirements unless requested",
            prompt,
        )
        self.assertIn(
            "Do not treat labels, examples, or logical identifiers as exact implementation "
            "requirements unless selected evidence explicitly says so",
            prompt,
        )
        self.assertIn(
            "Each next action must name its concrete subject, evidence, and pass/fail condition",
            prompt,
        )
        self.assertIn(
            "must change the subject or evidence packet rather than repeat the current task",
            prompt,
        )
        self.assertNotIn("classify every material requirement", prompt)
        self.assertIn(
            "Return citations only in the citations field; do not add citation labels or markers "
            "to any prose field",
            prompt,
        )
