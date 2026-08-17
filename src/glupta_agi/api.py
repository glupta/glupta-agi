"""Authenticated loopback FastAPI adapter for evidence_brief_v1."""

from __future__ import annotations

import uuid
from functools import lru_cache

from dbos import DBOS, SetWorkflowID
from fastapi import Depends, FastAPI, Header, HTTPException, status

from .contracts import EvidenceBriefRequest, EvidenceBriefResponse
from .intake import IntakeError, load_request
from .settings import Settings, SettingsError
from .workflow import evidence_brief_workflow

app = FastAPI(title="glupta agi", version="0.1.0", docs_url=None, redoc_url=None)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_environment()


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
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid Idempotency-Key") from exc
    if parsed.version != 7 or str(parsed) != raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Idempotency-Key must be lowercase UUIDv7")
    return raw


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "healthy", "stage": "Crawl", "effects": "disabled"}


@app.post("/v1/evidence-brief", response_model=EvidenceBriefResponse)
async def evidence_brief(
    request: EvidenceBriefRequest,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    settings: Settings = Depends(get_settings),
) -> EvidenceBriefResponse:
    _bearer(authorization, settings)
    workflow_id = _workflow_id(idempotency_key)
    try:
        canonical = load_request(
            input_root=settings.input_root,
            question=request.question,
            selected_paths=request.files,
            write_artifacts=request.write_artifacts,
        )
    except IntakeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    payload = canonical.workflow_payload()
    with SetWorkflowID(workflow_id):
        handle = await DBOS.start_workflow_async(
            evidence_brief_workflow,
            payload,
            workflow_id,
            str(settings.artifact_root),
            settings.ollama_base_url,
            settings.ollama_model,
        )

    recorded = await DBOS.get_workflow_status_async(workflow_id)
    recorded_args = recorded.input["args"] if recorded is not None and recorded.input else ()
    if not recorded_args or not isinstance(recorded_args[0], dict):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "workflow input unavailable")
    if recorded_args[0].get("request_digest") != canonical.request_digest:
        raise HTTPException(status.HTTP_409_CONFLICT, "Idempotency-Key already binds other input")

    result = await handle.get_result()
    return EvidenceBriefResponse.model_validate(result)


def load_app() -> FastAPI:
    try:
        get_settings()
    except SettingsError:
        raise
    return app
