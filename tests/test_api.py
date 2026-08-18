from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

from glupta_agi.api import evidence_brief
from glupta_agi.contracts import DISCLOSURE_NOTICE_DIGEST, EvidenceBrief, EvidenceBriefRequest
from glupta_agi.intake import load_request
from glupta_agi.settings import Settings
from glupta_agi.workflow import evidence_brief_workflow
from tests.helpers import private_file, provider_audit, release_profile


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
            ANY,
        )
        admitted_at = datetime.fromisoformat(enqueue.await_args.args[-1])
        self.assertIsNotNone(admitted_at.tzinfo)
