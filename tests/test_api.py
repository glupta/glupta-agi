from __future__ import annotations

import tempfile
import traceback
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

from fastapi import HTTPException

from glupta_agi.api import evidence_brief
from glupta_agi.contracts import DISCLOSURE_NOTICE_DIGEST, EvidenceBrief, EvidenceBriefRequest
from glupta_agi.effects import AmbiguousEffectError
from glupta_agi.intake import load_request
from glupta_agi.settings import Settings
from glupta_agi.workflow import BriefGenerationError, evidence_brief_workflow
from tests.helpers import private_file, provider_audit, release_profile


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
                item for item in captured.stack if item.filename == frame.f_code.co_filename
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
    async def test_admission_enqueues_the_root_on_the_bounded_dbos_queue(self) -> None:
        workflow_id = "01a011ce-66e7-70d0-94ca-d49cd9977081"
        token = "t" * 32
        with tempfile.TemporaryDirectory() as directory:
            input_root = Path(directory)
            (input_root / "facts.md").write_text("grounded fact\n", encoding="utf-8")
            profile = release_profile()
            key = private_file(input_root, "api-key", "secret-api-key-" + "x" * 32)
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
                        openai_api_key_file=key,
                        credential_generation=profile.credential_generation,
                    ),
                )

        self.assertEqual(result.workflow_id, workflow_id)
        enqueue.assert_awaited_once_with(
            evidence_brief_workflow,
            canonical.workflow_payload(),
            workflow_id,
            profile.model_dump(mode="json"),
            str(key),
            profile.credential_generation,
            ANY,
        )
        admitted_at = datetime.fromisoformat(enqueue.await_args.args[-1])
        self.assertIsNotNone(admitted_at.tzinfo)

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
                key = private_file(input_root, "api-key", "synthetic-key-material")
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
                handle = SimpleNamespace(
                    get_result=AsyncMock(side_effect=domain_error(detail))
                )
                enqueue = AsyncMock(return_value=handle)
                recorded_status = AsyncMock(
                    return_value=SimpleNamespace(
                        input={"args": [canonical.workflow_payload()]}
                    )
                )
                settings = Settings(
                    input_root=input_root,
                    token=authorization_marker,
                    release_profile=profile,
                    release_profile_digest=profile.digest(),
                    openai_api_key_file=key,
                    credential_generation=profile.credential_generation,
                )

                with (
                    patch("glupta_agi.api.crawl_observe_queue.enqueue_async", new=enqueue),
                    patch(
                        "glupta_agi.api.DBOS.get_workflow_status_async", new=recorded_status
                    ),
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
                _assert_public_error_sanitized(
                    self, caught, authorization_marker, source_marker
                )
                enqueue.assert_awaited_once()
                recorded_status.assert_awaited_once_with(workflow_id)
                handle.get_result.assert_awaited_once_with()
