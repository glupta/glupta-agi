from __future__ import annotations

import unittest
from pathlib import Path

from pydantic_evals.evaluators import EvaluatorContext

from evals.runner import EvalInput, GroundedBriefEvaluator, load_dataset
from glupta_agi.contracts import Citation, EvidenceBrief


class CrawlEvalTests(unittest.TestCase):
    def test_frozen_dataset_loads_as_pydantic_evals_cases(self) -> None:
        path = Path(__file__).parents[1] / "evals" / "evidence_brief_v1.json"
        dataset = load_dataset(path, case_names={"EV-001-single-source"})

        self.assertEqual(dataset.name, "evidence_brief_v1")
        self.assertEqual([case.name for case in dataset.cases], ["EV-001-single-source"])

    def test_deterministic_evaluator_scores_required_and_forbidden_content(self) -> None:
        source = {"path": "status.md", "content": "Status: paused"}
        output = EvidenceBrief(
            answer="The status is paused.",
            citations=[
                Citation(path="status.md", line_start=1, line_end=1, quote="Status: paused")
            ],
            uncertainties=[],
            next_decisions=[],
        )
        path = Path(__file__).parents[1] / "evals" / "evidence_brief_v1.json"
        expected = load_dataset(path, case_names={"EV-007-indirect-injection"}).cases[0].metadata
        context = EvaluatorContext(
            name="EV-007-indirect-injection",
            inputs=EvalInput(question="What is the recorded status?", sources=[source]),
            metadata=expected,
            expected_output=None,
            output=output,
            duration=0.1,
            _span_tree={},
            attributes={},
            metrics={},
        )

        result = GroundedBriefEvaluator().evaluate(context)

        self.assertTrue(all(item.value for item in result.values()))

    def test_unknown_case_fails_closed(self) -> None:
        path = Path(__file__).parents[1] / "evals" / "evidence_brief_v1.json"
        with self.assertRaisesRegex(ValueError, "unknown eval case"):
            load_dataset(path, case_names={"EV-999"})

    def test_forbidden_phrase_inside_negation_is_not_treated_as_asserted(self) -> None:
        output = EvidenceBrief(
            answer="No action is authorized.",
            citations=[
                Citation(
                    path="authority.txt",
                    line_start=1,
                    line_end=1,
                    quote="No action is authorized.",
                )
            ],
            uncertainties=[],
            next_decisions=[],
        )
        path = Path(__file__).parents[1] / "evals" / "evidence_brief_v1.json"
        case = load_dataset(path, case_names={"EV-008-tool-injection"}).cases[0]
        context = EvaluatorContext(
            name=case.name,
            inputs=case.inputs,
            metadata=case.metadata,
            expected_output=None,
            output=output,
            duration=0.1,
            _span_tree={},
            attributes={},
            metrics={},
        )

        result = GroundedBriefEvaluator().evaluate(context)

        self.assertTrue(result["forbidden_points"].value)

        context.output = output.model_copy(update={"answer": "Action is authorized."})
        result = GroundedBriefEvaluator().evaluate(context)
        self.assertFalse(result["forbidden_points"].value)
