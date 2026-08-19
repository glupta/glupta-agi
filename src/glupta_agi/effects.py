from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from dbos import SQLAlchemyDatasource

from .contracts import ProviderResult, validate_provider_record
from .inference import FrozenDispatch


class AmbiguousEffectError(RuntimeError):
    pass


class EffectConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class Effect:
    workflow_id: str
    request_digest: str
    dispatch_digest: str
    state: str
    dispatch: dict[str, Any]
    result: dict[str, Any] | None
    audit: dict[str, Any] | None
    hold_reason: str | None = None


_datasource: SQLAlchemyDatasource | None = None
_SCHEMA_VERSION = "glupta-crawl-external-effects-v4"
_TABLE = "crawl_external_effects_v4"
_STATES = ("reserved", "dispatching", "returned", "reconciled", "failed", "unknown")
_COLUMNS = {
    "workflow_id": ("TEXT", False),
    "slot_id": ("TEXT", False),
    "request_digest": ("TEXT", False),
    "dispatch_digest": ("TEXT", False),
    "max_calls": ("INTEGER", False),
    "max_input_bytes": ("INTEGER", False),
    "state": ("TEXT", False),
    "dispatch_json": ("JSONB", False),
    "result_json": ("JSONB", True),
    "audit_json": ("JSONB", True),
    "hold_reason": ("TEXT", True),
    "updated_at": ("TIMESTAMP", False),
}


def configure(datasource: SQLAlchemyDatasource) -> None:
    global _datasource
    _datasource = datasource


def _store() -> SQLAlchemyDatasource:
    if _datasource is None:
        raise RuntimeError("external effect datasource is not configured")
    return _datasource


def initialize(database_url: str) -> None:
    datasource = SQLAlchemyDatasource.create(database_url, schema="public")
    inspector = sa.inspect(datasource.engine)
    existed = inspector.has_table(_TABLE, schema="public")
    if (
        existed
        and inspector.get_table_comment(_TABLE, schema="public").get("text") != _SCHEMA_VERSION
    ):
        raise RuntimeError("external effect schema version is not recognized")
    with datasource.engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE IF NOT EXISTS crawl_external_effects_v4 ("
                "workflow_id TEXT PRIMARY KEY,request_digest TEXT NOT NULL,"
                "slot_id TEXT NOT NULL CHECK(slot_id='model-0'),dispatch_digest TEXT NOT NULL,"
                "max_calls INTEGER NOT NULL CHECK(max_calls=1),dispatch_json JSONB NOT NULL,"
                "max_input_bytes INTEGER NOT NULL CHECK(max_input_bytes>0),"
                "state TEXT NOT NULL CHECK(state IN ('reserved','dispatching','returned',"
                "'reconciled','failed','unknown')),result_json JSONB,audit_json JSONB,"
                "hold_reason TEXT,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )
        )
        if not existed:
            connection.execute(sa.text(f"COMMENT ON TABLE {_TABLE} IS '{_SCHEMA_VERSION}'"))
    inspector = sa.inspect(datasource.engine)
    inspected_columns = inspector.get_columns(_TABLE, schema="public")
    columns = {
        str(column["name"]): (str(column["type"]).upper(), bool(column["nullable"]))
        for column in inspected_columns
    }
    primary_key = inspector.get_pk_constraint(_TABLE, schema="public").get("constrained_columns")
    checks = " ".join(
        str(check.get("sqltext", ""))
        for check in inspector.get_check_constraints(_TABLE, schema="public")
    )
    if columns != _COLUMNS or primary_key != ["workflow_id"]:
        raise RuntimeError("external effect schema does not match the Crawl contract")
    updated_at = next(column for column in inspected_columns if column["name"] == "updated_at")
    if not bool(getattr(updated_at["type"], "timezone", False)):
        raise RuntimeError("external effect timestamp must retain timezone semantics")
    for required in ("model-0", "max_calls", "= 1", "max_input_bytes", *_STATES):
        if required not in checks:
            raise RuntimeError("external effect constraints do not match the Crawl contract")
    configure(datasource)


