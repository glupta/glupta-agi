from __future__ import annotations

import asyncio
import inspect
import tempfile
import traceback
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from httpx import Request, Response
from openai import APIStatusError
from pydantic_ai import Agent
from pydantic_ai.durable_exec.dbos import DBOSDurability
from pydantic_ai.messages import ModelRequest, UserPromptPart

from glupta_agi.contracts import (
    DISCLOSURE_NOTICE_DIGEST,
    Citation,
    EvidenceBrief,
    ProviderAudit,
    ProviderResult,
    canonical_digest,
    provider_record_digest,
)
from glupta_agi.effects import AmbiguousEffectError, Effect
from glupta_agi.inference import (
    FrozenDispatch,
)
from glupta_agi.intake import admit_inline_request
from glupta_agi.openai_adapter import (
    OpenAIResponsesAdapter,
    ProviderAmbiguousError,
    ProviderRejectedError,
)
from glupta_agi.workflow import (
    BriefGenerationError,
    _crawl_agent,
    _crawl_durability,
    _crawl_model,
    _CrawlModelPacket,
    _run_inference,
    crawl_observe_queue,
    evidence_brief_workflow,
)
from tests.helpers import private_file, release_profile

_WORKFLOW_ID = "0198be50-0000-7000-8000-000000000000"


def _admitted(
    question: str = "question", source_content: str = "grounded fact"
) -> dict[str, object]:
    return admit_inline_request(
        question=question,
        sources=[{"path": "source.md", "content": source_content}],
        disclosure_profile="external_disclosed_v1",
        disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
        external_disclosure_ack=True,
    ).workflow_payload()


_REQUEST_DIGEST = str(_admitted()["request_digest"])


def _packet(
    *,
    prompt: str = "question",
    workflow_id: str | None = None,
    admitted_at: datetime | None = None,
    credential_file: str = "/private/api-key",
    source_content: str = "grounded fact",
) -> _CrawlModelPacket:
    return _CrawlModelPacket(
        admitted_request=_admitted(prompt, source_content),
        release_profile=release_profile(),
        credential_file=credential_file,
        credential_generation=1,
        admitted_at=admitted_at or datetime.now(UTC),
        workflow_id=workflow_id or _WORKFLOW_ID,
    )


def _audit(**overrides: object) -> ProviderAudit:
    values: dict[str, object] = {
        "workflow_id": _WORKFLOW_ID,
        "request_digest": _REQUEST_DIGEST,
        "release_profile_digest": release_profile().digest(),
        "client_request_id": "0198be50-0000-7000-8000-000000000000",
        "provider_request_id": "req_1",
        "response_id": "resp_1",
        "requested_model": "gpt-5.6-sol",
        "returned_model": "gpt-5.6-sol",
        "service_tier": "default",
        "status": "completed",
        "input_tokens": 100,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 20,
        "reasoning_tokens": 5,
        "total_tokens": 120,
        "cost_upper_bound_micros": 1_225,
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

    def __init__(self, _profile: object, _credential: Path, *, credential_generation: int) -> None:
        if credential_generation != 1:
            raise ValueError
        pass

    async def generate(
        self, dispatch: FrozenDispatch, request_body: dict[str, object]
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
                workflow_id=dispatch.workflow_id,
                request_digest=dispatch.request_digest,
                release_profile_digest=dispatch.release_profile_digest,
                request_body_digest=request_body["model"] and dispatch.request_body_digest,
            ),
        )


def _run(packet: _CrawlModelPacket, *, adapter_factory: object) -> tuple[EvidenceBrief, object]:
    return asyncio.run(_run_inference(packet, adapter_factory=adapter_factory))


