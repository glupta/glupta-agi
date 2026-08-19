# ruff: noqa: S101,S108
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from openai_codex.generated.v2_all import (
    Account,
    ChatgptAccount,
    GetAccountResponse,
    PlanType,
    ReasoningEffort,
    TurnStatus,
)

from glupta_agi import contracts
from glupta_agi.codex_adapter import (
    AdapterError,
    CodexSubscriptionAdapter,
    ProviderAmbiguousError,
    ProviderRejectedError,
    _launch_args,
)
from glupta_agi.inference import FrozenDispatch
from tests.helpers import release_profile


def _body() -> dict[str, object]:
    return {"input": "grounded prompt", "model": "gpt-5.6-sol"}


def _dispatch(**changes: object) -> FrozenDispatch:
    profile, body = release_profile(), _body()
    values = {
        "workflow_id": "0198be50-0000-7000-8000-000000000000",
        "request_digest": "a" * 64,
        "request_body_digest": contracts.canonical_digest(body),
        "release_profile_digest": profile.digest(),
        "disclosure_profile": "external_disclosed_v1",
        "disclosure_notice_digest": contracts.DISCLOSURE_NOTICE_DIGEST,
        "external_disclosure_ack": True,
        "subscription_route_id": "crawl_subscription",
        "subscription_plan": "pro",
        "auth_generation": 1,
        "model": "gpt-5.6-sol",
        "reasoning_effort": "medium",
        "input_bytes": 100,
        "queue_deadline": datetime.now(UTC) + timedelta(minutes=5),
        "wall_deadline": datetime.now(UTC) + timedelta(minutes=5),
    }
    values.update(changes)
    return FrozenDispatch.model_validate(values)


class FakeThread:
    id = "thread_1"

    def __init__(self, result: object) -> None:
        self.result, self.run_kwargs = result, None

    async def run(self, prompt: str, **kwargs: object) -> object:
        self.run_kwargs = prompt, kwargs
        return self.result


class FakeClient:
    def __init__(
        self,
        result: object,
        *,
        plan: PlanType = PlanType.pro,
        account: bool = True,
        close_error: bool = False,
    ) -> None:
        root = ChatgptAccount(email=None, planType=plan, type="chatgpt") if account else None
        self.account_response = GetAccountResponse(
            account=None if root is None else Account(root), requiresOpenaiAuth=True
        )
        self.thread, self.close_error = FakeThread(result), close_error
        self.thread_kwargs = None

    async def account(self, **_: object) -> object:
        return self.account_response

    async def models(self) -> object:
        effort = SimpleNamespace(reasoning_effort=ReasoningEffort.medium)
        return SimpleNamespace(
            data=[SimpleNamespace(model="gpt-5.6-sol", supported_reasoning_efforts=[effort])]
        )

    async def thread_start(self, **kwargs: object) -> FakeThread:
        self.thread_kwargs = kwargs
        return self.thread

    async def close(self) -> None:
        if self.close_error:
            raise RuntimeError("RAW_CLOSE")