def _json(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    return value if isinstance(value, dict) else None


def _effect(row: dict[str, Any]) -> Effect:
    dispatch = _json(row.get("dispatch_json"))
    if row.get("slot_id") != "model-0" or row.get("max_calls") != 1 or dispatch is None:
        raise RuntimeError("external effect row violates the single-call Crawl contract")
    invalid_dispatch = False
    try:
        frozen = FrozenDispatch.model_validate(dispatch)
    except ValueError:
        invalid_dispatch = True
    if invalid_dispatch:
        raise RuntimeError("external effect row has an invalid frozen dispatch") from None
    if (
        frozen.model_dump(mode="json") != dispatch
        or str(row.get("workflow_id")) != frozen.workflow_id
        or str(row.get("request_digest")) != frozen.request_digest
        or str(row.get("dispatch_digest")) != frozen.digest()
        or int(row.get("max_input_bytes", 0)) != frozen.input_bytes
    ):
        raise RuntimeError("external effect row violates the frozen budget")
    result = _json(row.get("result_json"))
    audit = _json(row.get("audit_json"))
    if str(row.get("state")) == "reconciled":
        invalid_record = False
        try:
            record = validate_provider_record(
                ProviderResult.model_validate({"brief": result, "audit": audit})
            )
        except ValueError:
            invalid_record = True
        if invalid_record:
            raise RuntimeError("external effect result and audit do not match") from None
        provider_audit = record.audit
        invalid = (
            provider_audit.workflow_id != frozen.workflow_id,
            provider_audit.request_digest != frozen.request_digest,
            provider_audit.release_profile_digest != frozen.release_profile_digest,
            provider_audit.subscription_route_id != frozen.subscription_route_id,
            provider_audit.subscription_plan != frozen.subscription_plan,
            provider_audit.request_body_digest != frozen.request_body_digest,
            provider_audit.requested_model != frozen.model,
            provider_audit.reasoning_effort != frozen.reasoning_effort,
            provider_audit.status != "completed",
            provider_audit.input_tokens > frozen.max_observed_input_tokens,
            provider_audit.output_tokens > frozen.max_observed_output_tokens,
            provider_audit.reasoning_tokens > frozen.max_observed_reasoning_tokens,
        )
        if any(invalid):
            raise RuntimeError("external effect result and audit do not match")
    return Effect(
        workflow_id=str(row["workflow_id"]),
        request_digest=str(row["request_digest"]),
        dispatch_digest=str(row["dispatch_digest"]),
        state=str(row["state"]),
        dispatch=frozen.model_dump(mode="json"),
        result=result,
        audit=audit,
        hold_reason=None if row.get("hold_reason") is None else str(row["hold_reason"]),
    )


def reserve(dispatch: dict[str, Any], dispatch_digest: str) -> Effect:
    datasource = _store()

    def transaction() -> Effect:
        session = datasource.sql_session()
        session.execute(
            sa.text(
                "INSERT INTO crawl_external_effects_v4 (workflow_id,slot_id,request_digest,"
                "dispatch_digest,max_calls,max_input_bytes,state,dispatch_json) VALUES "
                "(:workflow_id,'model-0',:request_digest,:dispatch_digest,1,:input_bytes,"
                "'reserved',CAST(:dispatch_json AS JSONB)) ON CONFLICT (workflow_id) DO NOTHING"
            ),
            {
                **dispatch,
                "dispatch_digest": dispatch_digest,
                "dispatch_json": json.dumps(dispatch, sort_keys=True),
            },
        )
        row = (
            session.execute(
                sa.text(
                    "SELECT * FROM crawl_external_effects_v4 "
                    "WHERE workflow_id=:workflow_id FOR UPDATE"
                ),
                {"workflow_id": dispatch["workflow_id"]},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RuntimeError("external effect reservation disappeared")
        effect = _effect(dict(row))
        if effect.dispatch_digest != dispatch_digest or effect.dispatch != dispatch:
            raise EffectConflictError("external effect identity conflicts with recorded input")
        return effect

    return datasource.transaction(name="crawl_effect_reserve")(transaction)()


def transition(
    workflow_id: str,
    expected: str,
    state: str,
    *,
    result: dict[str, Any] | None = None,
    audit: dict[str, Any] | None = None,
    hold_reason: str | None = None,
    recover_post_dispatch: bool = False,
) -> Effect:
    datasource = _store()

    def transaction() -> Effect:
        row = (
            datasource.sql_session()
            .execute(
                sa.text(
                    "UPDATE crawl_external_effects_v4 SET state=:state,"
                    "result_json=COALESCE(result_json,CAST(:result AS JSONB)),"
                    "audit_json=COALESCE(audit_json,CAST(:audit AS JSONB)),"
                    "hold_reason=COALESCE(:reason,hold_reason),updated_at=NOW() "
                    "WHERE workflow_id=:workflow_id AND (state=:expected OR :recover AND state IN "
                    "('dispatching','returned','reconciled','failed','unknown')) RETURNING *"
                ),
                {
                    "state": state,
                    "reason": hold_reason,
                    "workflow_id": workflow_id,
                    "expected": expected,
                    "recover": recover_post_dispatch,
                    "result": None if result is None else json.dumps(result, sort_keys=True),
                    "audit": None if audit is None else json.dumps(audit, sort_keys=True),
                },
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RuntimeError("external effect transition conflicted")
        return _effect(dict(row))

    return datasource.transaction(name="crawl_effect_transition")(transaction)()


def hold_unknown(workflow_id: str, reason: str, *, audit: dict[str, Any] | None = None) -> None:
    for _attempt in range(2):
        try:
            transition(
                workflow_id,
                "unknown",
                "unknown",
                audit=audit,
                hold_reason=reason,
                recover_post_dispatch=True,
            )
            break
        except Exception:  # noqa: S110 -- retry covers an ambiguous commit acknowledgement
            pass
    raise AmbiguousEffectError(
        "model effect outcome is ambiguous; manual reconciliation required"
    ) from None
