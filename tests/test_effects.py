# ruff: noqa: S101
from __future__ import annotations

import traceback
from unittest.mock import Mock, patch

import pytest

from glupta_agi.contracts import DISCLOSURE_NOTICE_DIGEST, EvidenceBrief
from glupta_agi.effects import AmbiguousEffectError, _effect, hold_unknown, initialize
from glupta_agi.inference import FrozenDispatch
from tests.helpers import provider_audit


def _row(**overrides: object) -> dict[str, object]:
    dispatch = FrozenDispatch(
        workflow_id="0198be50-0000-7000-8000-000000000000",
        request_digest="a" * 64,
        request_body_digest="c" * 64,
        release_profile_digest="d" * 64,
        disclosure_profile="external_disclosed_v1",
        disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
        external_disclosure_ack=True,
        subscription_route_id="crawl_subscription",
        subscription_plan="pro",
        auth_generation=1,
        model="gpt-5.6-sol",
        reasoning_effort="medium",
        input_bytes=1_000,
        queue_deadline="2099-01-01T00:00:00Z",
        wall_deadline="2099-01-01T00:00:00Z",
    )
    row: dict[str, object] = {
        "workflow_id": dispatch.workflow_id,
        "slot_id": "model-0",
        "request_digest": dispatch.request_digest,
        "dispatch_digest": dispatch.digest(),
        "max_calls": 1,
        "max_input_bytes": 1_000,
        "state": "reserved",
        "dispatch_json": dispatch.model_dump(mode="json"),
        "result_json": None,
        "audit_json": None,
        "hold_reason": None,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    "change",
    [
        {"slot_id": "model-1"},
        {"max_calls": 2},
        {"max_input_bytes": 999},
        {"dispatch_digest": "b" * 64},
        {"dispatch_json": None},
    ],
)
def test_effect_rejects_identity_or_budget_drift(change: dict[str, object]) -> None:
    with pytest.raises(RuntimeError):
        _effect(_row(**change))


def test_reconciled_effect_requires_exact_subscription_result_binding() -> None:
    brief = EvidenceBrief(answer="Grounded.", citations=[], uncertainties=[], next_decisions=[])
    result = brief.model_dump(mode="json")
    audit = provider_audit(
        brief,
        workflow_id=str(_row()["workflow_id"]),
        request_digest="a" * 64,
        release_profile_digest="d" * 64,
        request_body_digest="c" * 64,
    ).model_dump(mode="json")
    assert _effect(_row(state="reconciled", result_json=result, audit_json=audit)).result == result
    mutations = (
        {**audit, "subscription_plan": "plus"},
        {**audit, "request_body_digest": "f" * 64},
        {**audit, "total_tokens": 999},
        {**audit, "thread_id": "tampered"},
    )
    for changed in mutations:
        with pytest.raises(RuntimeError, match="do not match"):
            _effect(_row(state="reconciled", result_json=result, audit_json=changed))


def test_initialize_rejects_prior_schema_and_unknown_hold_is_redacted() -> None:
    datasource, inspector = Mock(), Mock()
    inspector.has_table.return_value = True
    inspector.get_table_comment.return_value = {"text": "glupta-crawl-external-effects-v3"}
    with (
        patch("glupta_agi.effects.SQLAlchemyDatasource.create", return_value=datasource),
        patch("glupta_agi.effects.sa.inspect", return_value=inspector),
        pytest.raises(RuntimeError, match="not recognized"),
    ):
        initialize("postgresql://local/test")
    unknown = _effect(_row(state="unknown"))
    with (
        patch("glupta_agi.effects.transition", side_effect=[RuntimeError("RAW_DB"), unknown]),
        pytest.raises(AmbiguousEffectError) as caught,
    ):
        hold_unknown(unknown.workflow_id, "ambiguous")
    assert "RAW_DB" not in "".join(traceback.format_exception(caught.value))
