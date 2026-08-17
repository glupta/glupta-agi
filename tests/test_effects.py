from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock, patch

import pytest

from glupta_agi.effects import _effect, initialize


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "workflow_id": "workflow-1",
        "slot_id": "model-0",
        "request_digest": "digest-1",
        "model_name": "gpt-5.6-sol",
        "max_calls": 1,
        "state": "reserved",
        "thread_id": None,
        "turn_id": None,
        "result_json": None,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    "overrides",
    [
        {"slot_id": "model-1"},
        {"max_calls": 2},
    ],
)
def test_effect_row_rejects_any_slot_or_budget_drift(overrides: dict[str, object]) -> None:
    with pytest.raises(RuntimeError, match="single-call Crawl contract"):
        _effect(_row(**overrides))


def test_effect_row_accepts_the_predeclared_single_call_slot() -> None:
    effect = _effect(_row())

    case = TestCase()
    case.assertEqual(effect.workflow_id, "workflow-1")
    case.assertEqual(effect.state, "reserved")


def test_initialize_rejects_an_unversioned_existing_effect_table() -> None:
    datasource = Mock()
    inspector = Mock()
    inspector.has_table.return_value = True
    inspector.get_table_comment.return_value = {"text": None}
    with (
        patch(
            "glupta_agi.effects.SQLAlchemyDatasource.create",
            return_value=datasource,
        ),
        patch("glupta_agi.effects.sa.inspect", return_value=inspector),
        pytest.raises(RuntimeError, match="schema version is not recognized"),
    ):
        initialize("postgresql://local/test")

    datasource.engine.begin.assert_not_called()
