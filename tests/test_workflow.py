# ruff: noqa: S101
from __future__ import annotations

import asyncio
import inspect
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from glupta_agi.contracts import (
    DISCLOSURE_NOTICE_DIGEST,
    Citation,
    EvidenceBrief,
    ProviderResult,
    canonical_digest,
)
from glupta_agi.effects import AmbiguousEffectError, Effect
from glupta_agi.inference import FrozenDispatch
from glupta_agi.intake import admit_inline_request
from glupta_agi.workflow import (
    AmbiguousResult,
    BriefGenerationError,
    _crawl_model_step,
    _CrawlModelPacket,
    _evidence_brief_workflow_sensitive,
    _run_inference,
    crawl_observe_queue,
)
from tests.helpers import provider_audit, release_profile

WORKFLOW_ID = "0198be50-0000-7000-8000-000000000000"


def _packet(**changes: object) -> _CrawlModelPacket:
    admitted = admit_inline_request(
        question="question",
        sources=[{"path": "source.md", "content": "grounded fact"}],
        disclosure_profile="external_disclosed_v1",
        disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
        external_disclosure_ack=True,
    )
    values = {
        "admitted_request": admitted.workflow_payload(),
        "release_profile": release_profile(),
        "codex_home": "/private/codex",
        "auth_generation": 1,
        "admitted_at": datetime.now(UTC),
        "workflow_id": WORKFLOW_ID,
    }
    values.update(changes)
    return _CrawlModelPacket.model_validate(values)


def _effect(state: str, dispatch: dict[str, object], **changes: object) -> Effect:
    values = {
        "workflow_id": str(dispatch["workflow_id"]),
        "request_digest": str(dispatch["request_digest"]),
        "dispatch_digest": "e" * 64,
        "state": state,
        "dispatch": dispatch,
        "result": None,
        "audit": None,
        "hold_reason": None,
    }
    values.update(changes)
    return Effect(**values)  # type: ignore[arg-type]


def _reserve(state: str = "reserved", **changes: object):
    return lambda dispatch, _digest: _effect(state, dispatch, **changes)


def _transition(workflow_id: str, _expected: str, state: str, **kwargs: object) -> Effect:
    return Effect(
        workflow_id=workflow_id,
        request_digest="a" * 64,
        dispatch_digest="e" * 64,
        state=state,
        dispatch={"workflow_id": workflow_id, "request_digest": "a" * 64},
        result=kwargs.get("result") if isinstance(kwargs.get("result"), dict) else None,
        audit=kwargs.get("audit") if isinstance(kwargs.get("audit"), dict) else None,
        hold_reason=kwargs.get("hold_reason")
        if isinstance(kwargs.get("hold_reason"), str)
        else None,
    )


class FakeAdapter:
    calls = 0
    dispatch: FrozenDispatch | None = None
    body: dict[str, object] | None = None

    def __init__(self, _profile: object, _home: Path, *, auth_generation: int) -> None:
        assert auth_generation == 1

    async def generate(
        self, dispatch: FrozenDispatch, request_body: dict[str, object]
    ) -> ProviderResult:
        type(self).calls += 1
        type(self).dispatch, type(self).body = dispatch, request_body
        brief = EvidenceBrief(
            answer="Grounded.",
            citations=[Citation(path="source.md", line_start=1, line_end=1, quote="grounded fact")],
            uncertainties=[],
            next_decisions=[],
        )
        audit = provider_audit(
            brief,
            workflow_id=dispatch.workflow_id,
            request_digest=dispatch.request_digest,
            release_profile_digest=dispatch.release_profile_digest,
            request_body_digest=dispatch.request_body_digest,
        )
        return ProviderResult(brief=brief, audit=audit)


