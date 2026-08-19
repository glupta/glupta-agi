# ruff: noqa: E501
from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codex_cli_bin import bundled_codex_path, bundled_path_dir
from openai_codex import ApprovalMode, AsyncCodex, CodexConfig, Sandbox
from openai_codex.generated.v2_all import ChatgptAccount, ReasoningEffort, TurnStatus, WebSearchMode

from . import contracts
from .brief import SYSTEM_PROMPT
from .inference import RUNTIME_VERSION, SDK_VERSION, FrozenDispatch, ReleaseProfile

_BLOCKED_ENV = {"CODEX_API_KEY", "CODEX_ACCESS_TOKEN"}
_DISABLED_FEATURES = ("apps", "multi_agent", "plugins", "remote_plugin", "shell_tool", "skill_search")


class AdapterError(RuntimeError):
    def __init__(self, message: str, audit: contracts.ProviderAudit | None = None) -> None:
        super().__init__(message)
        self.audit = audit


class ProviderAmbiguousError(AdapterError):
    pass


class ProviderRejectedError(AdapterError):
    pass


def _launch_args(codex_home: Path, state_home: Path) -> tuple[str, ...]:
    env_binary = shutil.which("env", path=os.defpath)
    if env_binary is None:
        raise AdapterError("clean Codex environment launcher is unavailable")
    path = os.defpath
    if (tools := bundled_path_dir()) is not None:
        path = os.pathsep.join((str(tools), path))
    environment = {"CODEX_HOME": str(codex_home), "HOME": str(codex_home.parent), "LANG": "C.UTF-8", "PATH": path, "TMPDIR": tempfile.gettempdir(), "STUDIO_CODEX_SESSION_ORIGIN": "glupta-crawl-subscription-v1"}
    assignments = tuple(f"{key}={value}" for key, value in sorted(environment.items()))
    disabled = tuple(arg for feature in ("apps", "plugins", "remote_plugin") for arg in ("--disable", feature))
    return (env_binary, "-i", *assignments, str(bundled_codex_path()), "-c", 'cli_auth_credentials_store="file"', "-c", 'history.persistence="none"', "-c", f"sqlite_home={json.dumps(str(state_home))}", "app-server", *disabled, "--listen", "stdio://")


