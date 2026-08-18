"""Official OpenAI Responses API edge for the Crawl inference port."""

from __future__ import annotations

import asyncio
import os
import stat
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openai import APIStatusError, AsyncOpenAI, DefaultAsyncHttpxClient

from . import contracts
from .inference import FrozenDispatch, ReleaseProfile, usd_upper_bound

_USAGE_FIELDS = set("input_tokens input_tokens_details output_tokens output_tokens_details total_tokens".split())  # noqa: E501
_INPUT_DETAIL_FIELDS = set("cached_tokens cache_write_tokens".split())
_OUTPUT_DETAIL_FIELDS = {"reasoning_tokens"}


class AdapterError(RuntimeError):
    pass


class ProviderAmbiguousError(AdapterError):
    def __init__(self, message: str, audit: contracts.ProviderAudit | None = None) -> None:
        super().__init__(message)
        self.audit = audit


class ProviderRejectedError(AdapterError):
    def __init__(self, message: str, audit: contracts.ProviderAudit | None = None) -> None:
        super().__init__(message)
        self.audit = audit


def _field_names(value: Any) -> set[str]:
    return set(value.model_dump(exclude_none=False) if hasattr(value, "model_dump") else vars(value))  # noqa: E501


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
        client_factory: Callable[..., Any] = AsyncOpenAI,
    ) -> None:
        self.profile = profile
        self.credential_file = credential_file
        self.client_factory = client_factory

    async def generate(self, dispatch: FrozenDispatch, request_body: dict[str, Any]) -> contracts.ProviderResult:  # noqa: E501
        if not self.profile.current_at():
            raise AdapterError("release profile evidence is expired")
        if dispatch.release_profile_digest != self.profile.digest():
            raise AdapterError("release profile changed after effect reservation")
        if dispatch.request_body_digest != contracts.canonical_digest(request_body):
            raise AdapterError("provider request changed after effect reservation")
        key = _read_api_key(self.credential_file)
        client_request_id = str(uuid.uuid5(uuid.NAMESPACE_URL, dispatch.digest()))
        started = datetime.now(UTC)
        remaining_seconds = (dispatch.wall_deadline - started).total_seconds()
        if remaining_seconds <= 0:
            raise AdapterError("model request exceeded the wall deadline")
        client, cleanup_ambiguous, provider_status = None, False, None
        monotonic_deadline = asyncio.get_running_loop().time() + remaining_seconds
        try:
            http_client = DefaultAsyncHttpxClient(trust_env=False, follow_redirects=False)
            client = self.client_factory(
                api_key=key, base_url=self.profile.endpoint, max_retries=0,
                timeout=min(float(dispatch.wall_timeout_seconds), remaining_seconds),
                http_client=http_client,
            )
            async with asyncio.timeout_at(monotonic_deadline):
                headers = {"X-Client-Request-Id": client_request_id}
                response = await client.responses.create(**request_body, extra_headers=headers)
                completed = datetime.now(UTC)
        except APIStatusError as exc:
            provider_status = exc.status_code
        except Exception as exc:
            raise ProviderAmbiguousError("OpenAI request outcome is ambiguous") from exc
        finally:
            if client is not None:
                close = getattr(client, "close", None)
                if callable(close):
                    try:
                        async with asyncio.timeout_at(monotonic_deadline):
                            await close()
                    except Exception:
                        cleanup_ambiguous = True
        if provider_status is not None:
            if provider_status in {400, 401, 403, 404, 422} and not cleanup_ambiguous:
                raise ProviderRejectedError("OpenAI request was rejected") from None
            raise ProviderAmbiguousError("OpenAI request outcome is ambiguous") from None
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
            invalid_fields = (
                _field_names(usage) != _USAGE_FIELDS
                or _field_names(usage.input_tokens_details) != _INPUT_DETAIL_FIELDS
                or _field_names(usage.output_tokens_details) != _OUTPUT_DETAIL_FIELDS
            )
            if invalid_fields:
                raise ValueError
            input_tokens = int(usage.input_tokens)
            output_tokens = int(usage.output_tokens)
            total_tokens = int(usage.total_tokens)
            input_details = usage.input_tokens_details
            cached_tokens = int(getattr(input_details, "cached_tokens", 0) or 0)
            cache_write_tokens = int(getattr(input_details, "cache_write_tokens", 0) or 0)
            reasoning_tokens = int(getattr(usage.output_tokens_details, "reasoning_tokens", 0) or 0)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ProviderAmbiguousError("OpenAI usage is invalid") from exc
        token_counts = (input_tokens, output_tokens, total_tokens, cached_tokens,
                        cache_write_tokens, reasoning_tokens)
        if min(token_counts) < 0:
            raise ProviderAmbiguousError("OpenAI usage is invalid")
        if total_tokens != input_tokens + output_tokens or cached_tokens + cache_write_tokens > input_tokens:  # noqa: E501
            raise ProviderAmbiguousError("OpenAI usage is inconsistent")
        cost = usd_upper_bound(input_tokens, output_tokens)
        observed = (input_tokens, output_tokens, reasoning_tokens, cost)
        limits = (dispatch.input_token_upper_bound, dispatch.max_output_tokens,
                  self.profile.max_reasoning_tokens, dispatch.max_usd_micros)
        if any(value > limit for value, limit in zip(observed, limits, strict=True)):
            raise ProviderAmbiguousError("OpenAI usage exceeds the reserved budget")
        output_text = str(getattr(response, "output_text", "") or "")
        audit = contracts.ProviderAudit(
            workflow_id=dispatch.workflow_id, request_digest=dispatch.request_digest,
            release_profile_digest=dispatch.release_profile_digest,
            client_request_id=client_request_id, provider_request_id=request_id,
            response_id=response_id, requested_model=dispatch.model,
            returned_model=returned_model, status=status, input_tokens=input_tokens,
            cached_input_tokens=cached_tokens, output_tokens=output_tokens,
            cache_write_input_tokens=cache_write_tokens,
            reasoning_tokens=reasoning_tokens, total_tokens=total_tokens,
            cost_upper_bound_micros=cost,
            request_body_digest=dispatch.request_body_digest,
            output_digest=contracts.canonical_digest(output_text), started_at=started,
            completed_at=completed,
        )
        if cleanup_ambiguous:
            raise ProviderAmbiguousError("OpenAI response cleanup is ambiguous", audit)
        if returned_model != dispatch.model:
            raise ProviderRejectedError("OpenAI returned an unapproved model", audit)
        if completed > dispatch.wall_deadline:
            raise ProviderRejectedError("OpenAI response exceeded the wall deadline", audit)
        if status != "completed":
            raise ProviderRejectedError("OpenAI response was not completed", audit)
        try:
            brief = contracts.EvidenceBrief.model_validate_json(output_text)
        except ValueError as exc:
            raise ProviderRejectedError("OpenAI output failed the response schema", audit) from exc
        result_digest = contracts.canonical_digest(brief.model_dump(mode="json"))
        audit = audit.model_copy(update={"validated_result_digest": result_digest})
        audit = audit.model_copy(update={"record_digest": contracts.provider_record_digest(brief, audit)})  # noqa: E501
        return contracts.ProviderResult(brief=brief, audit=audit)
