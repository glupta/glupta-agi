"""Official OpenAI Responses API edge for the Crawl inference port."""

from __future__ import annotations

import os
import stat
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openai import DefaultHttpxClient, OpenAI

from .contracts import EvidenceBrief
from .inference import (
    FrozenDispatch,
    ProviderAudit,
    ProviderResult,
    ReleaseProfile,
    canonical_digest,
    usd_upper_bound,
)


class AdapterError(RuntimeError):
    pass


class ProviderAmbiguousError(AdapterError):
    pass


class ProviderRejectedError(AdapterError):
    def __init__(self, message: str, audit: ProviderAudit | None = None) -> None:
        super().__init__(message)
        self.audit = audit


def _field_names(value: Any) -> set[str]:
    dumped = value.model_dump(exclude_none=False) if hasattr(value, "model_dump") else vars(value)
    return set(dumped)


def _read_api_key(path: Path) -> str:
    file_fd = -1
    try:
        file_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        metadata = os.fstat(file_fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.geteuid()
            or not 20 <= metadata.st_size <= 512
        ):
            raise AdapterError("OpenAI credential file is not private and regular")
        with os.fdopen(file_fd, encoding="utf-8") as key_file:
            file_fd = -1
            key = key_file.read(513).strip()
    except AdapterError:
        raise
    except (OSError, UnicodeError) as exc:
        raise AdapterError("OpenAI credential is unavailable") from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
    if not 20 <= len(key.encode()) <= 512:
        raise AdapterError("OpenAI credential length is invalid")
    return key


class OpenAIResponsesAdapter:
    def __init__(
        self,
        profile: ReleaseProfile,
        credential_file: Path,
        *,
        client_factory: Callable[..., Any] = OpenAI,
    ) -> None:
        self.profile = profile
        self.credential_file = credential_file
        self.client_factory = client_factory

    def generate(self, dispatch: FrozenDispatch, request_body: dict[str, Any]) -> ProviderResult:
        if not self.profile.current_at():
            raise AdapterError("release profile evidence is expired")
        if dispatch.release_profile_digest != self.profile.digest():
            raise AdapterError("release profile changed after effect reservation")
        if dispatch.request_body_digest != canonical_digest(request_body):
            raise AdapterError("provider request changed after effect reservation")
        key = _read_api_key(self.credential_file)
        client_request_id = str(uuid.uuid5(uuid.NAMESPACE_URL, dispatch.digest()))
        started = datetime.now(UTC)
        remaining_seconds = (dispatch.wall_deadline - started).total_seconds()
        if remaining_seconds <= 0:
            raise AdapterError("model request exceeded the wall deadline")
        client = None
        try:
            client = self.client_factory(
                api_key=key,
                base_url=self.profile.endpoint,
                max_retries=0,
                timeout=min(float(dispatch.wall_timeout_seconds), remaining_seconds),
                http_client=DefaultHttpxClient(trust_env=False, follow_redirects=False),
            )
            response = client.responses.create(
                **request_body,
                extra_headers={"X-Client-Request-Id": client_request_id},
            )
        except Exception as exc:
            raise ProviderAmbiguousError("OpenAI request outcome is ambiguous") from exc
        finally:
            if client is not None:
                close = getattr(client, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:  # noqa: S110 -- cleanup cannot change request outcome
                        pass
        completed = datetime.now(UTC)
        status = str(getattr(response, "status", ""))
        request_id = str(getattr(response, "_request_id", "") or "")
        response_id = str(getattr(response, "id", "") or "")
        returned_model = str(getattr(response, "model", "") or "")
        if not request_id or not response_id:
            raise ProviderAmbiguousError("OpenAI response lacks request identity")
        usage = getattr(response, "usage", None)
        if usage is None:
            raise ProviderAmbiguousError("OpenAI response lacks usage")
        try:
            if _field_names(usage) != {
                "input_tokens",
                "input_tokens_details",
                "output_tokens",
                "output_tokens_details",
                "total_tokens",
            } or _field_names(usage.input_tokens_details) != {
                "cached_tokens",
                "cache_write_tokens",
            } or _field_names(usage.output_tokens_details) != {"reasoning_tokens"}:
                raise ValueError
            input_tokens = int(usage.input_tokens)
            output_tokens = int(usage.output_tokens)
            total_tokens = int(usage.total_tokens)
            cached_tokens = int(getattr(usage.input_tokens_details, "cached_tokens", 0) or 0)
            cache_write_tokens = int(
                getattr(usage.input_tokens_details, "cache_write_tokens", 0) or 0
            )
            reasoning_tokens = int(getattr(usage.output_tokens_details, "reasoning_tokens", 0) or 0)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ProviderAmbiguousError("OpenAI usage is invalid") from exc
        if min(
            input_tokens,
            output_tokens,
            total_tokens,
            cached_tokens,
            cache_write_tokens,
            reasoning_tokens,
        ) < 0:
            raise ProviderAmbiguousError("OpenAI usage is invalid")
        if (
            total_tokens != input_tokens + output_tokens
            or cached_tokens + cache_write_tokens > input_tokens
        ):
            raise ProviderAmbiguousError("OpenAI usage is inconsistent")
        cost = usd_upper_bound(input_tokens, output_tokens)
        if (
            input_tokens > dispatch.input_token_upper_bound
            or output_tokens > dispatch.max_output_tokens
            or reasoning_tokens > self.profile.max_reasoning_tokens
            or cost > dispatch.max_usd_micros
        ):
            raise ProviderAmbiguousError("OpenAI usage exceeds the reserved budget")
        output_text = str(getattr(response, "output_text", "") or "")
        audit = ProviderAudit(
            client_request_id=client_request_id,
            provider_request_id=request_id,
            response_id=response_id,
            requested_model=dispatch.model,
            returned_model=returned_model,
            status=status,
            input_tokens=input_tokens,
            cached_input_tokens=cached_tokens,
            cache_write_input_tokens=cache_write_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            cost_upper_bound_micros=cost,
            request_body_digest=dispatch.request_body_digest,
            output_digest=canonical_digest(output_text),
            started_at=started,
            completed_at=completed,
        )
        if returned_model != dispatch.model:
            raise ProviderRejectedError("OpenAI returned an unapproved model", audit)
        if completed > dispatch.wall_deadline:
            raise ProviderRejectedError("OpenAI response exceeded the wall deadline", audit)
        if status != "completed":
            raise ProviderRejectedError("OpenAI response was not completed", audit)
        try:
            brief = EvidenceBrief.model_validate_json(output_text)
        except ValueError as exc:
            raise ProviderRejectedError("OpenAI output failed the response schema", audit) from exc
        audit = audit.model_copy(
            update={"validated_result_digest": canonical_digest(brief.model_dump(mode="json"))}
        )
        return ProviderResult(brief=brief, audit=audit)
