from __future__ import annotations

import unittest

from glupta_agi.brief import resolve_citations
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
