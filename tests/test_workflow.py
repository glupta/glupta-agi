from __future__ import annotations

import json
import os
import subprocess
import tempfile
import traceback
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from codex_cli_bin import bundled_codex_path
from openai_codex import TransportClosedError
from pydantic import TypeAdapter
from pydantic_ai import Agent
from pydantic_ai.durable_exec.dbos import DBOSDurability
from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart
from pydantic_ai.usage import RequestUsage

from glupta_agi.contracts import EvidenceBrief
from glupta_agi.effects import AmbiguousEffectError, Effect
from glupta_agi.workflow import (
    BriefGenerationError,
    _crawl_agent,
    _crawl_durability,
    _crawl_model,
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

    def __init__(self, final_response: str, usage: object | None = None) -> None:
        self._final_response = final_response
        self._usage = usage

    def run(self) -> SimpleNamespace:
        return SimpleNamespace(
            status=SimpleNamespace(value="completed"),
            final_response=self._final_response,
            usage=self._usage,
        )


class FakeThread:
    id = "thread-1"

    def __init__(self, final_response: str, usage: object | None = None) -> None:
        self._final_response = final_response
        self._usage = usage
        self.turn_kwargs: dict[str, object] = {}

    def turn(self, prompt: str, **kwargs: object) -> FakeTurn:
        self.turn_kwargs = {"prompt": prompt, **kwargs}
        return FakeTurn(self._final_response, self._usage)


class FakeClient:
    def __init__(self, final_response: str, usage: object | None = None) -> None:
        self.thread = FakeThread(final_response, usage)
        self.start_kwargs: dict[str, object] = {}
        self.closed = False

    def thread_start(self, **kwargs: object) -> FakeThread:
        self.start_kwargs = kwargs
        return self.thread

    def close(self) -> None:
        self.closed = True


class CodexBriefTests(unittest.TestCase):
    def setUp(self) -> None:
        self._codex_home = tempfile.TemporaryDirectory(prefix="glupta-test-codex-")
        self.codex_home = self._codex_home.name

    def tearDown(self) -> None:
        self._codex_home.cleanup()

    def test_crawl_model_work_is_bounded_by_one_dbos_queue_slot(self) -> None:
        self.assertEqual(crawl_observe_queue.name, "crawl-observe-v1")
        self.assertEqual(crawl_observe_queue.concurrency, 1)
        self.assertEqual(crawl_observe_queue.worker_concurrency, 1)

    def test_runtime_uses_native_pydantic_ai_dbos_durability_without_retries(self) -> None:
        self.assertIsInstance(_crawl_agent, Agent)
        self.assertIsInstance(_crawl_durability, DBOSDurability)
        self.assertEqual(_crawl_durability._model_step_config, {"retries_allowed": False})
        self.assertFalse(_crawl_durability._register_legacy_workflows)

    def test_native_model_response_retains_usage_through_pydantic_serialization(self) -> None:
        packet = json.dumps(
            {
                "prompt": "question",
                "sources": [],
                "codex_home": self.codex_home,
                "model_name": "gpt-5.6-sol",
                "workflow_id": "workflow-1",
                "request_digest": "digest-1",
            }
        )
        brief = EvidenceBrief(answer="Grounded.", citations=[], uncertainties=[], next_decisions=[])
        usage = RequestUsage(input_tokens=120, cache_read_tokens=20, output_tokens=30)
        with patch("glupta_agi.workflow._run_codex", return_value=(brief, usage)):
            response = _crawl_model(
                [ModelRequest(parts=[UserPromptPart(content=packet)])],
                Mock(),
            )

        adapter = TypeAdapter(ModelResponse)
        restored = adapter.validate_json(adapter.dump_json(response))
        self.assertEqual(restored.usage, usage)

    def test_runs_fenced_secondary_codex_without_tools_and_resolves_quote(self) -> None:
        usage = SimpleNamespace(
            last=SimpleNamespace(
                input_tokens=120,
                cached_input_tokens=20,
                output_tokens=30,
                reasoning_output_tokens=12,
            )
        )
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
            ),
            usage,
        )
        with (
            patch("glupta_agi.workflow.reserve", return_value=_effect("reserved")),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
        ):
            result, request_usage = _run_codex(
                "question",
                [{"path": "compose.txt", "content": "services:"}],
                self.codex_home,
                "gpt-5.6-sol",
                "workflow-1",
                "digest-1",
                codex_factory=lambda config: client,
            )

        self.assertEqual(result.citations[0].quote, "services:")
        self.assertEqual(request_usage.input_tokens, 120)
        self.assertEqual(request_usage.cache_read_tokens, 20)
        self.assertEqual(request_usage.output_tokens, 30)
        self.assertEqual(request_usage.details, {"reasoning_output_tokens": 12})
        self.assertIsNone(request_usage.cost)
        self.assertTrue(client.start_kwargs["ephemeral"])
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
        state_home_existed_during_launch: list[bool] = []

        def factory(config: object) -> FakeClient:
            captured_config.append(config)
            launch_args = config.launch_args_override
            codex_index = launch_args.index(str(bundled_codex_path()))
            state_argument = launch_args[codex_index + 6]
            state_home = json.loads(state_argument.removeprefix("sqlite_home="))
            state_home_existed_during_launch.append(os.path.isdir(state_home))
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
                self.codex_home,
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
        self.assertEqual(
            launch_args[codex_index + 1 : codex_index + 6],
            (
                "-c",
                'cli_auth_credentials_store="file"',
                "-c",
                'history.persistence="none"',
                "-c",
            ),
        )
        state_argument = launch_args[codex_index + 6]
        self.assertTrue(state_argument.startswith(f'sqlite_home="{self.codex_home}/'))
        self.assertTrue(state_argument.endswith('"'))
        state_home = json.loads(state_argument.removeprefix("sqlite_home="))
        self.assertEqual(state_home_existed_during_launch, [True])
        self.assertFalse(os.path.exists(state_home))
        self.assertNotIn("log_dir", " ".join(launch_args))
        self.assertEqual(
            launch_args[codex_index + 7 :],
            (
                "app-server",
                "--disable",
                "apps",
                "--disable",
                "plugins",
                "--disable",
                "remote_plugin",
                "--listen",
                "stdio://",
            ),
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
            result, request_usage = _run_codex(
                "question",
                [{"path": "compose.txt", "content": "services:"}],
                self.codex_home,
                "gpt-5.6-sol",
                "workflow-1",
                "digest-1",
                codex_factory=factory,
            )

        self.assertEqual(result.answer, "Grounded answer.")
        self.assertEqual(request_usage.details, {"sdk_usage_unavailable": 1})
        self.assertTrue(request_usage.has_values())
        self.assertIsNone(request_usage.cost)
        factory.assert_not_called()
        self.assertEqual(os.listdir(self.codex_home), [])

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
                    self.codex_home,
                    "gpt-5.6-sol",
                    "workflow-1",
                    "digest-1",
                    codex_factory=factory,
                )
        factory.assert_not_called()

    def test_invalid_typed_output_is_terminal_not_retried(self) -> None:
        sentinel = "CRAWL_INVALID_OUTPUT_SENTINEL"
        client = FakeClient(json.dumps({"answer": sentinel}))
        with (
            patch("glupta_agi.workflow.reserve", return_value=_effect("reserved")),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
        ):
            with self.assertRaises(BriefGenerationError) as caught:
                _run_codex(
                    "question",
                    [{"path": "compose.txt", "content": "services:"}],
                    self.codex_home,
                    "gpt-5.6-sol",
                    "workflow-1",
                    "digest-1",
                    codex_factory=lambda config: client,
                )

        self.assertEqual(transition.call_args_list[-1].args[2], "failed")
        self.assertIsNone(caught.exception.__context__)
        rendered = "".join(traceback.format_exception(caught.exception))
        self.assertNotIn(sentinel, rendered)

    def test_provider_error_is_held_with_sanitized_token_and_no_raw_context(self) -> None:
        sentinel = "CRAWL_PROVIDER_ERROR_SENTINEL"

        class FailingClient(FakeClient):
            def thread_start(self, **kwargs: object) -> FakeThread:
                del kwargs
                raise TransportClosedError(sentinel)

        client = FailingClient("")
        factory = Mock(return_value=client)
        held: list[tuple[Effect, str]] = []

        def sanitized_hold(effect: Effect, reason: str) -> None:
            held.append((effect, reason))
            raise AmbiguousEffectError("model effect requires reconciliation")

        with (
            patch("glupta_agi.workflow.reserve", return_value=_effect("reserved")),
            patch("glupta_agi.workflow.transition", side_effect=_transition),
            patch("glupta_agi.workflow.hold_unknown", side_effect=sanitized_hold),
        ):
            with self.assertRaises(AmbiguousEffectError) as caught:
                _run_codex(
                    "question",
                    [{"path": "compose.txt", "content": "services:"}],
                    self.codex_home,
                    "gpt-5.6-sol",
                    "workflow-1",
                    "digest-1",
                    codex_factory=factory,
                )

        factory.assert_called_once()
        self.assertTrue(client.closed)
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0][1], "provider_transport_closed_after_dispatching")
        self.assertIsNone(caught.exception.__context__)
        rendered = "".join(traceback.format_exception(caught.exception))
        self.assertNotIn(sentinel, str(caught.exception))
        self.assertNotIn(sentinel, repr(caught.exception))
        self.assertNotIn(sentinel, rendered)
        self.assertEqual(os.listdir(self.codex_home), [])

    def test_pre_turn_value_error_is_provider_failure_not_invalid_output(self) -> None:
        sentinel = "CRAWL_PROVIDER_VALUE_ERROR_SENTINEL"

        class FailingClient(FakeClient):
            def thread_start(self, **kwargs: object) -> FakeThread:
                del kwargs
                raise ValueError(sentinel)

        client = FailingClient("")
        held: list[str] = []

        def sanitized_hold(effect: Effect, reason: str) -> None:
            del effect
            held.append(reason)
            raise AmbiguousEffectError("model effect requires reconciliation")

        with (
            patch("glupta_agi.workflow.reserve", return_value=_effect("reserved")),
            patch("glupta_agi.workflow.transition", side_effect=_transition),
            patch("glupta_agi.workflow.hold_unknown", side_effect=sanitized_hold),
        ):
            with self.assertRaises(AmbiguousEffectError) as caught:
                _run_codex(
                    "question",
                    [{"path": "compose.txt", "content": "services:"}],
                    self.codex_home,
                    "gpt-5.6-sol",
                    "workflow-1",
                    "digest-1",
                    codex_factory=lambda config: client,
                )

        self.assertTrue(client.closed)
        self.assertEqual(held, ["provider_error_after_dispatching"])
        self.assertIsNone(caught.exception.__context__)
        self.assertNotIn(sentinel, "".join(traceback.format_exception(caught.exception)))
