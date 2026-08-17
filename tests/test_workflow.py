from __future__ import annotations

import json
import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from codex_cli_bin import bundled_codex_path
from pydantic_ai import Agent
from pydantic_ai.durable_exec.dbos import DBOSDurability

from glupta_agi.effects import AmbiguousEffectError, Effect
from glupta_agi.workflow import (
    BriefGenerationError,
    _crawl_agent,
    _crawl_durability,
    _run_codex,
    crawl_observe_queue,
)


def _effect(state: str, result: dict[str, object] | None = None) -> Effect:
    return Effect(
        workflow_id="workflow-1",
        request_digest="digest-1",
        model_name="gpt-5.6-sol",
        state=state,
        thread_id="thread-1" if state in {"thread_started", "turn_started"} else None,
        turn_id="turn-1" if state == "turn_started" else None,
        result=result,
    )


def _transition(
    workflow_id: str,
    expected: str,
    state: str,
    **kwargs: object,
) -> Effect:
    del workflow_id, expected
    return Effect(
        workflow_id="workflow-1",
        request_digest="digest-1",
        model_name="gpt-5.6-sol",
        state=state,
        thread_id=str(kwargs.get("thread_id") or "thread-1"),
        turn_id=str(kwargs.get("turn_id") or "turn-1"),
        result=kwargs.get("result") if isinstance(kwargs.get("result"), dict) else None,
    )


class FakeTurn:
    id = "turn-1"

    def __init__(self, final_response: str) -> None:
        self._final_response = final_response

    def run(self) -> SimpleNamespace:
        return SimpleNamespace(
            status=SimpleNamespace(value="completed"),
            final_response=self._final_response,
        )


class FakeThread:
    id = "thread-1"

    def __init__(self, final_response: str) -> None:
        self._final_response = final_response
        self.turn_kwargs: dict[str, object] = {}

    def turn(self, prompt: str, **kwargs: object) -> FakeTurn:
        self.turn_kwargs = {"prompt": prompt, **kwargs}
        return FakeTurn(self._final_response)


class FakeClient:
    def __init__(self, final_response: str) -> None:
        self.thread = FakeThread(final_response)
        self.start_kwargs: dict[str, object] = {}
        self.closed = False

    def thread_start(self, **kwargs: object) -> FakeThread:
        self.start_kwargs = kwargs
        return self.thread

    def close(self) -> None:
        self.closed = True


