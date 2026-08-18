"""Official OpenAI Responses API edge for the Crawl inference port."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import stat
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openai import APIStatusError, AsyncOpenAI, DefaultAsyncHttpxClient, Omit

from . import contracts
from .inference import FrozenDispatch, ReleaseProfile, usd_upper_bound

_USAGE_FIELDS = set("input_tokens input_tokens_details output_tokens output_tokens_details total_tokens".split())  # noqa: E501
_INPUT_DETAIL_FIELDS, _OUTPUT_DETAIL_FIELDS = set("cached_tokens cache_write_tokens".split()), {"reasoning_tokens"}  # noqa: E501
class AdapterError(RuntimeError):
    def __init__(self, message: str, audit: contracts.ProviderAudit | None = None) -> None:
        super().__init__(message)
        self.audit = audit


class ProviderAmbiguousError(AdapterError):
    pass


class ProviderRejectedError(AdapterError):
    pass


def _field_names(value: Any) -> set[str]:
    return set(value.model_dump(exclude_none=False) if hasattr(value, "model_dump") else vars(value))  # noqa: E501


def _read_api_key(path: Path, expected_sha256: str) -> str:
    file_fd, unavailable = -1, False
    try:
        file_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        metadata = os.fstat(file_fd)
        if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_uid != os.geteuid() or not 20 <= metadata.st_size <= 512):
            raise AdapterError("OpenAI credential file is not private and regular")
        with os.fdopen(file_fd, encoding="utf-8") as key_file:
            file_fd = -1
            key = key_file.read(513).strip()
    except AdapterError:
        raise
    except (OSError, UnicodeError):
        unavailable = True
    finally:
        if file_fd >= 0:
            os.close(file_fd)
    if unavailable:
        raise AdapterError("OpenAI credential is unavailable") from None
    if not 20 <= len(key.encode()) <= 512:
        raise AdapterError("OpenAI credential length is invalid")
    observed_sha256 = hashlib.sha256(key.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(observed_sha256, expected_sha256):
        raise AdapterError("OpenAI credential does not match the approved identity and generation")
    return key


class OpenAIResponsesAdapter:
    def __init__(
        self, profile: ReleaseProfile, credential_file: Path, *, credential_generation: int,
        client_factory: Callable[..., Any] = AsyncOpenAI,
    ) -> None:
        self.profile = profile
        self.credential_file = credential_file
        self.credential_generation = credential_generation
        self.client_factory = client_factory

    async def generate(self, dispatch: FrozenDispatch, request_body: dict[str, Any]) -> contracts.ProviderResult:  # noqa: E501
        if not self.profile.current_at():
            raise AdapterError("release profile evidence is expired")
        if dispatch.release_profile_digest != self.profile.digest():
            raise AdapterError("release profile changed after effect reservation")
        if dispatch.request_body_digest != contracts.canonical_digest(request_body) or request_body.get("service_tier") != dispatch.service_tier:  # noqa: E501
            raise AdapterError("provider request changed after effect reservation")
        expected_identity = (self.profile.disclosure_profile, contracts.DISCLOSURE_NOTICE_DIGEST,
            True, self.profile.service_tier, self.profile.project_id,
            self.profile.service_account_id, self.profile.api_key_id, self.credential_generation)
        observed_identity = (dispatch.disclosure_profile, dispatch.disclosure_notice_digest,
            dispatch.external_disclosure_ack, dispatch.service_tier, dispatch.project_id,
            dispatch.service_account_id, dispatch.api_key_id, dispatch.credential_generation)
        if (observed_identity != expected_identity
                or self.credential_generation != self.profile.credential_generation):
            raise AdapterError("provider identity changed after effect reservation")
        if any(name.startswith("OPENAI_") for name in os.environ):
            raise AdapterError("unsupported ambient OpenAI configuration is present")
        key = _read_api_key(self.credential_file, self.profile.credential_sha256)
        client_request_id = str(uuid.uuid5(uuid.NAMESPACE_URL, dispatch.digest()))
        started = datetime.now(UTC)
        remaining_seconds = (dispatch.wall_deadline - started).total_seconds()
        if remaining_seconds <= 0:
            raise AdapterError("model request exceeded the wall deadline")
        client, cleanup_ambiguous, provider_status = None, False, None
        request_ambiguous = False
        monotonic_deadline = asyncio.get_running_loop().time() + remaining_seconds
        try:
            http_client = DefaultAsyncHttpxClient(trust_env=False, follow_redirects=False)
            client = self.client_factory(
                api_key=key, base_url=self.profile.endpoint, max_retries=0,
                timeout=min(float(dispatch.wall_timeout_seconds), remaining_seconds),
                organization="", project=self.profile.project_id, admin_api_key="",
                webhook_secret="", default_headers={"Authorization": f"Bearer {key}",
                    "OpenAI-Project": self.profile.project_id, "OpenAI-Organization": Omit()},
                http_client=http_client,
            )
            async with asyncio.timeout_at(monotonic_deadline):
                headers = {"X-Client-Request-Id": client_request_id}
                response = await client.responses.create(**request_body, extra_headers=headers)
                completed = datetime.now(UTC)
        except APIStatusError as exc:
            provider_status = exc.status_code
        except Exception:
            request_ambiguous = True
        finally:
            if client is not None:
                close = getattr(client, "close", None)
                if callable(close):
                    try:
                        async with asyncio.timeout_at(monotonic_deadline):
                            await close()
                    except Exception:
                        cleanup_ambiguous = True
        if request_ambiguous:
            raise ProviderAmbiguousError("OpenAI request outcome is ambiguous") from None
        if provider_status is not None:
            if provider_status in {400, 401, 403, 404, 422} and not cleanup_ambiguous:
                raise ProviderRejectedError("OpenAI request was rejected") from None
            raise ProviderAmbiguousError("OpenAI request outcome is ambiguous") from None
        invalid_response = False
        try:
            status, request_id = response.status, response._request_id
            response_id, returned_model, service_tier, output_text = response.id, response.model, response.service_tier, response.output_text  # noqa: E501
            if not all(type(value) is str for value in (status, request_id, response_id, returned_model, service_tier, output_text)):  # noqa: E501
                raise ValueError
            if not request_id or not response_id:
                raise ValueError
            usage = response.usage
            invalid_fields = (_field_names(usage) != _USAGE_FIELDS
                or _field_names(usage.input_tokens_details) != _INPUT_DETAIL_FIELDS
                or _field_names(usage.output_tokens_details) != _OUTPUT_DETAIL_FIELDS)
            if invalid_fields:
                raise ValueError
            input_tokens, output_tokens, total_tokens = (
                usage.input_tokens, usage.output_tokens, usage.total_tokens)
            input_details = usage.input_tokens_details
            cached_tokens = input_details.cached_tokens
            cache_write_tokens = input_details.cache_write_tokens
            reasoning_tokens = usage.output_tokens_details.reasoning_tokens
            token_counts = (input_tokens, output_tokens, total_tokens, cached_tokens,
                            cache_write_tokens, reasoning_tokens)
            if any(type(value) is not int or value < 0 for value in token_counts):
                raise ValueError
        except Exception:
            invalid_response = True
        if invalid_response or service_tier != dispatch.service_tier:
            raise ProviderAmbiguousError("OpenAI response or usage is invalid") from None
        if (total_tokens != input_tokens + output_tokens
                or cached_tokens + cache_write_tokens > input_tokens
                or reasoning_tokens > output_tokens):
            raise ProviderAmbiguousError("OpenAI usage is inconsistent")
        cost = usd_upper_bound(input_tokens, output_tokens)
        observed = (input_tokens, output_tokens, reasoning_tokens, cost)
        limits = (dispatch.input_token_upper_bound, dispatch.max_output_tokens,
                  self.profile.max_reasoning_tokens, dispatch.max_usd_micros)
        if any(value > limit for value, limit in zip(observed, limits, strict=True)):
            raise ProviderAmbiguousError("OpenAI usage exceeds the reserved budget")
        audit = contracts.ProviderAudit(
            workflow_id=dispatch.workflow_id, request_digest=dispatch.request_digest,
            release_profile_digest=dispatch.release_profile_digest,
            client_request_id=client_request_id, provider_request_id=request_id,
            response_id=response_id, requested_model=dispatch.model,
            returned_model=returned_model, service_tier=service_tier, status=status, input_tokens=input_tokens,  # noqa: E501
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
        invalid_output = False
        try:
            brief = contracts.EvidenceBrief.model_validate_json(output_text)
        except ValueError:
            invalid_output = True
        if invalid_output:
            raise ProviderRejectedError("OpenAI output failed the response schema", audit) from None
        result_digest = contracts.canonical_digest(brief.model_dump(mode="json"))
        audit = audit.model_copy(update={"validated_result_digest": result_digest})
        audit = audit.model_copy(update={"record_digest": contracts.provider_record_digest(brief, audit)})  # noqa: E501
        return contracts.ProviderResult(brief=brief, audit=audit)
