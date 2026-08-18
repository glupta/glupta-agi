from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic_ai.usage import RequestUsage
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EvaluatorContext

from evals.runner import EvalInput, GroundedBriefEvaluator, load_dataset, run_eval
from glupta_agi.contracts import Citation, EvidenceBrief, ProviderResult
from tests.helpers import provider_audit, release_profile


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

    def test_synthetic_runner_awaits_inference_through_pydantic_evals(self) -> None:
        inputs = EvalInput(
            question="What is the status?",
            sources=[{"path": "status.md", "content": "Status: paused"}],
        )
        dataset = Dataset(name="synthetic", cases=[Case(name="synthetic", inputs=inputs)])
        brief = EvidenceBrief(
            answer="The status is paused.",
            citations=[
                Citation(path="status.md", line_start=1, line_end=1, quote="Status: paused")
            ],
            uncertainties=[],
            next_decisions=[],
        )
        audit = provider_audit(
            brief,
            workflow_id="synthetic-workflow",
            request_digest="a" * 64,
        )
        inference = AsyncMock(
            return_value=(ProviderResult(brief=brief, audit=audit), RequestUsage())
        )
        settings = SimpleNamespace(
            dbos_system_database_url=lambda: "postgresql://local/synthetic",
            require_external_profile=lambda: (release_profile(), Path("/private/synthetic-key")),
        )

        with (
            patch("evals.runner.Settings.from_environment", return_value=settings),
            patch("evals.runner.initialize") as initialize,
            patch("evals.runner._run_inference", inference),
        ):
            report = run_eval(dataset)

        self.assertEqual(report.failures, [])
        self.assertEqual(len(report.cases), 1)
        self.assertEqual(report.cases[0].output, brief)
        initialize.assert_called_once_with("postgresql://local/synthetic")
        inference.assert_awaited_once()
        packet = inference.await_args.args[0]
        self.assertIn("What is the status?", packet.prompt)
        self.assertEqual(packet.sources, inputs.sources)

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
