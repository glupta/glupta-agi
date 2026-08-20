from __future__ import annotations

import asyncio
import json
import tempfile
import traceback
import unittest
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from glupta_agi.api import app, evidence_brief
from glupta_agi.contracts import (
    DISCLOSURE_NOTICE_DIGEST,
    EvidenceBrief,
    EvidenceBriefInlineRequest,
    EvidenceBriefRequest,
)
from glupta_agi.effects import AmbiguousEffectError
from glupta_agi.intake import admit_inline_request, load_request
from glupta_agi.settings import Settings, get_settings
from glupta_agi.workflow import BriefGenerationError, evidence_brief_workflow
from tests.helpers import codex_home, provider_audit, release_profile


def _assert_public_error_sanitized(
    case: unittest.TestCase, error: BaseException, *markers: str
) -> None:
    case.assertIsNone(error.__cause__)
    case.assertIsNone(error.__context__)
    captured = traceback.TracebackException.from_exception(error, capture_locals=True)
    product_frames: list[str] = []
    traceback_cursor = error.__traceback__
    while traceback_cursor is not None:
        frame = traceback_cursor.tb_frame
        if "/src/glupta_agi/" in frame.f_code.co_filename:
            product_frames.append(frame.f_code.co_name)
            captured_frame = next(
                item
                for item in captured.stack
                if item.filename == frame.f_code.co_filename
                and item.lineno == traceback_cursor.tb_lineno
            )
            for marker in markers:
                case.assertNotIn(marker, repr(frame.f_locals))
                case.assertNotIn(marker, repr(captured_frame.locals))
        traceback_cursor = traceback_cursor.tb_next
    for marker in markers:
        case.assertNotIn(marker, str(error))
        case.assertNotIn(marker, repr(vars(error)))
        case.assertNotIn(marker, "".join(traceback.format_exception(error)))
    case.assertEqual(product_frames, ["evidence_brief"])


