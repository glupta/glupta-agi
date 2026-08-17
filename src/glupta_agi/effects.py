"""One durable external-model effect slot for the Crawl workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from dbos import SQLAlchemyDatasource


class AmbiguousEffectError(RuntimeError):
    """A model call may have been accepted but has no safely replayable result."""


@dataclass(frozen=True)
class Effect:
    workflow_id: str
    request_digest: str
    model_name: str
    state: str
    thread_id: str | None
    turn_id: str | None
    result: dict[str, Any] | None


_datasource: SQLAlchemyDatasource | None = None

_SCHEMA_VERSION = "glupta-crawl-external-effects-v1"
_COLUMNS = {
    "workflow_id": ("TEXT", False),
    "slot_id": ("TEXT", False),
    "request_digest": ("TEXT", False),
    "model_name": ("TEXT", False),
    "max_calls": ("INTEGER", False),
    "state": ("TEXT", False),
    "thread_id": ("TEXT", True),
    "turn_id": ("TEXT", True),
    "result_json": ("JSONB", True),
    "hold_reason": ("TEXT", True),
    "updated_at": ("TIMESTAMP", False),
}
_STATES = (
    "reserved",
    "dispatching",
    "thread_started",
    "turn_started",
    "returned",
    "reconciled",
    "failed",
    "unknown",
)


def configure(datasource: SQLAlchemyDatasource) -> None:
    global _datasource
    _datasource = datasource


def _store() -> SQLAlchemyDatasource:
    if _datasource is None:
        raise RuntimeError("external effect datasource is not configured")
    return _datasource


def initialize(database_url: str) -> None:
    """Apply and verify the only Blueprint-permitted Crawl schema migration."""

    datasource = SQLAlchemyDatasource.create(database_url, schema="public")
    inspector = sa.inspect(datasource.engine)
    existed = inspector.has_table("crawl_external_effects", schema="public")
    if existed:
        comment = inspector.get_table_comment(
            "crawl_external_effects", schema="public"
        ).get("text")
        if comment != _SCHEMA_VERSION:
            raise RuntimeError("external effect schema version is not recognized")

    with datasource.engine.begin() as connection:
        connection.execute(
            sa.text(
                """
            CREATE TABLE IF NOT EXISTS crawl_external_effects (
                workflow_id TEXT PRIMARY KEY,
                slot_id TEXT NOT NULL CHECK (slot_id = 'model-0'),
                request_digest TEXT NOT NULL,
                model_name TEXT NOT NULL,
                max_calls INTEGER NOT NULL CHECK (max_calls = 1),
                state TEXT NOT NULL CHECK (
                    state IN (
                        'reserved', 'dispatching', 'thread_started', 'turn_started',
                        'returned', 'reconciled', 'failed', 'unknown'
                    )
                ),
                thread_id TEXT,
                turn_id TEXT,
                result_json JSONB,
                hold_reason TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
            )
        )
        if not existed:
            connection.execute(
                sa.text(f"COMMENT ON TABLE crawl_external_effects IS '{_SCHEMA_VERSION}'")
            )

    inspector = sa.inspect(datasource.engine)
    columns = {
        str(column["name"]): (str(column["type"]).upper(), bool(column["nullable"]))
        for column in inspector.get_columns("crawl_external_effects", schema="public")
    }
    primary_key = inspector.get_pk_constraint(
        "crawl_external_effects", schema="public"
    ).get("constrained_columns")
    checks = " ".join(
        str(check.get("sqltext", ""))
        for check in inspector.get_check_constraints(
            "crawl_external_effects", schema="public"
        )
    )
    if columns != _COLUMNS or primary_key != ["workflow_id"]:
        raise RuntimeError("external effect schema does not match the Crawl contract")
    updated_at = next(
        column
        for column in inspector.get_columns("crawl_external_effects", schema="public")
        if column["name"] == "updated_at"
    )
    if not bool(getattr(updated_at["type"], "timezone", False)):
        raise RuntimeError("external effect timestamp must retain timezone semantics")
    for required in ("slot_id", "model-0", "max_calls", "= 1", "state", *_STATES):
        if required not in checks:
            raise RuntimeError("external effect constraints do not match the Crawl contract")
    configure(datasource)