def _result(**changes: object) -> object:
    brief = {"answer": "Grounded.", "citations": [], "uncertainties": [], "next_decisions": []}
    usage = SimpleNamespace(
        last=SimpleNamespace(
            input_tokens=100,
            cached_input_tokens=10,
            cache_write_input_tokens=0,
            output_tokens=20,
            reasoning_output_tokens=5,
            total_tokens=120,
        )
    )
    values = {
        "id": "turn_1",
        "status": TurnStatus.completed,
        "final_response": contracts.EvidenceBrief.model_validate(brief).model_dump_json(),
        "usage": usage,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_exact_subscription_account_and_native_safety_controls() -> None:
    client, constructed, phases = FakeClient(_result()), [], []

    def factory(config: object) -> FakeClient:
        constructed.append(config)
        return client

    result = asyncio.run(
        CodexSubscriptionAdapter(
            release_profile(), Path("/private/codex"), auth_generation=1,
            phase_recorder=phases.append, client_factory=factory
        ).generate(_dispatch(), _body())
    )
    assert result.audit.subscription_plan == "pro"
    assert result.audit.thread_id == "thread_1" and result.audit.turn_id == "turn_1"
    assert len(constructed) == 1 and "env" in constructed[0].launch_args_override[0]
    assert client.thread_kwargs["ephemeral"] is True
    assert client.thread_kwargs["sandbox"].value == "read-only"
    assert client.thread_kwargs["approval_mode"].value == "deny_all"
    prompt, kwargs = client.thread.run_kwargs
    assert prompt == "grounded prompt" and kwargs["effort"] == ReasoningEffort.medium
    assert kwargs["output_schema"] == contracts.EvidenceBrief.model_json_schema()
    assert phases == ["account_lookup_started", "model_catalog_started",
        "thread_start_started", "turn_invocation_started", "turn_returned"]


def test_clean_launcher_uses_only_env_i_and_explicit_runtime_state() -> None:
    with (
        patch("glupta_agi.codex_adapter.shutil.which", return_value="/usr/bin/env") as which,
        patch("glupta_agi.codex_adapter.bundled_path_dir", return_value=None),
        patch("glupta_agi.codex_adapter.bundled_codex_path", return_value=Path("/codex")),
        patch.dict(os.environ, {"UNAPPROVED_AMBIENT": "must-not-pass"}, clear=True),
    ):
        args = _launch_args(Path("/private/codex"), Path("/tmp/state"))

    which.assert_called_once_with("env", path=os.defpath)
    assert args[:2] == ("/usr/bin/env", "-i")
    assert f"PATH={os.defpath}" in args
    assert "CODEX_HOME=/private/codex" in args
    assert "UNAPPROVED_AMBIENT=must-not-pass" not in args
    assert args[-2:] == ("--listen", "stdio://")


def test_missing_clean_launcher_fails_before_sdk_construction() -> None:
    constructed = False

    def factory(_: object) -> object:
        nonlocal constructed
        constructed = True
        raise AssertionError

    with (
        patch.dict(os.environ, {}, clear=True),
        patch("glupta_agi.codex_adapter.shutil.which", return_value=None),
        pytest.raises(AdapterError, match="clean Codex environment launcher is unavailable"),
    ):
        asyncio.run(
            CodexSubscriptionAdapter(
                release_profile(),
                Path("/private/codex"),
                auth_generation=1,
                phase_recorder=lambda _phase: None,
                client_factory=factory,
            ).generate(_dispatch(), _body())
        )
    assert constructed is False


@pytest.mark.parametrize("ambient", ["OPENAI_API_KEY", "OPENAI_BASE_URL", "CODEX_API_KEY"])
def test_metered_or_ambient_provider_routes_reject_before_client(ambient: str) -> None:
    built = False

    def factory(_: object) -> object:
        nonlocal built
        built = True
        raise AssertionError

    with (
        patch.dict(os.environ, {ambient: "RAW_SECRET"}, clear=True),
        pytest.raises(AdapterError, match="metered or ambient"),
    ):
        asyncio.run(
            CodexSubscriptionAdapter(
                release_profile(), Path("/private/codex"), auth_generation=1,
                phase_recorder=lambda _phase: None, client_factory=factory
            ).generate(_dispatch(), _body())
        )
    assert built is False


def test_wrong_plan_invalid_usage_and_cleanup_fail_closed() -> None:
    cases = (
        (FakeClient(_result(), plan=PlanType.self_serve_business_usage_based), AdapterError),
        (FakeClient(_result(usage=None)), ProviderRejectedError),
        (FakeClient(_result(), close_error=True), ProviderAmbiguousError),
    )
    for client, expected in cases:
        with pytest.raises(expected):
            asyncio.run(
                CodexSubscriptionAdapter(
                    release_profile(),
                    Path("/private/codex"),
                    auth_generation=1,
                    phase_recorder=lambda _phase: None,
                    client_factory=lambda _config, value=client: value,
                ).generate(_dispatch(), _body())
            )


@pytest.mark.parametrize(
    ("boundary", "phases"),
    [
        ("account", ["account_lookup_started"]),
        ("models", ["account_lookup_started", "model_catalog_started"]),
        ("thread_start", ["account_lookup_started", "model_catalog_started",
            "thread_start_started"]),
    ],
)
def test_each_pre_turn_boundary_is_proven_and_terminal(
    boundary: str, phases: list[str]
) -> None:
    client, observed = FakeClient(_result()), []

    async def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("RAW_PRE_TURN")

    setattr(client, boundary, fail)
    adapter = CodexSubscriptionAdapter(release_profile(), Path("/private/codex"),
        auth_generation=1, phase_recorder=observed.append, client_factory=lambda _: client)
    with pytest.raises(AdapterError) as caught:
        asyncio.run(adapter.generate(_dispatch(), _body()))
    assert observed == phases
    assert "RAW_PRE_TURN" not in str(caught.value)
    assert client.thread.run_kwargs is None


@pytest.mark.parametrize("failed_phase", ["account_lookup_started", "model_catalog_started",
    "thread_start_started", "turn_invocation_started"])
def test_pre_turn_phase_persistence_failure_never_invokes_turn(failed_phase: str) -> None:
    client, phases = FakeClient(_result()), []

    def record(phase: str) -> None:
        phases.append(phase)
        if phase == failed_phase:
            raise RuntimeError("RAW_LOST_PHASE_ACK")

    adapter = CodexSubscriptionAdapter(release_profile(), Path("/private/codex"),
        auth_generation=1, phase_recorder=record, client_factory=lambda _: client)
    with pytest.raises(AdapterError) as caught:
        asyncio.run(adapter.generate(_dispatch(), _body()))
    assert phases[-1] == failed_phase
    assert client.thread.run_kwargs is None
    assert "RAW_LOST_PHASE_ACK" not in str(caught.value)


def test_turn_invocation_or_returned_phase_failure_is_ambiguous() -> None:
    for failure in ("turn", "returned_phase"):
        client, phases = FakeClient(_result()), []
        if failure == "turn":
            async def fail(*_args: object, **_kwargs: object) -> None:
                raise RuntimeError("RAW_TURN")
            client.thread.run = fail  # type: ignore[method-assign]

        def record(phase: str, *, seen: list[str] = phases, fail_at: str = failure) -> None:
            seen.append(phase)
            if fail_at == "returned_phase" and phase == "turn_returned":
                raise RuntimeError("RAW_PHASE_ACK")

        adapter = CodexSubscriptionAdapter(release_profile(), Path("/private/codex"),
            auth_generation=1, phase_recorder=record,
            client_factory=lambda _, value=client: value)
        with pytest.raises(ProviderAmbiguousError) as caught:
            asyncio.run(adapter.generate(_dispatch(), _body()))
        assert "turn_invocation_started" in phases
        assert "RAW_" not in str(caught.value)


def test_request_identity_and_observed_usage_are_bound() -> None:
    client = FakeClient(_result())
    adapter = CodexSubscriptionAdapter(
        release_profile(),
        Path("/private/codex"),
        auth_generation=1,
        phase_recorder=lambda _phase: None,
        client_factory=lambda _: client,
    )
    with pytest.raises(AdapterError):
        asyncio.run(adapter.generate(_dispatch(subscription_plan="plus"), _body()))
    excessive = SimpleNamespace(
        last=SimpleNamespace(
            input_tokens=100,
            cached_input_tokens=0,
            cache_write_input_tokens=0,
            output_tokens=8_001,
            reasoning_output_tokens=1,
            total_tokens=8_101,
        )
    )
    adapter = CodexSubscriptionAdapter(
        release_profile(),
        Path("/private/codex"),
        auth_generation=1,
        phase_recorder=lambda _phase: None,
        client_factory=lambda _: FakeClient(_result(usage=excessive)),
    )
    with pytest.raises(ProviderRejectedError, match="observed ceiling"):
        asyncio.run(adapter.generate(_dispatch(), _body()))
