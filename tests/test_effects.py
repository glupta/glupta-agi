from __future__ import annotations

import traceback
from datetime import UTC, datetime
from unittest import TestCase
from unittest.mock import Mock, patch

import pytest

from glupta_agi.contracts import (
    DISCLOSURE_NOTICE_DIGEST,
    EvidenceBrief,
    ProviderAudit,
    canonical_digest,
    provider_record_digest,
)
from glupta_agi.effects import AmbiguousEffectError, _effect, hold_unknown, initialize
from glupta_agi.inference import FrozenDispatch


def _row(**overrides: object) -> dict[str, object]:
    dispatch = FrozenDispatch(
        workflow_id="0198be50-0000-7000-8000-000000000000",
        request_digest="a" * 64,
        request_body_digest="c" * 64,
        release_profile_digest="d" * 64,
        disclosure_profile="external_disclosed_v1",
        disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
        external_disclosure_ack=True,
        project_id="proj_crawl",
        service_account_id="svc_crawl",
        api_key_id="key_crawl",
        credential_generation=1,
        input_token_upper_bound=1_000,
        queue_deadline="2099-01-01T00:00:00Z",
        wall_deadline="2099-01-01T00:00:00Z",
    )
    dispatch_json = dispatch.model_dump(mode="json")
    row: dict[str, object] = {
        "workflow_id": dispatch.workflow_id,
        "slot_id": "model-0",
        "request_digest": dispatch.request_digest,
        "dispatch_digest": dispatch.digest(),
        "max_calls": 1,
        "max_usd_micros": 1_850_000,
        "state": "reserved",
        "dispatch_json": dispatch_json,
        "result_json": None,
        "audit_json": None,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    "overrides",
    [
        {"slot_id": "model-1"},
        {"max_calls": 2},
        {"max_usd_micros": 1_850_001},
        {"dispatch_json": None},
        {"dispatch_digest": "b" * 64},
        {
            "dispatch_json": {
                **_row()["dispatch_json"],
                "queue_deadline": "2099-01-01T00:00:01Z",
            }
        },
    ],
)
def test_effect_row_rejects_call_or_budget_drift(overrides: dict[str, object]) -> None:
    with pytest.raises(RuntimeError):
        _effect(_row(**overrides))


def test_effect_row_retains_frozen_dispatch_result_and_audit() -> None:
    effect = _effect(
        _row(
            result_json={"answer": "grounded"},
            audit_json={"total_tokens": 10},
            hold_reason="provider_rejected",
        )
    )
    case = TestCase()
    case.assertEqual(effect.state, "reserved")
    case.assertEqual(effect.dispatch["max_usd_micros"], 1_850_000)
    case.assertEqual(effect.dispatch["queue_deadline"], "2099-01-01T00:00:00Z")
    case.assertEqual(effect.result, {"answer": "grounded"})
    case.assertEqual(effect.audit, {"total_tokens": 10})
    case.assertEqual(effect.hold_reason, "provider_rejected")


def _bound_result_and_audit() -> tuple[dict[str, object], dict[str, object]]:
    result = EvidenceBrief(
        answer="Grounded.", citations=[], uncertainties=[], next_decisions=[]
    ).model_dump(mode="json")
    provider_audit = ProviderAudit(
        workflow_id="0198be50-0000-7000-8000-000000000000",
        request_digest="a" * 64,
        release_profile_digest="d" * 64,
        client_request_id="client_1",
        provider_request_id="req_1",
        response_id="resp_1",
        requested_model="gpt-5.6-sol",
        returned_model="gpt-5.6-sol",
        status="completed",
        input_tokens=100,
        cached_input_tokens=0,
        cache_write_input_tokens=0,
        output_tokens=20,
        reasoning_tokens=5,
        total_tokens=120,
        cost_upper_bound_micros=1_225,
        request_body_digest="c" * 64,
        output_digest="e" * 64,
        validated_result_digest=canonical_digest(result),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    brief = EvidenceBrief.model_validate(result)
    audit = provider_audit.model_copy(
        update={"record_digest": provider_record_digest(brief, provider_audit)}
    ).model_dump(mode="json")
    return result, audit


def test_reconciled_effect_requires_exact_result_dispatch_and_audit_binding() -> None:
    result, audit = _bound_result_and_audit()
    effect = _effect(_row(state="reconciled", result_json=result, audit_json=audit))
    case = TestCase()
    case.assertEqual(effect.result, result)
    case.assertEqual(effect.audit, audit)

    mutations = (
        ({**result, "answer": "tampered"}, audit),
        (result, {**audit, "validated_result_digest": "f" * 64}),
        (result, {**audit, "request_body_digest": "f" * 64}),
        (result, {**audit, "requested_model": "drifted"}),
        (result, {**audit, "cost_upper_bound_micros": 1_850_001}),
        (result, {**audit, "returned_model": "drifted"}),
        (result, {**audit, "status": "failed"}),
        (result, {**audit, "total_tokens": 999}),
        (result, {**audit, "response_id": "tampered"}),
    )
    for changed_result, changed_audit in mutations:
        with pytest.raises(RuntimeError, match="do not match"):
            _effect(
                _row(
                    state="reconciled",
                    result_json=changed_result,
                    audit_json=changed_audit,
                )
            )


def test_initialize_rejects_any_prior_or_unversioned_schema() -> None:
    datasource = Mock()
    inspector = Mock()
    inspector.has_table.return_value = True
    for comment in (None, "glupta-crawl-external-effects-v1"):
        inspector.get_table_comment.return_value = {"text": comment}
        with (
            patch("glupta_agi.effects.SQLAlchemyDatasource.create", return_value=datasource),
            patch("glupta_agi.effects.sa.inspect", return_value=inspector),
            pytest.raises(RuntimeError, match="schema version is not recognized"),
        ):
            initialize("postgresql://local/test")
    datasource.engine.begin.assert_not_called()


def test_unknown_hold_retries_ambiguous_ack_and_always_raises_redacted() -> None:
    unknown = _effect(_row(state="unknown"))
    case = TestCase()
    with (
        patch(
            "glupta_agi.effects.transition",
            side_effect=[RuntimeError("RAW_DB"), unknown],
        ) as mark,
        pytest.raises(AmbiguousEffectError) as caught,
    ):
        hold_unknown(unknown.workflow_id, "result_persistence_ambiguous")
    case.assertEqual(mark.call_count, 2)
    case.assertTrue(all(call.kwargs["recover_post_dispatch"] for call in mark.call_args_list))
    case.assertNotIn("RAW_DB", "".join(traceback.format_exception(caught.value)))