class EvidenceBriefApiTests(unittest.IsolatedAsyncioTestCase):
    def test_disclosure_acknowledgement_requires_exact_true(self) -> None:
        common = {
            "question": "q",
            "disclosure_profile": "external_disclosed_v1",
            "disclosure_notice_digest": DISCLOSURE_NOTICE_DIGEST,
        }
        branches = (
            (EvidenceBriefRequest, {"files": ["source.md"]}),
            (EvidenceBriefInlineRequest,
             {"sources": [{"path": "source.md", "content": "approved"}]}),
        )
        for model, selection in branches:
            for acknowledgement in (1, 1.0, False, "true"):
                with self.subTest(model=model.__name__, acknowledgement=acknowledgement):
                    with self.assertRaises(ValueError):
                        model(**common, **selection,
                              external_disclosure_ack=acknowledgement)

    async def test_invalid_union_and_non_utf8_inline_text_are_bounded_before_effects(self) -> None:
        source_marker = "REJECTED_ASGI_SOURCE_MARKER"
        token_marker = "REJECTED_ASGI_TOKEN_MARKER_" + "t" * 32
        common = {
            "question": "What is grounded?",
            "disclosure_profile": "external_disclosed_v1",
            "disclosure_notice_digest": DISCLOSURE_NOTICE_DIGEST,
            "external_disclosure_ack": True,
        }
        cases = (
            (
                {
                    **common,
                    "files": ["source.md"],
                    "sources": [{"path": "source.md", "content": source_marker}],
                },
                "request validation failed",
            ),
            (
                {
                    **common,
                    "sources": [{"path": "source.md", "content": source_marker + "\ud800"}],
                },
                "request text is not valid UTF-8",
            ),
            *(
                (
                {**common, **selection, "external_disclosure_ack": acknowledgement},
                "request validation failed",
                )
                for selection in (
                    {"files": ["source.md"]},
                    {"sources": [{"path": "source.md", "content": source_marker}]},
                )
                for acknowledgement in (1, 1.0, False, "true")
            )
        )
        app.dependency_overrides[get_settings] = lambda: Settings(
            input_root=Path("/not-used"), token=token_marker
        )
        try:
            for body, detail in cases:
                with (
                    self.subTest(body_keys=sorted(body)),
                    patch("glupta_agi.api.crawl_observe_queue.enqueue_async") as enqueue,
                    patch("glupta_agi.api.DBOS.get_workflow_status_async") as workflow_status,
                    patch(
                        "glupta_agi.workflow.codex_adapter.CodexSubscriptionAdapter.generate"
                    ) as provider,
                ):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.post(
                            "/v1/evidence-brief",
                            content=json.dumps(body, ensure_ascii=True),
                            headers={
                                "content-type": "application/json",
                                "authorization": f"Bearer {token_marker}",
                                "idempotency-key": "01a011ce-66e7-70d0-94ca-d49cd9977089",
                            },
                        )

                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json(), {"detail": detail})
                for marker in (source_marker, token_marker):
                    self.assertNotIn(marker, response.text)
                enqueue.assert_not_called()
                workflow_status.assert_not_called()
                provider.assert_not_called()
        finally:
            app.dependency_overrides.pop(get_settings, None)

    async def test_non_utf8_inline_intake_releases_sensitive_exception_state(self) -> None:
        source_marker = "REJECTED_INLINE_UTF8_SOURCE_MARKER"
        token_marker = "REJECTED_INLINE_UTF8_TOKEN_MARKER_" + "t" * 32
        request = EvidenceBriefInlineRequest(
            question="What is grounded?",
            sources=[{"path": "source.md", "content": source_marker + "\ud800"}],
            disclosure_profile="external_disclosed_v1",
            disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
            external_disclosure_ack=True,
        )
        with patch("glupta_agi.api.crawl_observe_queue.enqueue_async") as enqueue:
            try:
                await evidence_brief(
                    request=request,
                    authorization=f"Bearer {token_marker}",
                    idempotency_key="01a011ce-66e7-70d0-94ca-d49cd9977089",
                    settings=Settings(input_root=Path("/not-used"), token=token_marker),
                )
            except HTTPException as exc:
                caught = exc
            else:
                self.fail("non-UTF-8 inline text reached admission")

        self.assertEqual(caught.status_code, 422)
        self.assertEqual(caught.detail, "request text is not valid UTF-8")
        _assert_public_error_sanitized(self, caught, source_marker, token_marker)
        enqueue.assert_not_called()

    async def test_admission_enqueues_the_root_on_the_bounded_dbos_queue(self) -> None:
        workflow_id = "01a011ce-66e7-70d0-94ca-d49cd9977081"
        token = "t" * 32
        with tempfile.TemporaryDirectory() as directory:
            input_root = Path(directory)
            (input_root / "facts.md").write_text("grounded fact\n", encoding="utf-8")
            profile = release_profile()
            home = codex_home(input_root)
            request = EvidenceBriefRequest(
                question="What is grounded?",
                files=["facts.md"],
                disclosure_profile="external_disclosed_v1",
                disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
                external_disclosure_ack=True,
            )
            canonical = load_request(
                input_root=input_root,
                question=request.question,
                selected_paths=request.files,
                disclosure_profile=request.disclosure_profile,
            )
            brief = EvidenceBrief(
                answer="Grounded answer.", citations=[], uncertainties=[], next_decisions=[]
            )
            response = {
                **brief.model_dump(mode="json"),
                "request_digest": canonical.request_digest,
                "workflow_id": workflow_id,
                "markdown": "# Evidence brief\n",
                "provider_audit": provider_audit(
                    brief, workflow_id=workflow_id, request_digest=canonical.request_digest
                ).model_dump(mode="json"),
            }
            handle = SimpleNamespace(get_result=AsyncMock(return_value=response))

            with (
                patch(
                    "glupta_agi.api.crawl_observe_queue.enqueue_async",
                    new=AsyncMock(return_value=handle),
                ) as enqueue,
                patch(
                    "glupta_agi.api.DBOS.get_workflow_status_async",
                    new=AsyncMock(
                        return_value=SimpleNamespace(input={"args": [canonical.workflow_payload()]})
                    ),
                ),
            ):
                result = await evidence_brief(
                    request=request,
                    authorization=f"Bearer {token}",
                    idempotency_key=workflow_id,
                    settings=Settings(
                        input_root=input_root,
                        token=token,
                        release_profile=profile,
                        release_profile_digest=profile.digest(),
                        codex_home=home,
                        auth_generation=profile.auth_generation,
                    ),
                )

        self.assertEqual(result.workflow_id, workflow_id)
        enqueue.assert_awaited_once_with(
            evidence_brief_workflow,
            canonical.workflow_payload(),
            workflow_id,
            profile.model_dump(mode="json"),
            str(home),
            profile.auth_generation,
            ANY,
        )
        admitted_at = datetime.fromisoformat(enqueue.await_args.args[-1])
        self.assertIsNotNone(admitted_at.tzinfo)

    async def test_inline_admission_binds_http_bytes_not_server_input_root(self) -> None:
        workflow_id = "01a011ce-66e7-70d0-94ca-d49cd9977082"
        token, content = "t" * 32, "approved inline bytes\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "facts.md").write_text("different server-root bytes\n", encoding="utf-8")
            profile, home = release_profile(), codex_home(root)
            request = EvidenceBriefInlineRequest(
                question="What is grounded?",
                sources=[{"path": "facts.md", "content": content}],
                disclosure_profile="external_disclosed_v1",
                disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
                external_disclosure_ack=True,
            )
            canonical = admit_inline_request(
                question=request.question,
                sources=[source.model_dump() for source in request.sources],
                disclosure_profile=request.disclosure_profile,
                disclosure_notice_digest=request.disclosure_notice_digest,
                external_disclosure_ack=request.external_disclosure_ack,
            )
            brief = EvidenceBrief(
                answer="Grounded answer.", citations=[], uncertainties=[], next_decisions=[]
            )
            response = {
                **brief.model_dump(mode="json"),
                "request_digest": canonical.request_digest,
                "workflow_id": workflow_id,
                "markdown": "# Evidence brief\n",
                "provider_audit": provider_audit(
                    brief, workflow_id=workflow_id, request_digest=canonical.request_digest
                ).model_dump(mode="json"),
            }
            enqueue = AsyncMock(
                return_value=SimpleNamespace(get_result=AsyncMock(return_value=response))
            )
            with (
                patch("glupta_agi.api.crawl_observe_queue.enqueue_async", new=enqueue),
                patch(
                    "glupta_agi.api.DBOS.get_workflow_status_async",
                    new=AsyncMock(
                        return_value=SimpleNamespace(
                            input={"args": [canonical.workflow_payload()]}
                        )
                    ),
                ),
            ):
                result = await evidence_brief(
                    request=request,
                    authorization=f"Bearer {token}",
                    idempotency_key=workflow_id,
                    settings=Settings(
                        input_root=root,
                        token=token,
                        release_profile=profile,
                        release_profile_digest=profile.digest(),
                        codex_home=home,
                        auth_generation=profile.auth_generation,
                    ),
                )

        self.assertEqual(result.request_digest, canonical.request_digest)
        self.assertEqual(enqueue.await_args.args[0], evidence_brief_workflow)
        self.assertEqual(enqueue.await_args.args[1], canonical.workflow_payload())
        self.assertEqual(enqueue.await_args.args[1]["sources"][0]["content"], content)

    async def test_header_rejections_release_request_auth_settings_and_id_locals(self) -> None:
        source_marker = "REJECTED_INLINE_SOURCE_MARKER"
        valid_token = "VALID_SETTINGS_TOKEN_" + "v" * 32
        bad_authorization = "REJECTED_AUTHORIZATION_" + "a" * 32
        invalid_id = "invalid-uuidv7-" + "i" * 32
        valid_id = "01a011ce-66e7-70d0-94ca-d49cd9977083"
        request = EvidenceBriefInlineRequest(
            question="q",
            sources=[{"path": "source.md", "content": source_marker}],
            disclosure_profile="external_disclosed_v1",
            disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
            external_disclosure_ack=True,
        )
        cases = (
            (f"Bearer {bad_authorization}", valid_id, 401, "invalid bearer capability",
             (source_marker, bad_authorization, valid_token)),
            (f"Bearer {valid_token}", invalid_id, 400, "invalid Idempotency-Key",
             (source_marker, valid_token, invalid_id)),
        )
        with tempfile.TemporaryDirectory() as directory:
            for authorization, idempotency_key, code, detail, markers in cases:
                with (
                    self.subTest(code=code),
                    patch("glupta_agi.api.crawl_observe_queue.enqueue_async") as enqueue,
                ):
                    try:
                        await evidence_brief(
                            request=request,
                            authorization=authorization,
                            idempotency_key=idempotency_key,
                            settings=Settings(input_root=Path(directory), token=valid_token),
                        )
                    except HTTPException as error:
                        caught = error
                    else:
                        self.fail("expected HTTPException")
                self.assertEqual(caught.status_code, code)
                self.assertEqual(caught.detail, detail)
                _assert_public_error_sanitized(self, caught, *markers)
                enqueue.assert_not_called()

    async def test_workflow_failures_release_public_secret_and_payload_locals(self) -> None:
        workflow_id = "01a011ce-66e7-70d0-94ca-d49cd9977081"
        authorization_marker = "R11_AUTHORIZATION_" + "a" * 32
        source_marker = "R11_ADMITTED_SOURCE_BYTES"
        for domain_error, expected_status, detail in (
            (AmbiguousEffectError, 503, "manual reconciliation required"),
            (BriefGenerationError, 502, "brief generation failed"),
        ):
            with (
                self.subTest(domain_error=domain_error.__name__),
                tempfile.TemporaryDirectory() as directory,
            ):
                input_root = Path(directory)
                (input_root / "marked.md").write_text(source_marker, encoding="utf-8")
                profile = release_profile()
                home = codex_home(input_root)
                request = EvidenceBriefRequest(
                    question="What is grounded?",
                    files=["marked.md"],
                    disclosure_profile="external_disclosed_v1",
                    disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
                    external_disclosure_ack=True,
                )
                canonical = load_request(
                    input_root=input_root,
                    question=request.question,
                    selected_paths=request.files,
                    disclosure_profile=request.disclosure_profile,
                )
                handle = SimpleNamespace(get_result=AsyncMock(side_effect=domain_error(detail)))
                enqueue = AsyncMock(return_value=handle)
                recorded_status = AsyncMock(
                    return_value=SimpleNamespace(input={"args": [canonical.workflow_payload()]})
                )
                settings = Settings(
                    input_root=input_root,
                    token=authorization_marker,
                    release_profile=profile,
                    release_profile_digest=profile.digest(),
                    codex_home=home,
                    auth_generation=profile.auth_generation,
                )

                with (
                    patch("glupta_agi.api.crawl_observe_queue.enqueue_async", new=enqueue),
                    patch("glupta_agi.api.DBOS.get_workflow_status_async", new=recorded_status),
                ):
                    try:
                        await evidence_brief(
                            request=request,
                            authorization=f"Bearer {authorization_marker}",
                            idempotency_key=workflow_id,
                            settings=settings,
                        )
                    except HTTPException as exc:
                        caught = exc
                    else:
                        self.fail("workflow failure reached a successful HTTP response")

                self.assertEqual(caught.status_code, expected_status)
                self.assertEqual(caught.detail, detail)
                _assert_public_error_sanitized(self, caught, authorization_marker, source_marker)
                enqueue.assert_awaited_once()
                recorded_status.assert_awaited_once_with(workflow_id)
                handle.get_result.assert_awaited_once_with()

    async def test_all_post_inline_failures_release_public_sensitive_locals(self) -> None:
        workflow_id = "01a011ce-66e7-70d0-94ca-d49cd9977083"
        source_marker = "POST_INLINE_SOURCE_MARKER"
        token_marker = "POST_INLINE_TOKEN_MARKER_" + "t" * 32
        result_marker = "POST_INLINE_RESULT_MARKER"
        cases = (
            ("payload", 500, "evidence brief unavailable", (0, 0, 0)),
            ("profile", 500, "evidence brief unavailable", (0, 0, 0)),
            ("workflow_context", 500, "evidence brief unavailable", (0, 0, 0)),
            ("enqueue", 500, "evidence brief unavailable", (1, 0, 0)),
            ("status", 500, "evidence brief unavailable", (1, 1, 0)),
            ("malformed", 500, "evidence brief unavailable", (1, 1, 0)),
            ("missing", 503, "workflow input unavailable", (1, 1, 0)),
            ("mismatch", 409, "Idempotency-Key already binds other input", (1, 1, 0)),
            ("result", 500, "evidence brief unavailable", (1, 1, 1)),
            ("response_validation", 500, "evidence brief unavailable", (1, 1, 1)),
            ("cancelled", None, None, (1, 0, 0)),
        )
        for failure, expected_status, detail, expected_calls in cases:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile = release_profile()
                request = EvidenceBriefInlineRequest(
                    question="What is grounded?",
                    sources=[{"path": "facts.md", "content": source_marker}],
                    disclosure_profile="external_disclosed_v1",
                    disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
                    external_disclosure_ack=True,
                )
                canonical = admit_inline_request(
                    question=request.question,
                    sources=[source.model_dump() for source in request.sources],
                    disclosure_profile=request.disclosure_profile,
                    disclosure_notice_digest=request.disclosure_notice_digest,
                    external_disclosure_ack=request.external_disclosure_ack,
                )
                settings = Settings(
                    input_root=root,
                    token=token_marker,
                    release_profile=profile,
                    release_profile_digest=profile.digest(),
                    codex_home=codex_home(root),
                    auth_generation=profile.auth_generation,
                )
                handle = SimpleNamespace(
                    get_result=AsyncMock(side_effect=RuntimeError(result_marker))
                )
                enqueue = AsyncMock(return_value=handle)
                recorded_status = AsyncMock(
                    return_value=SimpleNamespace(input={"args": [canonical.workflow_payload()]})
                )

                class WorkflowContext:
                    def __init__(self, _workflow_id: str) -> None:
                        pass

                    def __enter__(self, current_failure: str = failure) -> None:
                        if current_failure == "workflow_context":
                            raise RuntimeError(result_marker)

                    def __exit__(self, *_args: object) -> bool:
                        return False

                if failure == "profile":
                    settings = Settings(input_root=root, token=token_marker)
                elif failure == "enqueue":
                    enqueue.side_effect = HTTPException(418, result_marker)
                elif failure == "status":
                    recorded_status.side_effect = RuntimeError(result_marker)
                elif failure == "malformed":
                    recorded_status.return_value = SimpleNamespace(input={"wrong": True})
                elif failure == "missing":
                    recorded_status.return_value = None
                elif failure == "mismatch":
                    mismatched = canonical.workflow_payload()
                    mismatched["question"] = "different question"
                    recorded_status.return_value = SimpleNamespace(input={"args": [mismatched]})
                elif failure == "response_validation":
                    handle.get_result.side_effect = None
                    handle.get_result.return_value = {"answer": result_marker}
                elif failure == "cancelled":
                    enqueue.side_effect = asyncio.CancelledError()
                payload_failure = (
                    patch(
                        "glupta_agi.intake.CanonicalRequest.workflow_payload",
                        side_effect=RuntimeError(result_marker),
                    )
                    if failure == "payload"
                    else nullcontext()
                )

                with (
                    patch("glupta_agi.api.SetWorkflowID", new=WorkflowContext),
                    patch("glupta_agi.api.crawl_observe_queue.enqueue_async", new=enqueue),
                    patch(
                        "glupta_agi.api.DBOS.get_workflow_status_async", new=recorded_status
                    ),
                    payload_failure,
                ):
                    try:
                        await evidence_brief(
                            request=request,
                            authorization=f"Bearer {token_marker}",
                            idempotency_key=workflow_id,
                            settings=settings,
                        )
                    except BaseException as exc:
                        caught = exc
                    else:
                        self.fail("post-inline failure reached a successful HTTP response")

                if expected_status is None:
                    self.assertIsInstance(caught, asyncio.CancelledError)
                else:
                    self.assertIsInstance(caught, HTTPException)
                    self.assertEqual(caught.status_code, expected_status)
                    self.assertEqual(caught.detail, detail)
                _assert_public_error_sanitized(
                    self, caught, source_marker, token_marker, result_marker
                )
                self.assertEqual(
                    (
                        enqueue.await_count,
                        recorded_status.await_count,
                        handle.get_result.await_count,
                    ),
                    expected_calls,
                )