class AmbiguousAdapter(FakeAdapter):
    async def generate(
        self, dispatch: FrozenDispatch, request_body: dict[str, object]
    ) -> ProviderResult:
        type(self).calls += 1
        type(self).dispatch, type(self).body = dispatch, request_body
        from glupta_agi.codex_adapter import ProviderAmbiguousError

        raise ProviderAmbiguousError("synthetic ambiguous turn")


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAdapter.calls = 0
        AmbiguousAdapter.calls = 0

    def test_queue_step_and_retry_contract_are_fixed(self) -> None:
        self.assertEqual(
            (crawl_observe_queue.concurrency, crawl_observe_queue.worker_concurrency), (1, 1)
        )
        self.assertEqual(
            _crawl_model_step.dbos_function_name, "crawl_observe_model_v2"
        )
        self.assertIn(
            '@DBOS.step(name="crawl_observe_model_v2", retries_allowed=False)',
            inspect.getsource(_crawl_model_step),
        )

    def test_success_freezes_subscription_request_and_persists_exact_audit(self) -> None:
        with (
            patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
        ):
            result = asyncio.run(_run_inference(_packet(), adapter_factory=FakeAdapter))
        self.assertEqual(FakeAdapter.calls, 1)
        self.assertEqual(result.brief.citations[0].quote, "grounded fact")
        self.assertEqual(FakeAdapter.dispatch.subscription_plan, "pro")
        self.assertEqual(FakeAdapter.body["reasoning_effort"], "medium")
        self.assertEqual(FakeAdapter.body["sandbox"], "read-only")
        self.assertEqual(
            [call.args[2] for call in transition.call_args_list], ["dispatching", "reconciled"]
        )
        persisted = transition.call_args_list[-1].kwargs
        self.assertEqual(
            persisted["audit"]["validated_result_digest"], canonical_digest(persisted["result"])
        )

    def test_replay_of_reconciled_result_never_constructs_adapter(self) -> None:
        packet = _packet()
        brief = EvidenceBrief(
            answer="Grounded.",
            citations=[Citation(path="source.md", line_start=1, line_end=1, quote="grounded fact")],
            uncertainties=[],
            next_decisions=[],
        )
        audit = provider_audit(
            brief,
            workflow_id=WORKFLOW_ID,
            request_digest=str(packet.admitted_request["request_digest"]),
        )

        def reserve(dispatch: dict[str, object], _digest: str) -> Effect:
            bound = audit.model_copy(
                update={
                    "release_profile_digest": dispatch["release_profile_digest"],
                    "request_body_digest": dispatch["request_body_digest"],
                }
            )
            bound = bound.model_copy(update={"record_digest": None})
            from glupta_agi.contracts import provider_record_digest

            bound = bound.model_copy(update={"record_digest": provider_record_digest(brief, bound)})
            return _effect(
                "reconciled",
                dispatch,
                result=brief.model_dump(mode="json"),
                audit=bound.model_dump(mode="json"),
            )

        with patch("glupta_agi.workflow.reserve", side_effect=reserve):
            result = asyncio.run(
                _run_inference(
                    packet,
                    adapter_factory=lambda *_args, **_kwargs: self.fail("adapter constructed"),
                )
            )
        self.assertEqual(result.brief.answer, "Grounded.")

    def test_post_dispatch_ambiguity_is_sticky_and_never_redispatches(self) -> None:
        for state in ("dispatching", "returned", "unknown"):
            with (
                self.subTest(state=state),
                patch("glupta_agi.workflow.reserve", side_effect=_reserve(state)),
                patch(
                    "glupta_agi.workflow.hold_unknown",
                    side_effect=AmbiguousEffectError("manual reconciliation"),
                ),
            ):
                with self.assertRaises(AmbiguousEffectError):
                    asyncio.run(_run_inference(_packet(), adapter_factory=FakeAdapter))
        self.assertEqual(FakeAdapter.calls, 0)

    def test_model_step_checkpoints_structured_ambiguity_without_retry(self) -> None:
        with patch(
            "glupta_agi.workflow._run_inference",
            side_effect=AmbiguousEffectError("manual reconciliation"),
        ) as inference:
            result = asyncio.run(_crawl_model_step(_packet()))

        self.assertEqual(result, AmbiguousResult(kind="unknown"))
        inference.assert_awaited_once()

    def test_structured_ambiguity_becomes_the_sanitized_workflow_error(self) -> None:
        packet = _packet()

        async def ambiguous(*_args: object, **_kwargs: object) -> AmbiguousResult:
            return AmbiguousResult(kind="unknown")

        with (
            patch("glupta_agi.workflow._crawl_model_step", side_effect=ambiguous),
            self.assertRaisesRegex(AmbiguousEffectError, "manual reconciliation"),
        ):
            asyncio.run(_evidence_brief_workflow_sensitive(
                packet.admitted_request,
                packet.workflow_id,
                packet.release_profile.model_dump(mode="json"),
                packet.codex_home,
                packet.auth_generation,
                packet.admitted_at.isoformat(),
            ))

    def test_initial_ambiguity_and_replay_make_only_one_adapter_call(self) -> None:
        packet = _packet()
        reservation_count = 0

        def reserve(dispatch: dict[str, object], _digest: str) -> Effect:
            nonlocal reservation_count
            reservation_count += 1
            return _effect("reserved" if reservation_count == 1 else "unknown", dispatch)

        with (
            patch("glupta_agi.workflow.reserve", side_effect=reserve),
            patch("glupta_agi.workflow.transition", side_effect=_transition),
            patch(
                "glupta_agi.workflow.hold_unknown",
                side_effect=AmbiguousEffectError("manual reconciliation"),
            ),
        ):
            with self.assertRaises(AmbiguousEffectError):
                asyncio.run(_run_inference(packet, adapter_factory=AmbiguousAdapter))
            with self.assertRaises(AmbiguousEffectError):
                asyncio.run(_run_inference(packet, adapter_factory=AmbiguousAdapter))

        self.assertEqual(AmbiguousAdapter.calls, 1)

    def test_expired_queue_or_changed_auth_fails_before_dispatch(self) -> None:
        cases = (
            _packet(admitted_at=datetime.now(UTC) - timedelta(seconds=301)),
            _packet(auth_generation=2),
        )
        for packet in cases:
            with (
                self.subTest(packet=packet),
                patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
                patch("glupta_agi.workflow.transition", side_effect=_transition),
                self.assertRaises(BriefGenerationError),
            ):
                asyncio.run(_run_inference(packet, adapter_factory=FakeAdapter))
        self.assertEqual(FakeAdapter.calls, 0)
