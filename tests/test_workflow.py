from __future__ import annotations

import asyncio
import traceback
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from pydantic_ai import Agent
from pydantic_ai.durable_exec.dbos import DBOSDurability

from glupta_agi.client import _uuid7
from glupta_agi.contracts import Citation, EvidenceBrief
from glupta_agi.effects import AmbiguousEffectError, Effect
from glupta_agi.inference import (
    ProviderAudit,
    ProviderResult,
    canonical_digest,
    provider_record_digest,
)
from glupta_agi.openai_adapter import ProviderAmbiguousError, ProviderRejectedError
from glupta_agi.workflow import (
    BriefGenerationError,
    _crawl_agent,
    _crawl_durability,
    _CrawlModelPacket,
    _run_inference,
    crawl_observe_queue,
)
from tests.helpers import release_profile


def _packet(
    *,
    prompt: str = "question",
    workflow_id: str | None = None,
    admitted_at: datetime | None = None,
) -> _CrawlModelPacket:
    return _CrawlModelPacket(
        prompt=prompt,
        sources=[{"path": "source.md", "content": "grounded fact"}],
        release_profile=release_profile(),
        credential_file="/private/api-key",
        admitted_at=admitted_at or datetime.now(UTC),
        workflow_id=workflow_id or _uuid7(),
        request_digest="a" * 64,
    )


def _audit(**overrides: object) -> ProviderAudit:
    values: dict[str, object] = {
        "client_request_id": "0198be50-0000-7000-8000-000000000000",
        "provider_request_id": "req_1",
        "response_id": "resp_1",
        "requested_model": "gpt-5.6-sol",
        "returned_model": "gpt-5.6-sol",
        "status": "completed",
        "input_tokens": 100,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 20,
        "reasoning_tokens": 5,
        "total_tokens": 120,
        "cost_upper_bound_micros": 1_100,
        "request_body_digest": "b" * 64,
        "output_digest": "c" * 64,
        "validated_result_digest": "d" * 64,
        "started_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC),
    }
    values.update(overrides)
    return ProviderAudit.model_validate(values)


def _recorded_audit(result: dict[str, object]) -> ProviderAudit:
    brief = EvidenceBrief.model_validate(result)
    audit = _audit(validated_result_digest=canonical_digest(result))
    return audit.model_copy(update={"record_digest": provider_record_digest(brief, audit)})


def _effect(state: str, dispatch: dict[str, object], **overrides: object) -> Effect:
    values: dict[str, object] = {
        "workflow_id": str(dispatch["workflow_id"]),
        "request_digest": str(dispatch["request_digest"]),
        "dispatch_digest": "e" * 64,
        "state": state,
        "dispatch": dispatch,
        "result": None,
        "audit": None,
    }
    values.update(overrides)
    return Effect(**values)  # type: ignore[arg-type]


def _reserve(state: str = "reserved", **overrides: object):
    def reserve(dispatch: dict[str, object], _digest: str) -> Effect:
        return _effect(state, dispatch, **overrides)

    return reserve


def _transition(
    workflow_id: str,
    _expected: str,
    state: str,
    **kwargs: object,
) -> Effect:
    return Effect(
        workflow_id=workflow_id,
        request_digest="a" * 64,
        dispatch_digest="e" * 64,
        state=state,
        dispatch={"workflow_id": workflow_id, "request_digest": "a" * 64},
        result=kwargs.get("result") if isinstance(kwargs.get("result"), dict) else None,
        audit=kwargs.get("audit") if isinstance(kwargs.get("audit"), dict) else None,
    )


class FakeAdapter:
    request_body: dict[str, object] | None = None
    dispatch: object = None

    def __init__(self, _profile: object, _credential: Path) -> None:
        pass

    async def generate(
        self, dispatch: object, request_body: dict[str, object]
    ) -> ProviderResult:
        type(self).request_body = request_body
        type(self).dispatch = dispatch
        return ProviderResult(
            brief=EvidenceBrief(
                answer="Grounded.",
                citations=[Citation(path="source.md", line_start=1, line_end=1, quote="wrong")],
                uncertainties=[],
                next_decisions=[],
            ),
            audit=_audit(
                request_body_digest=request_body["model"] and dispatch.request_body_digest
            ),
        )


