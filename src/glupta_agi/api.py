from __future__ import annotations

import uuid
from datetime import UTC, datetime

from dbos import DBOS, SetWorkflowID
from fastapi import Depends, FastAPI, Header, HTTPException, status

from . import __version__
from .contracts import EvidenceBriefRequest, EvidenceBriefResponse
from .effects import AmbiguousEffectError
from .intake import IntakeError, load_request
from .settings import Settings, get_settings
from .workflow import BriefGenerationError, crawl_observe_queue, evidence_brief_workflow

app = FastAPI(title="glupta agi", version=__version__, docs_url=None, redoc_url=None)


def _bearer(authorization: str | None, settings: Settings) -> None:
    prefix = "Bearer "
    if authorization is None or not authorization.startswith(prefix):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer capability")
    if not settings.authenticates(authorization[len(prefix) :]):
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


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "healthy", "stage": "Crawl", "actions": "disabled", "inference": "external_disclosed_v1"}  # noqa: E501


@app.post("/v1/evidence-brief", response_model=EvidenceBriefResponse)
async def evidence_brief(
    request: EvidenceBriefRequest,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    settings: Settings = Depends(get_settings),  # noqa: B008 -- FastAPI dependency marker
) -> EvidenceBriefResponse:
    _bearer(authorization, settings)
    workflow_id = _workflow_id(idempotency_key)
    try:
        canonical = load_request(input_root=settings.input_root, question=request.question,
            selected_paths=request.files, disclosure_profile=request.disclosure_profile,
            disclosure_notice_digest=request.disclosure_notice_digest, external_disclosure_ack=request.external_disclosure_ack)  # noqa: E501
    except IntakeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None

    payload = canonical.workflow_payload()
    with SetWorkflowID(workflow_id):
        profile, credential_file, credential_generation = settings.require_external_profile()
        handle = await crawl_observe_queue.enqueue_async(evidence_brief_workflow, payload,
            workflow_id, profile.model_dump(mode="json"), str(credential_file), credential_generation, datetime.now(UTC).isoformat())  # noqa: E501

    recorded = await DBOS.get_workflow_status_async(workflow_id)
    recorded_args = recorded.input["args"] if recorded is not None and recorded.input else ()
    if not recorded_args or not isinstance(recorded_args[0], dict):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "workflow input unavailable")
    if not canonical.matches_recorded_payload(recorded_args[0]):
        raise HTTPException(status.HTTP_409_CONFLICT, "Idempotency-Key already binds other input")

    error: tuple[int, str] | None = None
    try:
        result = await handle.get_result()
    except AmbiguousEffectError as exc:
        error = status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)
    except BriefGenerationError as exc:
        error = status.HTTP_502_BAD_GATEWAY, str(exc)
    if error is not None:
        del request, authorization, idempotency_key, settings, workflow_id, canonical, payload, profile, credential_file, credential_generation, handle, recorded, recorded_args  # noqa: E501
        raise HTTPException(error[0], error[1]) from None
    return EvidenceBriefResponse.model_validate(result)