def _assert_product_frames_sanitized(error: BaseException, *markers: str) -> None:
    current: BaseException | None = error
    while current is not None:
        self_case = unittest.TestCase()
        self_case.assertIsNone(current.__context__)
        self_case.assertIsNone(current.__cause__)
        traceback_cursor = current.__traceback__
        while traceback_cursor is not None:
            frame = traceback_cursor.tb_frame
            if "/src/glupta_agi/" in frame.f_code.co_filename:
                captured_locals = repr(frame.f_locals)
                for marker in markers:
                    self_case.assertNotIn(marker, captured_locals)
            traceback_cursor = traceback_cursor.tb_next
        current = current.__cause__ or current.__context__


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
            result, usage = _run(_packet(), adapter_factory=FakeAdapter)

        self.assertEqual(result.brief.citations[0].quote, "grounded fact")
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.details["reasoning_output_tokens"], 5)
        body = FakeAdapter.request_body
        self.assertIsNotNone(body)
        self.assertEqual(body["model"], "gpt-5.6-sol")
        self.assertEqual(body["reasoning"], {"effort": "medium"})
        self.assertEqual(body["service_tier"], "default")
        self.assertEqual(body["tools"], [])
        self.assertEqual(body["tool_choice"], "none")
        self.assertFalse(body["store"])
        self.assertFalse(body["stream"])
        self.assertEqual(
            [call.args[2] for call in transition.call_args_list],
            ["dispatching", "reconciled"],
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
            result, usage = _run(_packet(), adapter_factory=factory)
        self.assertEqual(result.brief.answer, "Grounded.")
        self.assertEqual(usage.output_tokens, 20)
        self.assertEqual(usage.details["cost_upper_bound_micros"], 1_225)
        factory.assert_not_called()

    def test_initial_and_replay_public_results_return_identical_bound_audit(self) -> None:
        brief = EvidenceBrief(
            answer="Grounded.",
            citations=[Citation(path="source.md", line_start=1, line_end=1, quote="grounded fact")],
            uncertainties=[],
            next_decisions=[],
        )
        provider_result = ProviderResult(
            brief=brief, audit=_recorded_audit(brief.model_dump(mode="json"))
        )
        payload = _admitted()
        with patch.object(
            _crawl_agent, "run", new=AsyncMock(return_value=SimpleNamespace(output=provider_result))
        ):
            responses = [
                asyncio.run(
                    inspect.unwrap(evidence_brief_workflow)(
                        payload,
                        _WORKFLOW_ID,
                        release_profile().model_dump(mode="json"),
                        "/private/key",
                        1,
                        datetime.now(UTC).isoformat(),
                    )
                )
                for _ in range(2)
            ]
        self.assertEqual(responses[0], responses[1])
        self.assertEqual(responses[0]["provider_audit"]["provider_request_id"], "req_1")
        self.assertEqual(responses[0]["provider_audit"]["cost_upper_bound_micros"], 1_225)

    def test_public_workflow_exception_drops_admitted_payload_traceback_locals(self) -> None:
        marker = "RAW_ADMITTED_SOURCE_BYTES"
        with (
            patch.object(_crawl_agent, "run", new=AsyncMock(
                side_effect=BriefGenerationError("provider response was rejected"))),
            self.assertRaises(BriefGenerationError) as caught,
        ):
            asyncio.run(inspect.unwrap(evidence_brief_workflow)(
                _admitted(source_content=marker), _WORKFLOW_ID,
                release_profile().model_dump(mode="json"), "/private/key", 1,
                datetime.now(UTC).isoformat()))
        _assert_product_frames_sanitized(caught.exception, marker)

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
                        audit=_recorded_audit(recorded)
                        .model_copy(update={"validated_result_digest": digest})
                        .model_dump(mode="json"),
                    ),
                ),
                self.assertRaisesRegex(BriefGenerationError, "failed validation"),
            ):
                _run(_packet(), adapter_factory=factory)
        factory.assert_not_called()

    def test_replay_rejects_non_integer_subset_and_cost_inconsistency_without_adapter(self) -> None:
        recorded = EvidenceBrief(
            answer="Grounded.",
            citations=[Citation(path="source.md", line_start=1, line_end=1, quote="grounded fact")],
            uncertainties=[],
            next_decisions=[],
        ).model_dump(mode="json")
        brief = EvidenceBrief.model_validate(recorded)
        factory = Mock()
        for mutation in (
            {"input_tokens": True, "total_tokens": 21},
            {"reasoning_tokens": 21},
            {"cached_input_tokens": 60, "cache_write_input_tokens": 60},
            {"cost_upper_bound_micros": 1},
            {"service_tier": "priority"},
        ):
            audit = _recorded_audit(recorded).model_copy(update=mutation)
            audit = audit.model_copy(update={"record_digest": provider_record_digest(brief, audit)})
            with (
                self.subTest(mutation=mutation),
                patch(
                    "glupta_agi.workflow.reserve",
                    side_effect=_reserve(
                        "reconciled", result=recorded, audit=audit.model_dump(mode="json")
                    ),
                ),
                self.assertRaisesRegex(BriefGenerationError, "failed validation"),
            ):
                _run(_packet(), adapter_factory=factory)
        factory.assert_not_called()

    def test_disclosure_digest_and_credential_generation_are_reverified_before_effect(self) -> None:
        packet = _packet()
        admitted = packet.admitted_request
        mutations = (
            {**admitted, "disclosure_profile": "local_only"},
            {**admitted, "disclosure_notice_digest": "0" * 64},
            {**admitted, "external_disclosure_ack": False},
            {**admitted, "request_digest": "f" * 64},
            {
                **admitted,
                "sources": [{**admitted["sources"][0], "content": "changed"}],
            },
        )
        factory = Mock()
        for mutation in mutations:
            with (
                self.subTest(mutation=mutation),
                patch("glupta_agi.workflow.reserve") as reserve,
                self.assertRaisesRegex(BriefGenerationError, "admitted request"),
            ):
                _run(
                    packet.model_copy(update={"admitted_request": mutation}),
                    adapter_factory=factory,
                )
            reserve.assert_not_called()
        with (
            patch("glupta_agi.workflow.reserve") as reserve,
            self.assertRaisesRegex(BriefGenerationError, "credential generation"),
        ):
            _run(packet.model_copy(update={"credential_generation": 2}), adapter_factory=factory)
        reserve.assert_not_called()
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
        for state in ("dispatching", "returned", "unknown"):
            with (
                self.subTest(state=state),
                patch("glupta_agi.workflow.reserve", side_effect=_reserve(state)),
                patch(
                    "glupta_agi.workflow.hold_unknown",
                    side_effect=AmbiguousEffectError("manual reconciliation required"),
                ),
                self.assertRaises(AmbiguousEffectError),
            ):
                _run(_packet(), adapter_factory=factory)
        factory.assert_not_called()

    def test_persistence_fault_boundaries_never_redispatch(self) -> None:
        def scenario(fault: str) -> None:
            store: dict[str, object] = {"state": "reserved", "calls": 0, "fault": fault}

            class CountingAdapter(FakeAdapter):
                async def generate(
                    self, dispatch: FrozenDispatch, request_body: dict[str, object]
                ) -> ProviderResult:
                    store["calls"] = int(store["calls"]) + 1
                    return await super().generate(dispatch, request_body)

            def reserve_effect(dispatch: dict[str, object], digest: str) -> Effect:
                result = store.get("result")
                audit = store.get("audit")
                return Effect(
                    workflow_id=str(dispatch["workflow_id"]),
                    request_digest=str(dispatch["request_digest"]),
                    dispatch_digest=digest,
                    state=str(store["state"]),
                    dispatch=dispatch,
                    result=result if isinstance(result, dict) else None,
                    audit=audit if isinstance(audit, dict) else None,
                )

            def persist(workflow_id: str, expected: str, state: str, **kwargs: object) -> Effect:
                self.assertEqual(store["state"], expected)
                if expected == "dispatching" and store["fault"]:
                    if str(store["fault"]).startswith("after_"):
                        store.update(state=state, result=kwargs["result"], audit=kwargs["audit"])
                        if store["fault"] == "after_tampered_commit":
                            store["audit"] = {**store["audit"], "response_id": "tampered"}
                    store["fault"] = None
                    raise RuntimeError("ambiguous commit acknowledgement")
                store.update(state=state, result=kwargs.get("result"), audit=kwargs.get("audit"))
                return reserve_effect(
                    {"workflow_id": workflow_id, "request_digest": "a" * 64}, "e" * 64
                )

            def hold(_workflow_id: str, _reason: str, **_kwargs: object) -> None:
                store["state"] = "unknown"
                raise AmbiguousEffectError("manual reconciliation required")

            with (
                patch("glupta_agi.workflow.reserve", side_effect=reserve_effect),
                patch("glupta_agi.workflow.transition", side_effect=persist),
                patch("glupta_agi.workflow.hold_unknown", side_effect=hold),
            ):
                if fault != "after_commit":
                    with self.assertRaises(AmbiguousEffectError):
                        _run(_packet(), adapter_factory=CountingAdapter)
                    with self.assertRaises(AmbiguousEffectError):
                        _run(_packet(), adapter_factory=CountingAdapter)
                else:
                    first, _ = _run(_packet(), adapter_factory=CountingAdapter)
                    second, _ = _run(_packet(), adapter_factory=CountingAdapter)
                    self.assertEqual(first, second)
            self.assertEqual(store["calls"], 1)

        for fault in ("before_commit", "after_commit", "after_tampered_commit"):
            with self.subTest(fault=fault):
                scenario(fault)

    def test_ambiguous_model_step_returns_checkpointable_unknown_sentinel(self) -> None:
        message = ModelRequest(parts=[UserPromptPart(_packet().model_dump_json())])
        with patch(
            "glupta_agi.workflow._run_inference",
            side_effect=AmbiguousEffectError("manual reconciliation required"),
        ):
            response = asyncio.run(_crawl_model([message], Mock()))
        self.assertEqual(response.parts[0].content, '"unknown"')

    def test_definitive_model_step_exception_drops_raw_packet_traceback_locals(self) -> None:
        marker = "RAW_ADMITTED_SOURCE_BYTES"
        message = ModelRequest(parts=[UserPromptPart(
            _packet(source_content=marker).model_dump_json())])
        with (
            patch("glupta_agi.workflow._run_inference",
                  side_effect=BriefGenerationError("provider response was rejected")),
            self.assertRaises(BriefGenerationError) as caught,
        ):
            asyncio.run(_crawl_model([message], Mock()))
        _assert_product_frames_sanitized(caught.exception, marker)

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
            _run(
                _packet(prompt="x" * 32_000, source_content="y" * (256 * 1024)),
                adapter_factory=factory,
            )
        reserve.assert_not_called()

    def test_ambiguous_provider_failure_is_redacted_and_sticky(self) -> None:
        sentinel = "RAW_PROVIDER_MARKER"
        source_marker = "RAW_ADMITTED_SOURCE_BYTES"

        class FailingAdapter(FakeAdapter):
            async def generate(self, _dispatch: object, _body: dict[str, object]) -> ProviderResult:
                raise ProviderAmbiguousError(sentinel)

        def hold(_workflow_id: str, reason: str, **_kwargs: object) -> None:
            self.assertEqual(reason, "provider_outcome_ambiguous")
            raise AmbiguousEffectError("manual reconciliation required") from None

        with (
            patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
            patch("glupta_agi.workflow.transition", side_effect=_transition),
            patch("glupta_agi.workflow.hold_unknown", side_effect=hold),
            self.assertRaises(AmbiguousEffectError) as caught,
        ):
            _run(_packet(source_content=source_marker), adapter_factory=FailingAdapter)
        self.assertNotIn(sentinel, "".join(traceback.format_exception(caught.exception)))
        _assert_product_frames_sanitized(caught.exception, sentinel, source_marker)

    def test_retryable_provider_status_routes_to_sticky_unknown(self) -> None:
        request = Request("POST", "https://api.openai.com/v1/responses")
        response = Response(429, request=request, headers={"x-request-id": "req_unknown"})
        status_error = APIStatusError(
            "RAW_PROVIDER_MARKER", response=response, body={"secret": "marker"}
        )

        class RejectingClient:
            def __init__(self) -> None:
                self.responses = self

            async def create(self, **_kwargs: object) -> None:
                raise status_error

            async def close(self) -> None:
                pass

        def hold(_workflow_id: str, reason: str, **_kwargs: object) -> None:
            self.assertEqual(reason, "provider_outcome_ambiguous")
            raise AmbiguousEffectError("manual reconciliation required") from None

        with tempfile.TemporaryDirectory() as temporary:
            key = private_file(Path(temporary), "api-key", "secret-api-key-" + "x" * 32)

            def factory(
                profile: object, credential_file: Path, *, credential_generation: int
            ) -> OpenAIResponsesAdapter:
                return OpenAIResponsesAdapter(
                    profile,
                    credential_file,
                    credential_generation=credential_generation,
                    client_factory=lambda **_kwargs: RejectingClient(),
                )

            with (
                patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
                patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
                patch("glupta_agi.workflow.hold_unknown", side_effect=hold),
                self.assertRaises(AmbiguousEffectError) as caught,
            ):
                _run(_packet(credential_file=str(key)), adapter_factory=factory)
        self.assertEqual(transition.call_count, 1)
        self.assertNotIn(
            "RAW_PROVIDER_MARKER", "".join(traceback.format_exception(caught.exception))
        )

    def test_definitive_rejection_is_failed_without_retry(self) -> None:
        class RejectingAdapter(FakeAdapter):
            async def generate(self, _dispatch: object, _body: dict[str, object]) -> ProviderResult:
                raise ProviderRejectedError("invalid output", _audit())

        with (
            patch("glupta_agi.workflow.reserve", side_effect=_reserve()),
            patch("glupta_agi.workflow.transition", side_effect=_transition) as transition,
            self.assertRaisesRegex(BriefGenerationError, "rejected"),
        ):
            _run(_packet(), adapter_factory=RejectingAdapter)
        self.assertEqual(transition.call_args.args[2], "failed")
        self.assertIsNotNone(transition.call_args.kwargs["audit"])

    def test_terminal_failure_persistence_boundaries_never_redispatch(self) -> None:
        def scenario(route: str, fault: str) -> None:
            reason = "provider_rejected" if route == "rejection" else "invalid_citation"
            store: dict[str, object] = {
                "state": "reserved",
                "audit": None,
                "reason": None,
                "fault": fault,
            }
            hold_reasons: list[str] = []

            class TerminalAdapter(FakeAdapter):
                calls = 0

                async def generate(
                    self, dispatch: FrozenDispatch, body: dict[str, object]
                ) -> ProviderResult:
                    type(self).calls += 1
                    if route == "rejection":
                        raise ProviderRejectedError("RAW_PROVIDER", _audit())
                    return await super().generate(dispatch, body)

            def reserve_effect(dispatch: dict[str, object], digest: str) -> Effect:
                if store.get("readback_fault") and TerminalAdapter.calls == 1:
                    store["readback_fault"] = False
                    raise RuntimeError("RAW_READBACK")
                return Effect(
                    workflow_id=str(dispatch["workflow_id"]),
                    request_digest=str(dispatch["request_digest"]),
                    dispatch_digest=digest,
                    state=str(store["state"]),
                    dispatch=dispatch,
                    result=None,
                    audit=store["audit"] if isinstance(store["audit"], dict) else None,
                    hold_reason=str(store["reason"]) if store["reason"] else None,
                )

            def persist(workflow_id: str, expected: str, state: str, **kwargs: object) -> Effect:
                self.assertEqual(store["state"], expected)
                if expected == "dispatching" and store["fault"]:
                    if fault in {"after_commit", "tampered_commit"}:
                        store.update(
                            state=state, audit=kwargs["audit"], reason=kwargs["hold_reason"]
                        )
                        if fault == "tampered_commit":
                            store["audit"] = {**store["audit"], "response_id": "tampered"}
                    if fault == "readback_failure":
                        store["readback_fault"] = True
                    store["fault"] = None
                    raise RuntimeError("RAW_TRANSITION")
                store.update(
                    state=state, audit=kwargs.get("audit"), reason=kwargs.get("hold_reason")
                )
                return reserve_effect(
                    {"workflow_id": workflow_id, "request_digest": "a" * 64}, "e" * 64
                )

            def hold(_workflow_id: str, hold_reason: str, **_kwargs: object) -> None:
                hold_reasons.append(hold_reason)
                if fault != "hold_failure":
                    store["state"] = "unknown"
                raise AmbiguousEffectError("manual reconciliation required") from None

            def exercise() -> None:
                error = BriefGenerationError if fault == "after_commit" else AmbiguousEffectError
                with self.assertRaises(error) as first:
                    _run(_packet(source_content="RAW_SOURCE"), adapter_factory=TerminalAdapter)
                with self.assertRaises(error):
                    _run(_packet(source_content="RAW_SOURCE"), adapter_factory=TerminalAdapter)
                self.assertNotIn("RAW_", "".join(traceback.format_exception(first.exception)))
                _assert_product_frames_sanitized(
                    first.exception, "RAW_PROVIDER", "RAW_SOURCE", "RAW_TRANSITION",
                    "RAW_READBACK",
                )

            with (
                patch("glupta_agi.workflow.reserve", side_effect=reserve_effect),
                patch("glupta_agi.workflow.transition", side_effect=persist),
                patch("glupta_agi.workflow.hold_unknown", side_effect=hold),
            ):
                if route == "invalid_citation":
                    with patch("glupta_agi.workflow.resolve_citations", side_effect=ValueError):
                        exercise()
                else:
                    exercise()
            self.assertEqual(TerminalAdapter.calls, 1)
            if fault != "after_commit":
                self.assertEqual(hold_reasons[0], f"{reason}_persistence_ambiguous")

        faults = (
            "before_commit",
            "after_commit",
            "tampered_commit",
            "readback_failure",
            "hold_failure",
        )
        for route in ("rejection", "invalid_citation"):
            for fault in faults:
                with self.subTest(route=route, fault=fault):
                    scenario(route, fault)
