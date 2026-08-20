from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from dbos import DBOS, SetWorkflowID
from fastapi import Depends, FastAPI, Header, HTTPException, status

from . import __version__
from .contracts import EvidenceBriefInlineRequest, EvidenceBriefRequest, EvidenceBriefResponse
from .effects import AmbiguousEffectError
from .intake import CanonicalRequest, IntakeError, admit_inline_request, load_request
from .settings import Settings, get_settings
from .workflow import BriefGenerationError, crawl_observe_queue, evidence_brief_workflow

app = FastAPI(title="glupta agi", version=__version__, docs_url=None, redoc_url=None)


def _bearer(authorization: str | None, settings: Settings) -> None:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer capability")
    if not settings.authenticates(authorization.removeprefix("Bearer ")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid bearer capability")


def _workflow_id(raw: str | None) -> str:
    if raw is None or raw != raw.lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid Idempotency-Key")
    try:
        parsed = uuid.UUID(raw)
    except (ValueError, AttributeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid Idempotency-Key") from None
    if parsed.version != 7 or str(parsed) != raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Idempotency-Key must be lowercase UUIDv7")
    return raw


async def _complete_admission(canonical: CanonicalRequest, workflow_id: str, settings: Settings):
    try:
        payload = canonical.workflow_payload()
        with SetWorkflowID(workflow_id):
            profile, codex_home, auth_generation = settings.require_external_profile()
            handle = await crawl_observe_queue.enqueue_async(
                evidence_brief_workflow, payload, workflow_id,
                profile.model_dump(mode="json"), str(codex_home), auth_generation,
                datetime.now(UTC).isoformat(),
            )
        recorded = await DBOS.get_workflow_status_async(workflow_id)
        recorded_args = recorded.input["args"] if recorded is not None and recorded.input else ()
        if not recorded_args or not isinstance(recorded_args[0], dict):
            return status.HTTP_503_SERVICE_UNAVAILABLE, "workflow input unavailable"
        if recorded_args[0] != canonical.workflow_payload():
            return status.HTTP_409_CONFLICT, "Idempotency-Key already binds other input"
        return EvidenceBriefResponse.model_validate(await handle.get_result())
    except asyncio.CancelledError:
        return None
    except AmbiguousEffectError as exc:
        return status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)
    except BriefGenerationError as exc:
        return status.HTTP_502_BAD_GATEWAY, str(exc)
    except Exception:
        return status.HTTP_500_INTERNAL_SERVER_ERROR, "evidence brief unavailable"


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "healthy", "stage": "Crawl", "actions": "disabled",
            "inference": "external_disclosed_v1"}


@app.post("/v1/evidence-brief", response_model=EvidenceBriefResponse)
async def evidence_brief(
    request: EvidenceBriefRequest | EvidenceBriefInlineRequest,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    settings: Settings = Depends(get_settings),  # noqa: B008 -- FastAPI dependency marker
) -> EvidenceBriefResponse:
    header_error = None
    try:
        _bearer(authorization, settings)
        workflow_id = _workflow_id(idempotency_key)
    except HTTPException as exc:
        header_error = exc.status_code, str(exc.detail)
    if header_error is not None:
        del request, authorization, idempotency_key, settings
        raise HTTPException(header_error[0], header_error[1]) from None
    del authorization, idempotency_key
    intake_error = None
    try:
        common = request.model_dump(exclude={"files", "sources"})
        if isinstance(request, EvidenceBriefInlineRequest):
            canonical = admit_inline_request(
                sources=[source.model_dump() for source in request.sources], **common
            )
        else:
            canonical = load_request(
                input_root=settings.input_root, selected_paths=request.files, **common
            )
    except IntakeError as exc:
        intake_error = status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)
    if intake_error is not None:
        del request, settings, workflow_id, common
        raise HTTPException(intake_error[0], intake_error[1]) from None

    outcome = await _complete_admission(canonical, workflow_id, settings)
    del request, settings, workflow_id, canonical, common
    if outcome is None:
        raise asyncio.CancelledError from None
    if isinstance(outcome, tuple):
        raise HTTPException(outcome[0], outcome[1]) from None
    return outcome
