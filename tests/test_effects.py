from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock, patch

import pytest

from glupta_agi.effects import _effect, initialize
from glupta_agi.inference import FrozenDispatch


def _row(**overrides: object) -> dict[str, object]:
    dispatch = FrozenDispatch(
        workflow_id="0198be50-0000-7000-8000-000000000000",
        request_digest="a" * 64,
        request_body_digest="c" * 64,
        release_profile_digest="d" * 64,
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
    effect = _effect(_row(result_json={"answer": "grounded"}, audit_json={"total_tokens": 10}))
    case = TestCase()
    case.assertEqual(effect.state, "reserved")
    case.assertEqual(effect.dispatch["max_usd_micros"], 1_850_000)
    case.assertEqual(effect.dispatch["queue_deadline"], "2099-01-01T00:00:00Z")
    case.assertEqual(effect.result, {"answer": "grounded"})
    case.assertEqual(effect.audit, {"total_tokens": 10})


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