class CodexBriefTests(unittest.TestCase):
    def test_crawl_model_work_is_bounded_by_one_dbos_queue_slot(self) -> None:
        self.assertEqual(crawl_observe_queue.name, "crawl-observe-v1")
        self.assertEqual(crawl_observe_queue.concurrency, 1)
        self.assertEqual(crawl_observe_queue.worker_concurrency, 1)

    def test_runtime_uses_native_pydantic_ai_dbos_durability_without_retries(self) -> None:
        self.assertIsInstance(_crawl_agent, Agent)
        self.assertIsInstance(_crawl_durability, DBOSDurability)
        self.assertEqual(_crawl_durability._model_step_config, {"retries_allowed": False})
        self.assertFalse(_crawl_durability._register_legacy_workflows)

    def test_runs_fenced_secondary_codex_without_tools_and_resolves_quote(self) -> None:
        client = FakeClient(
            json.dumps(
                {
                    "answer": "Grounded answer.",
                    "citations": [
                        {
                            "path": "compose.txt",
                            "line_start": 1,
                            "line_end": 1,
                            "quote": "model quote",
                        }
                    ],
                    "uncertainties": [],
                    "next_decisions": [],
                }
            )
        )
        with (
            patch("glupta_agi.workflow.reserve", return_value=_effect("reserved")),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
        ):
            result = _run_codex(
                "question",
                [{"path": "compose.txt", "content": "services:"}],
                "/run/codex",
                "gpt-5.6-sol",
                "workflow-1",
                "digest-1",
                codex_factory=lambda config: client,
            )

        self.assertEqual(result.citations[0].quote, "services:")
        self.assertFalse(client.start_kwargs["ephemeral"])
        self.assertEqual(client.start_kwargs["model"], "gpt-5.6-sol")
        config = client.start_kwargs["config"]
        self.assertIsInstance(config, dict)
        self.assertEqual(config["features"]["shell_tool"], False)
        self.assertEqual(config["web_search"], "disabled")
        self.assertEqual(config["model_provider"], "crawl_openai")
        self.assertEqual(config["model_providers"]["crawl_openai"]["request_max_retries"], 0)
        self.assertEqual(config["model_providers"]["crawl_openai"]["stream_max_retries"], 0)
        self.assertEqual(client.thread.turn_kwargs["effort"].value, "medium")
        self.assertTrue(client.closed)
        self.assertEqual(
            [call.args[2] for call in transition.call_args_list],
            ["dispatching", "thread_started", "turn_started", "returned", "reconciled"],
        )

    def test_codex_launch_discards_ambient_environment(self) -> None:
        client = FakeClient(
            json.dumps(
                {
                    "answer": "Grounded answer.",
                    "citations": [],
                    "uncertainties": [],
                    "next_decisions": [],
                }
            )
        )
        captured_config: list[object] = []

        def factory(config: object) -> FakeClient:
            captured_config.append(config)
            return client

        sentinel = "CRAWL_TEST_SENTINEL_SECRET"
        with (
            patch.dict(os.environ, {sentinel: "must-not-leak"}),
            patch("glupta_agi.workflow.reserve", return_value=_effect("reserved")),
            patch("glupta_agi.workflow.transition", side_effect=_transition),
        ):
            _run_codex(
                "question",
                [{"path": "compose.txt", "content": "services:"}],
                "/run/codex",
                "gpt-5.6-sol",
                "workflow-1",
                "digest-1",
                codex_factory=factory,
            )

        self.assertEqual(len(captured_config), 1)
        sdk_config = captured_config[0]
        self.assertIsNone(sdk_config.env)
        launch_args = sdk_config.launch_args_override
        self.assertIsNotNone(launch_args)
        self.assertEqual(launch_args[1], "-i")
        codex_index = launch_args.index(str(bundled_codex_path()))
        assignments = dict(assignment.split("=", 1) for assignment in launch_args[2:codex_index])
        self.assertNotIn(sentinel, assignments)
        self.assertEqual(
            set(assignments),
            {
                "CODEX_HOME",
                "HOME",
                "LANG",
                "PATH",
                "STUDIO_CODEX_SESSION_ORIGIN",
                "TMPDIR",
            },
        )
        probe = subprocess.run(  # noqa: S603 -- launcher is resolved from os.defpath
            [*launch_args[:codex_index], launch_args[0]],
            check=True,
            capture_output=True,
            env={**os.environ, sentinel: "must-not-leak"},
            text=True,
        )
        child_environment = dict(line.split("=", 1) for line in probe.stdout.splitlines())
        self.assertEqual(child_environment, assignments)
        self.assertNotIn(sentinel, child_environment)

    def test_replay_returns_recorded_result_without_provider_call(self) -> None:
        recorded = {
            "answer": "Grounded answer.",
            "citations": [
                {"path": "compose.txt", "line_start": 1, "line_end": 1, "quote": "services:"}
            ],
            "uncertainties": [],
            "next_decisions": [],
        }
        factory = Mock()
        with patch("glupta_agi.workflow.reserve", return_value=_effect("reconciled", recorded)):
            result = _run_codex(
                "question",
                [{"path": "compose.txt", "content": "services:"}],
                "/run/codex",
                "gpt-5.6-sol",
                "workflow-1",
                "digest-1",
                codex_factory=factory,
            )

        self.assertEqual(result.answer, "Grounded answer.")
        factory.assert_not_called()

    def test_ambiguous_dispatch_is_held_without_second_provider_call(self) -> None:
        factory = Mock()
        with (
            patch("glupta_agi.workflow.reserve", return_value=_effect("dispatching")),
            patch(
                "glupta_agi.workflow.hold_unknown",
                side_effect=AmbiguousEffectError("manual reconciliation required"),
            ),
        ):
            with self.assertRaises(AmbiguousEffectError):
                _run_codex(
                    "question",
                    [{"path": "compose.txt", "content": "services:"}],
                    "/run/codex",
                    "gpt-5.6-sol",
                    "workflow-1",
                    "digest-1",
                    codex_factory=factory,
                )
        factory.assert_not_called()

    def test_invalid_typed_output_is_terminal_not_retried(self) -> None:
        client = FakeClient("{}")
        with (
            patch("glupta_agi.workflow.reserve", return_value=_effect("reserved")),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
        ):
            with self.assertRaises(BriefGenerationError):
                _run_codex(
                    "question",
                    [{"path": "compose.txt", "content": "services:"}],
                    "/run/codex",
                    "gpt-5.6-sol",
                    "workflow-1",
                    "digest-1",
                    codex_factory=lambda config: client,
                )

        self.assertEqual(transition.call_args_list[-1].args[2], "failed")
