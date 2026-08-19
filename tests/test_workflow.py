# ruff: noqa: S101
from __future__ import annotations

import asyncio
import inspect
import traceback
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


def _packet(source_content: str = "grounded fact", **changes: object) -> _CrawlModelPacket:
    admitted = admit_inline_request(
        question="question",
        sources=[{"path": "source.md", "content": source_content}],
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

    def __init__(self, _profile: object, _home: Path, *, auth_generation: int,
        phase_recorder: object) -> None:
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


class PreTurnAdapter(FakeAdapter):
    async def generate(self, *_args: object, **_kwargs: object) -> ProviderResult:
        type(self).calls += 1
        from glupta_agi.codex_adapter import AdapterError

        raise AdapterError("RAW_PRE_TURN")


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAdapter.calls = 0
        AmbiguousAdapter.calls = 0
        PreTurnAdapter.calls = 0

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
        for state, reason in (("dispatching", None),
            ("dispatching", "dispatch_phase:turn_invocation_started"),
            ("dispatching", "dispatch_phase:turn_returned"), ("returned", None),
            ("unknown", None)):
            with (
                self.subTest(state=state, reason=reason),
                patch("glupta_agi.workflow.reserve", side_effect=_reserve(
                    state, hold_reason=reason)),
                patch(
                    "glupta_agi.workflow.hold_unknown",
                    side_effect=AmbiguousEffectError("manual reconciliation"),
                ),
            ):
                with self.assertRaises(AmbiguousEffectError):
                    asyncio.run(_run_inference(_packet(), adapter_factory=FakeAdapter))
        self.assertEqual(FakeAdapter.calls, 0)

    def test_proven_pre_turn_failure_is_terminal(self) -> None:
        with (
            patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
            self.assertRaisesRegex(BriefGenerationError, "before turn invocation"),
        ):
            asyncio.run(_run_inference(_packet(), adapter_factory=PreTurnAdapter))
        self.assertEqual(PreTurnAdapter.calls, 1)
        self.assertEqual(transition.call_args_list[-1].args[2], "failed")
        self.assertEqual(transition.call_args_list[-1].kwargs["hold_reason"], "pre_turn_failure")

    def test_each_recorded_pre_turn_phase_recovers_without_redispatch(self) -> None:
        for phase in ("adapter_construction_started", "account_lookup_started",
            "model_catalog_started", "thread_start_started"):
            with (
                self.subTest(phase=phase),
                patch("glupta_agi.workflow.reserve", side_effect=_reserve(
                    "dispatching", hold_reason=f"dispatch_phase:{phase}")),
                patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
                self.assertRaisesRegex(BriefGenerationError, "before turn invocation"),
            ):
                asyncio.run(_run_inference(_packet(), adapter_factory=FakeAdapter))
            self.assertEqual(transition.call_args_list[-1].args[2], "failed")
            self.assertEqual(
                transition.call_args_list[-1].kwargs["hold_reason"], "pre_turn_recovery"
            )
        self.assertEqual(FakeAdapter.calls, 0)

    def test_adapter_construction_failure_is_sanitized_terminal(self) -> None:
        def broken_factory(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("RAW_CONSTRUCTION")

        with (
            patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
            self.assertRaisesRegex(BriefGenerationError, "before turn invocation") as caught,
        ):
            asyncio.run(_run_inference(_packet(), adapter_factory=broken_factory))
        self.assertNotIn("RAW_CONSTRUCTION", str(caught.exception))
        self.assertEqual(transition.call_args_list[-1].args[2], "failed")

    def test_denied_ambient_provider_authority_is_terminal_before_client(self) -> None:
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "RAW_DENIED_AUTHORITY"}, clear=True),
            patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
            self.assertRaisesRegex(BriefGenerationError, "before turn invocation") as caught,
        ):
            asyncio.run(_run_inference(_packet()))
        self.assertNotIn("RAW_DENIED_AUTHORITY", str(caught.exception))
        self.assertEqual(transition.call_args_list[-1].args[2], "failed")

    def test_pre_turn_recovery_lost_ack_reads_definitive_failure_once(self) -> None:
        packet, reservations, writes = _packet(), 0, 0

        def reserve(dispatch: dict[str, object], _digest: str) -> Effect:
            nonlocal reservations
            reservations += 1
            return _effect("dispatching" if reservations == 1 else "failed", dispatch,
                hold_reason="dispatch_phase:thread_start_started" if reservations == 1
                else "pre_turn_recovery")

        def transition(*_args: object, **_kwargs: object) -> Effect:
            nonlocal writes
            writes += 1
            raise RuntimeError("RAW_LOST_ACK")

        with (
            patch("glupta_agi.workflow.reserve", side_effect=reserve),
            patch("glupta_agi.workflow.transition", side_effect=transition),
            patch("glupta_agi.workflow.hold_unknown") as hold,
            self.assertRaisesRegex(BriefGenerationError, "before turn invocation"),
        ):
            asyncio.run(_run_inference(packet, adapter_factory=FakeAdapter))
        self.assertEqual((FakeAdapter.calls, writes), (0, 1))
        hold.assert_not_called()

    def test_initial_phase_write_faults_are_sanitized_and_never_dispatch(self) -> None:
        for readback in ("reserved", "dispatching", "mismatched", "unavailable"):
            packet = _packet(source_content="ADMITTED_SOURCE_SECRET")
            reservations = writes = 0
            terminal = "failed" if readback in {"reserved", "dispatching"} else "unknown"

            def reserve(dispatch: dict[str, object], _digest: str, *, mode: str = readback,
                final: str = terminal) -> Effect:
                nonlocal reservations
                reservations += 1
                if reservations == 1:
                    return _effect("reserved", dispatch)
                if reservations == 2 and mode == "unavailable":
                    raise RuntimeError("RAW_READBACK_SECRET")
                if reservations == 2 and mode != "reserved":
                    phase = "adapter_construction_started" if mode == "dispatching" else (
                        "turn_invocation_started"
                    )
                    return _effect("dispatching", dispatch, hold_reason=f"dispatch_phase:{phase}")
                return _effect(final if reservations > 2 else "reserved", dispatch,
                    hold_reason="pre_turn_failure" if final == "failed" else
                    "initial_phase_persistence_ambiguous")

            def transition(workflow_id: str, expected: str, state: str,
                **kwargs: object) -> Effect:
                nonlocal writes
                writes += 1
                if writes == 1:
                    raise RuntimeError("RAW_INITIAL_PHASE_SECRET")
                return _transition(workflow_id, expected, state, **kwargs)

            hold = patch("glupta_agi.workflow.hold_unknown",
                side_effect=AmbiguousEffectError("manual reconciliation"))
            with self.subTest(readback=readback), patch(
                "glupta_agi.workflow.reserve", side_effect=reserve
            ), patch("glupta_agi.workflow.transition", side_effect=transition), hold as held:
                expected = BriefGenerationError if terminal == "failed" else AmbiguousEffectError
                try:
                    asyncio.run(_run_inference(packet,
                        adapter_factory=lambda *_a, **_k: self.fail("adapter constructed")))
                except expected as caught:
                    captured_error = caught
                else:
                    self.fail(f"{expected.__name__} not raised")
                self.assertIsNone(captured_error.__cause__)
                self.assertIsNone(captured_error.__context__)
                product_frames: list[str] = []
                cursor = captured_error.__traceback__
                while cursor is not None:
                    if "/src/glupta_agi/" in cursor.tb_frame.f_code.co_filename:
                        product_frames.append(cursor.tb_frame.f_code.co_name)
                        captured = traceback.TracebackException(
                            type(captured_error), captured_error, cursor, capture_locals=True)
                        for marker in ("RAW_", "ADMITTED_SOURCE_SECRET"):
                            self.assertNotIn(marker, repr(cursor.tb_frame.f_locals))
                            self.assertNotIn(marker, repr(captured.stack[0].locals))
                            self.assertNotIn(marker, "".join(captured.format()))
                    cursor = cursor.tb_next
                self.assertEqual(product_frames, ["_run_inference"])
                if terminal == "failed":
                    held.assert_not_called()
                    self.assertEqual(writes, 2)
                else:
                    held.assert_called_once()
                with self.assertRaises(expected):
                    asyncio.run(_run_inference(packet,
                        adapter_factory=lambda *_a, **_k: self.fail("replay dispatched")))

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