def _run(packet: _CrawlModelPacket, *, adapter_factory: object) -> tuple[EvidenceBrief, object]:
    return asyncio.run(_run_inference(packet, adapter_factory=adapter_factory))


class WorkflowTests(unittest.TestCase):
    def test_queue_agent_and_retry_contract_are_fixed(self) -> None:
        self.assertEqual(crawl_observe_queue.concurrency, 1)
        self.assertEqual(crawl_observe_queue.worker_concurrency, 1)
        self.assertIsInstance(_crawl_agent, Agent)
        self.assertIsInstance(_crawl_durability, DBOSDurability)
        self.assertEqual(_crawl_durability._model_step_config, {"retries_allowed": False})

    def test_success_uses_gpt56_medium_exact_body_and_persists_usage(self) -> None:
        with (
            patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
        ):
            brief, usage = _run(_packet(), adapter_factory=FakeAdapter)

        self.assertEqual(brief.citations[0].quote, "grounded fact")
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.details["reasoning_output_tokens"], 5)
        body = FakeAdapter.request_body
        self.assertIsNotNone(body)
        self.assertEqual(body["model"], "gpt-5.6-sol")
        self.assertEqual(body["reasoning"], {"effort": "medium"})
        self.assertEqual(body["tools"], [])
        self.assertEqual(body["tool_choice"], "none")
        self.assertFalse(body["store"])
        self.assertFalse(body["stream"])
        self.assertEqual(
            [call.args[2] for call in transition.call_args_list],
            ["dispatching", "returned", "reconciled"],
        )
        returned = transition.call_args_list[1]
        self.assertEqual(
            returned.kwargs["audit"]["validated_result_digest"],
            canonical_digest(returned.kwargs["result"]),
        )
        self.assertEqual(returned.kwargs["result"]["citations"][0]["quote"], "grounded fact")

    def test_replay_returns_recorded_result_and_exact_usage_without_adapter(self) -> None:
        recorded = EvidenceBrief(
            answer="Grounded.",
            citations=[Citation(path="source.md", line_start=1, line_end=1, quote="grounded fact")],
            uncertainties=[],
            next_decisions=[],
        ).model_dump(mode="json")
        factory = Mock()
        with patch(
            "glupta_agi.workflow.reserve",
            side_effect=_reserve(
                "reconciled",
                result=recorded,
                audit=_recorded_audit(recorded).model_dump(mode="json"),
            ),
        ):
            brief, usage = _run(_packet(), adapter_factory=factory)
        self.assertEqual(brief.answer, "Grounded.")
        self.assertEqual(usage.output_tokens, 20)
        self.assertEqual(usage.details["cost_upper_bound_micros"], 1_100)
        factory.assert_not_called()

    def test_replay_rejects_result_or_audit_digest_tampering_without_adapter(self) -> None:
        recorded = EvidenceBrief(
            answer="Grounded.",
            citations=[Citation(path="source.md", line_start=1, line_end=1, quote="grounded fact")],
            uncertainties=[],
            next_decisions=[],
        ).model_dump(mode="json")
        factory = Mock()
        for result, digest in (
            ({**recorded, "answer": "tampered"}, canonical_digest(recorded)),
            (recorded, "f" * 64),
        ):
            with (
                self.subTest(result=result, digest=digest),
                patch(
                    "glupta_agi.workflow.reserve",
                    side_effect=_reserve(
                        "reconciled",
                        result=result,
                        audit=_recorded_audit(recorded).model_copy(
                            update={"validated_result_digest": digest}
                        ).model_dump(mode="json"),
                    ),
                ),
                self.assertRaisesRegex(BriefGenerationError, "failed validation"),
            ):
                _run(_packet(), adapter_factory=factory)
        factory.assert_not_called()

    def test_queue_deadline_uses_server_admission_not_caller_uuid_time(self) -> None:
        admitted_at = datetime.now(UTC) - timedelta(seconds=1)
        future_uuid = "ffffffff-ffff-7fff-bfff-ffffffffffff"
        with (
            patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
            patch("glupta_agi.workflow.transition", side_effect=_transition),
        ):
            _run(
                _packet(workflow_id=future_uuid, admitted_at=admitted_at),
                adapter_factory=FakeAdapter,
            )
        self.assertEqual(
            FakeAdapter.dispatch.queue_deadline,
            admitted_at + timedelta(seconds=300),
        )

    def test_ambiguous_recovery_never_redispatches(self) -> None:
        factory = Mock()
        with (
            patch("glupta_agi.workflow.reserve", side_effect=_reserve("dispatching")),
            patch(
                "glupta_agi.workflow.hold_unknown",
                side_effect=AmbiguousEffectError("manual reconciliation required"),
            ),
            self.assertRaises(AmbiguousEffectError),
        ):
            _run(_packet(), adapter_factory=factory)
        factory.assert_not_called()

    def test_expired_queue_and_oversized_prompt_reject_before_adapter(self) -> None:
        factory = Mock()
        with (
            patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
            self.assertRaisesRegex(BriefGenerationError, "queue deadline"),
        ):
            _run(
                _packet(admitted_at=datetime.now(UTC) - timedelta(seconds=301)),
                adapter_factory=factory,
            )
        factory.assert_not_called()
        self.assertEqual(transition.call_args.args[2], "failed")

        for invalid_admission in (
            datetime.now() + timedelta(seconds=10),
            datetime.now(UTC) + timedelta(seconds=10),
        ):
            with (
                self.subTest(admitted_at=invalid_admission),
                patch("glupta_agi.workflow.reserve") as reserve,
                self.assertRaisesRegex(BriefGenerationError, "admission timestamp"),
            ):
                _run(
                    _packet(admitted_at=invalid_admission),
                    adapter_factory=factory,
                )
            reserve.assert_not_called()

        with (
            patch("glupta_agi.workflow.reserve") as reserve,
            self.assertRaisesRegex(BriefGenerationError, "input-token"),
        ):
            _run(_packet(prompt="x" * 280_000), adapter_factory=factory)
        reserve.assert_not_called()

    def test_ambiguous_provider_failure_is_redacted_and_sticky(self) -> None:
        sentinel = "RAW_PROVIDER_MARKER"

        class FailingAdapter(FakeAdapter):
            async def generate(
                self, _dispatch: object, _body: dict[str, object]
            ) -> ProviderResult:
                raise ProviderAmbiguousError(sentinel)

        def hold(_effect: Effect, reason: str) -> None:
            self.assertEqual(reason, "provider_outcome_ambiguous")
            raise AmbiguousEffectError("manual reconciliation required") from None

        with (
            patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
            patch("glupta_agi.workflow.transition", side_effect=_transition),
            patch("glupta_agi.workflow.hold_unknown", side_effect=hold),
            self.assertRaises(AmbiguousEffectError) as caught,
        ):
            _run(_packet(), adapter_factory=FailingAdapter)
        self.assertNotIn(sentinel, "".join(traceback.format_exception(caught.exception)))

    def test_definitive_rejection_is_failed_without_retry(self) -> None:
        class RejectingAdapter(FakeAdapter):
            async def generate(
                self, _dispatch: object, _body: dict[str, object]
            ) -> ProviderResult:
                raise ProviderRejectedError("invalid output", _audit())

        with (
            patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
            self.assertRaisesRegex(BriefGenerationError, "rejected"),
        ):
            _run(_packet(), adapter_factory=RejectingAdapter)
        self.assertEqual(transition.call_args.args[2], "failed")
        self.assertIsNotNone(transition.call_args.kwargs["audit"])