def _effect(row: dict[str, Any]) -> Effect:
    if row.get("slot_id") != "model-0" or row.get("max_calls") != 1:
        raise RuntimeError("external effect row violates the single-call Crawl contract")
    result = row.get("result_json")
    if isinstance(result, str):
        result = json.loads(result)
    return Effect(
        workflow_id=str(row["workflow_id"]),
        request_digest=str(row["request_digest"]),
        model_name=str(row["model_name"]),
        state=str(row["state"]),
        thread_id=None if row.get("thread_id") is None else str(row["thread_id"]),
        turn_id=None if row.get("turn_id") is None else str(row["turn_id"]),
        result=result if isinstance(result, dict) else None,
    )


def reserve(workflow_id: str, request_digest: str, model_name: str) -> Effect:
    """Predeclare the only possible model call and return its durable state."""

    datasource = _store()

    def transaction() -> Effect:
        session = datasource.sql_session()
        session.execute(
            sa.text(
                """
                INSERT INTO crawl_external_effects (
                    workflow_id, slot_id, request_digest, model_name, max_calls, state
                ) VALUES (:workflow_id, 'model-0', :digest, :model, 1, 'reserved')
                ON CONFLICT (workflow_id) DO NOTHING
                """
            ),
            {"workflow_id": workflow_id, "digest": request_digest, "model": model_name},
        )
        row = session.execute(
            sa.text(
                "SELECT * FROM crawl_external_effects "
                "WHERE workflow_id = :workflow_id FOR UPDATE"
            ),
            {"workflow_id": workflow_id},
        ).mappings().one_or_none()
        if row is None:
            raise RuntimeError("external effect reservation disappeared")
        effect = _effect(dict(row))
        if effect.request_digest != request_digest or effect.model_name != model_name:
            raise RuntimeError("external effect identity conflicts with recorded input")
        return effect

    return datasource.transaction(name="crawl_effect_reserve")(transaction)()


def transition(
    workflow_id: str,
    expected: str,
    state: str,
    *,
    thread_id: str | None = None,
    turn_id: str | None = None,
    result: dict[str, Any] | None = None,
    hold_reason: str | None = None,
) -> Effect:
    """Apply one exact state transition; races and replay mismatches fail closed."""

    datasource = _store()

    def transaction() -> Effect:
        row = datasource.sql_session().execute(
            sa.text(
                """
                UPDATE crawl_external_effects
                SET state = :state,
                    thread_id = COALESCE(:thread_id, thread_id),
                    turn_id = COALESCE(:turn_id, turn_id),
                    result_json = COALESCE(CAST(:result_json AS JSONB), result_json),
                    hold_reason = COALESCE(:hold_reason, hold_reason),
                    updated_at = NOW()
                WHERE workflow_id = :workflow_id AND state = :expected
                RETURNING *
                """
            ),
            {
                "state": state,
                "thread_id": thread_id,
                "turn_id": turn_id,
                "result_json": None if result is None else json.dumps(result, sort_keys=True),
                "hold_reason": hold_reason,
                "workflow_id": workflow_id,
                "expected": expected,
            },
        ).mappings().one_or_none()
        if row is None:
            raise RuntimeError("external effect transition conflicted")
        return _effect(dict(row))

    return datasource.transaction(name="crawl_effect_transition")(transaction)()


def hold_unknown(effect: Effect, reason: str) -> None:
    if effect.state != "unknown":
        transition(effect.workflow_id, effect.state, "unknown", hold_reason=reason)
    raise AmbiguousEffectError("model effect outcome is ambiguous; manual reconciliation required")