class CodexSubscriptionAdapter:
    def __init__(self, profile: ReleaseProfile, codex_home: Path, *, auth_generation: int,
        phase_recorder: Any, client_factory: Any = AsyncCodex) -> None:
        self.profile, self.codex_home, self.phase_recorder = profile, codex_home, phase_recorder
        self.auth_generation, self.client_factory = auth_generation, client_factory

    async def generate(self, dispatch: FrozenDispatch, request_body: dict[str, Any]) -> contracts.ProviderResult:
        error: tuple[type[AdapterError], str, contracts.ProviderAudit | None] | None = None
        try:
            result = await self._generate(dispatch, request_body)
        except AdapterError as exc:
            error = type(exc), str(exc), exc.audit
        except (Exception, asyncio.CancelledError):
            error = ProviderAmbiguousError, "Codex subscription outcome is ambiguous", None
        if error is not None:
            del self, dispatch, request_body
            raise error[0](error[1], error[2]) from None
        return result

    async def _generate(self, dispatch: FrozenDispatch, request_body: dict[str, Any]) -> contracts.ProviderResult:
        if not self.profile.current_at() or dispatch.release_profile_digest != self.profile.digest() or dispatch.request_body_digest != contracts.canonical_digest(request_body):
            raise AdapterError("subscription request changed after effect reservation")
        identity = dispatch.subscription_route_id, dispatch.subscription_plan, dispatch.auth_generation, dispatch.model, dispatch.reasoning_effort
        expected = self.profile.subscription_route_id, self.profile.subscription_plan, self.auth_generation, self.profile.model, self.profile.reasoning_effort
        if identity != expected or self.auth_generation != self.profile.auth_generation:
            raise AdapterError("subscription identity changed after effect reservation")
        if any(name.startswith("OPENAI_") or name in _BLOCKED_ENV for name in os.environ):
            raise AdapterError("metered or ambient provider configuration is present")
        started = datetime.now(UTC)
        if (remaining := (dispatch.wall_deadline - started).total_seconds()) <= 0:
            raise AdapterError("model request exceeded the wall deadline")
        client = result = thread = completed = None
        error: AdapterError | None = None
        cleanup_failed = turn_invoked = False
        try:
            with tempfile.TemporaryDirectory(prefix="glupta-crawl-") as cwd, tempfile.TemporaryDirectory(prefix="glupta-codex-state-") as state:
                client = self.client_factory(CodexConfig(cwd=cwd, launch_args_override=_launch_args(self.codex_home, Path(state))))
                async with asyncio.timeout(remaining):
                    self.phase_recorder("account_lookup_started")
                    account_response = await client.account(refresh_token=False)
                    account = None if account_response.account is None else account_response.account.root
                    if not isinstance(account, ChatgptAccount) or account.plan_type.value != dispatch.subscription_plan:
                        raise AdapterError("approved ChatGPT subscription is unavailable")
                    self.phase_recorder("model_catalog_started")
                    models = await client.models()
                    model = next((item for item in models.data if item.model == dispatch.model), None)
                    efforts = () if model is None else model.supported_reasoning_efforts
                    if model is None or not any(item.reasoning_effort == ReasoningEffort.medium for item in efforts):
                        raise AdapterError("approved Codex model is unavailable")
                    config = {"features": {feature: False for feature in _DISABLED_FEATURES}, "model_provider": "crawl_openai", "model_providers": {"crawl_openai": {"name": "OpenAI", "requires_openai_auth": True, "wire_api": "responses", "request_max_retries": 0, "stream_max_retries": 0}}, "tools": {"view_image": False}, "web_search": WebSearchMode.disabled.value}
                    self.phase_recorder("thread_start_started")
                    thread = await client.thread_start(approval_mode=ApprovalMode.deny_all, base_instructions=SYSTEM_PROMPT, config=config, cwd=cwd, ephemeral=True, model=dispatch.model, sandbox=Sandbox.read_only)
                    self.phase_recorder("turn_invocation_started")
                    turn_invoked = True
                    result = await thread.run(str(request_body["input"]), approval_mode=ApprovalMode.deny_all, cwd=cwd, effort=ReasoningEffort.medium, model=dispatch.model, output_schema=contracts.EvidenceBrief.model_json_schema(), sandbox=Sandbox.read_only)
                    self.phase_recorder("turn_returned")
                    completed = datetime.now(UTC)
        except (Exception, asyncio.CancelledError) as exc:
            error_type = ProviderAmbiguousError if turn_invoked else AdapterError
            error = exc if isinstance(exc, AdapterError) else error_type("Codex subscription scope failed")
        finally:
            if client is not None:
                try:
                    remaining = max(0.001, (dispatch.wall_deadline - datetime.now(UTC)).total_seconds())
                    async with asyncio.timeout(remaining):
                        await client.close()
                except (Exception, asyncio.CancelledError):
                    cleanup_failed = True
        if cleanup_failed:
            error_type = ProviderAmbiguousError if turn_invoked else AdapterError
            raise error_type("Codex subscription cleanup failed")
        if error is not None:
            raise error
        if result is None or thread is None or completed is None:
            raise ProviderAmbiguousError("Codex subscription outcome is ambiguous")
        if result.status != TurnStatus.completed or completed > dispatch.wall_deadline:
            raise ProviderRejectedError("Codex subscription turn was not completed")
        try:
            usage = result.usage.last
            counts = usage.input_tokens, usage.cached_input_tokens, usage.cache_write_input_tokens or 0, usage.output_tokens, usage.reasoning_output_tokens, usage.total_tokens
            if any(type(value) is not int or value < 0 for value in counts):
                raise ValueError
            brief = contracts.EvidenceBrief.model_validate_json(result.final_response or "")
        except (AttributeError, ValueError):
            raise ProviderRejectedError("Codex subscription output or usage is invalid") from None
        input_tokens, cached, cache_write, output_tokens, reasoning, total = counts
        limits = dispatch.max_observed_input_tokens, dispatch.max_observed_output_tokens, dispatch.max_observed_reasoning_tokens
        if total != input_tokens + output_tokens or cached + cache_write > input_tokens or reasoning > output_tokens or any(value > limit for value, limit in zip((input_tokens, output_tokens, reasoning), limits, strict=True)):
            raise ProviderRejectedError("Codex subscription usage exceeded the observed ceiling")
        audit = contracts.ProviderAudit(workflow_id=dispatch.workflow_id, request_digest=dispatch.request_digest, release_profile_digest=dispatch.release_profile_digest, subscription_route_id=dispatch.subscription_route_id, subscription_plan=dispatch.subscription_plan, sdk_version=SDK_VERSION, runtime_version=RUNTIME_VERSION, thread_id=thread.id, turn_id=result.id, requested_model=dispatch.model, reasoning_effort=dispatch.reasoning_effort, status="completed", input_tokens=input_tokens, cached_input_tokens=cached, cache_write_input_tokens=cache_write, output_tokens=output_tokens, reasoning_tokens=reasoning, total_tokens=total, request_body_digest=dispatch.request_body_digest, output_digest=contracts.canonical_digest(result.final_response), started_at=started, completed_at=completed)
        digest = contracts.canonical_digest(brief.model_dump(mode="json"))
        audit = audit.model_copy(update={"validated_result_digest": digest})
        audit = audit.model_copy(update={"record_digest": contracts.provider_record_digest(brief, audit)})
        return contracts.ProviderResult(brief=brief, audit=audit)
