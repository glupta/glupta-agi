from __future__ import annotations

import asyncio
import hashlib
import hmac
import uuid
from datetime import UTC, datetime

from dbos import DBOS, SetWorkflowID
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.responses import Response

from . import __version__
from .contracts import EvidenceBriefInlineRequest, EvidenceBriefRequest, EvidenceBriefResponse
from .effects import AmbiguousEffectError
from .intake import CanonicalRequest, IntakeError, admit_inline_request, load_request
from .settings import Settings, get_settings
from .walk import WalkArtifact, WalkRequest, WalkResponse
from .workflow import (
    BriefGenerationError,
    crawl_observe_queue,
    evidence_brief_workflow,
    walk_proposal_workflow,
    walk_queue,
)

app = FastAPI(title="glupta agi", version=__version__, docs_url=None, redoc_url=None)
WALK_ARTIFACT_MAX_BYTES = 512 * 1024


@app.exception_handler(RequestValidationError)
async def _bounded_validation_error(request: Request, error: RequestValidationError) -> Response:
    del request, error
    return Response(b'{"detail":"request validation failed"}',
                    status.HTTP_422_UNPROCESSABLE_CONTENT, media_type="application/json")


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
    except (AmbiguousEffectError, BriefGenerationError) as exc:
        code = (status.HTTP_503_SERVICE_UNAVAILABLE if isinstance(exc, AmbiguousEffectError)
                else status.HTTP_502_BAD_GATEWAY)
        return code, str(exc)
    except Exception:
        return status.HTTP_500_INTERNAL_SERVER_ERROR, "evidence brief unavailable"


def _admit_walk_artifact(raw: bytes, expected_digest: str) -> tuple[WalkRequest | None, str | None]:
    admitted = None
    try:
        if (len(raw) > WALK_ARTIFACT_MAX_BYTES or len(expected_digest) != 64
                or expected_digest != expected_digest.lower()
                or any(character not in "0123456789abcdef" for character in expected_digest)
                or not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected_digest)):
            raise ValueError
        artifact = WalkArtifact.model_validate_json(raw)
        admitted = artifact.admit(expected_digest)
    except (ValueError, UnicodeError):
        error = "Walk artifact is invalid or does not match its approved digest"
    else:
        error = None
    raw = b""
    return admitted, error


async def _read_walk_body(request: Request) -> bytes | None:
    buffer = bytearray()
    chunk = b""
    try:
        async for chunk in request.stream():
            if len(buffer) + len(chunk) > WALK_ARTIFACT_MAX_BYTES:
                buffer.clear()
                return None
            buffer.extend(chunk)
    except asyncio.CancelledError:
        buffer.clear()
        chunk = b""
        del request
        raise asyncio.CancelledError from None
    except Exception:
        buffer.clear()
        return None
    return bytes(buffer)


async def _complete_walk_admission(admitted: WalkRequest, workflow_id: str,
    settings: Settings) -> WalkResponse | tuple[int, str] | None:
    try:
        profile, codex_home, auth_generation = settings.require_walk_profile()
        if admitted.release_profile_digest != profile.digest():
            return status.HTTP_409_CONFLICT, "Walk artifact binds another release profile"
        payload = admitted.workflow_payload()
        with SetWorkflowID(workflow_id):
            handle = await walk_queue.enqueue_async(walk_proposal_workflow, payload, workflow_id,
                profile.model_dump(mode="json"), str(codex_home), auth_generation,
                datetime.now(UTC).isoformat())
        recorded = await DBOS.get_workflow_status_async(workflow_id)
        recorded_args = recorded.input["args"] if recorded is not None and recorded.input else ()
        if not recorded_args or recorded_args[0] != admitted.workflow_payload():
            return status.HTTP_409_CONFLICT, "Idempotency-Key already binds other input"
        return WalkResponse.model_validate(await handle.get_result())
    except asyncio.CancelledError:
        return None
    except (AmbiguousEffectError, BriefGenerationError) as exc:
        code = (status.HTTP_503_SERVICE_UNAVAILABLE if isinstance(exc, AmbiguousEffectError)
                else status.HTTP_502_BAD_GATEWAY)
        return code, str(exc)
    except Exception:
        return status.HTTP_500_INTERNAL_SERVER_ERROR, "Walk proposal unavailable"


@app.get("/healthz")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:  # noqa: B008
    profile = settings.release_profile
    return dict(status="healthy", stage=getattr(profile, "stage", "Crawl"), actions="disabled",
                inference="external_disclosed_v1")


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


@app.post("/v1/walk/proposals", response_model=WalkResponse)
async def walk_proposal(
    request: Request,
    authorization: str | None = Header(default=None),
    artifact_sha256: str = Header(alias="X-Artifact-SHA256"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> WalkResponse:
    cancelled = False
    try:
        raw = await _read_walk_body(request)
    except asyncio.CancelledError:
        raw, cancelled = None, True
    if cancelled:
        del request, authorization, artifact_sha256, idempotency_key, settings, raw
        raise asyncio.CancelledError from None
    admitted, artifact_error = ((None, "Walk artifact is invalid or exceeds its size limit")
        if raw is None else _admit_walk_artifact(raw, artifact_sha256))
    raw = b""
    del raw, request, artifact_sha256
    header_error = None
    try:
        if artifact_error is not None or admitted is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, artifact_error)
        _bearer(authorization, settings)
        workflow_id = _workflow_id(idempotency_key)
    except HTTPException as exc:
        header_error = exc.status_code, str(exc.detail)
    if header_error is not None:
        del admitted, authorization, idempotency_key, settings
        raise HTTPException(header_error[0], header_error[1]) from None
    del authorization, idempotency_key
    outcome = await _complete_walk_admission(admitted, workflow_id, settings)
    del admitted, workflow_id, settings
    if outcome is None:
        raise asyncio.CancelledError from None
    if isinstance(outcome, tuple):
        raise HTTPException(outcome[0], outcome[1]) from None
    return outcome
