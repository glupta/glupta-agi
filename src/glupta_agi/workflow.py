"""One durable evidence workflow backed by the secondary Codex subscription."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any

from codex_cli_bin import bundled_codex_path, bundled_path_dir
from dbos import DBOS, Queue
from openai_codex import (
    ApprovalMode,
    Codex,
    CodexConfig,
    CodexError,
    CodexRpcError,
    Sandbox,
    TransportClosedError,
)
from openai_codex.generated.v2_all import ReasoningEffort, WebSearchMode
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent
from pydantic_ai.durable_exec.dbos import DBOSDurability
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from .brief import SYSTEM_PROMPT, build_user_prompt, render_markdown, resolve_citations
from .contracts import EvidenceBrief
from .effects import AmbiguousEffectError, hold_unknown, reserve, transition

_GLOBAL_DISABLED_FEATURES = ("apps", "plugins", "remote_plugin")


class BriefGenerationError(RuntimeError):
    """Codex did not produce a valid source-grounded brief."""


class _CrawlModelPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt: str
    sources: list[dict[str, Any]]
    codex_home: str
    model_name: str
    workflow_id: str
    request_digest: str


def _codex_launch_args(environment: dict[str, str], sqlite_home: str) -> tuple[str, ...]:
    env_binary = shutil.which("env", path=os.defpath)
    if env_binary is None:
        raise BriefGenerationError("clean Codex environment launcher is unavailable")
    assignments = tuple(f"{key}={value}" for key, value in sorted(environment.items()))
    disabled_features = tuple(
        argument for feature in _GLOBAL_DISABLED_FEATURES for argument in ("--disable", feature)
    )
    return (
        env_binary,
        "-i",
        *assignments,
        str(bundled_codex_path()),
        "-c",
        'cli_auth_credentials_store="file"',
        "-c",
        'history.persistence="none"',
        "-c",
        f"sqlite_home={json.dumps(sqlite_home)}",
        "app-server",
        *disabled_features,
        "--listen",
        "stdio://",
    )


def _provider_error_token(error: BaseException) -> str:
    """Return a bounded token without persisting provider error details."""
    if isinstance(error, TransportClosedError):
        return "provider_transport_closed"
    if isinstance(error, CodexRpcError):
        return "provider_rpc_error"
    if isinstance(error, CodexError):
        return "provider_sdk_error"
    if isinstance(error, TimeoutError):
        return "provider_timeout"
    if isinstance(error, OSError):
        return "provider_os_error"
    return "provider_error"


def _run_codex(
    prompt: str,
    sources: list[dict[str, Any]],
    codex_home: str,
    model_name: str,
    workflow_id: str,
    request_digest: str,
    *,
    codex_factory: Any = Codex,
) -> EvidenceBrief:
    effect = reserve(workflow_id, request_digest, model_name)

    def validate(raw: str | dict[str, Any]) -> EvidenceBrief:
        brief = (
            EvidenceBrief.model_validate_json(raw)
            if isinstance(raw, str)
            else EvidenceBrief.model_validate(raw)
        )
        return resolve_citations(brief, sources)

    if effect.state in {"returned", "reconciled"}:
        if effect.result is None:
            raise BriefGenerationError("recorded model effect has no result")
        recorded_output_invalid = False
        try:
            brief = validate(effect.result)
        except ValueError:
            recorded_output_invalid = True
        if recorded_output_invalid:
            raise BriefGenerationError("recorded model effect failed validation") from None
        if effect.state == "returned":
            transition(workflow_id, "returned", "reconciled")
        return brief
    if effect.state == "failed":
        raise BriefGenerationError("recorded model effect failed validation")
    if effect.state in {"dispatching", "thread_started", "unknown"}:
        hold_unknown(effect, f"recovery_from_{effect.state}")

    with (
        tempfile.TemporaryDirectory(prefix="glupta-crawl-") as temporary,
        tempfile.TemporaryDirectory(prefix="glupta-crawl-state-", dir=codex_home) as state_home,
    ):
        bundled_tools = bundled_path_dir()
        search_path = os.defpath
        if bundled_tools is not None:
            search_path = os.pathsep.join((str(bundled_tools), search_path))
        environment = {
            "CODEX_HOME": codex_home,
            "HOME": os.path.dirname(codex_home),
            "LANG": "C.UTF-8",
            "PATH": search_path,
            "TMPDIR": tempfile.gettempdir(),
            "STUDIO_CODEX_SESSION_ORIGIN": "glupta-crawl-v1",
        }
        launch_args = _codex_launch_args(environment, state_home)
        client = None
        invalid_output = False
        provider_failure: str | None = None
        try:
            effect = transition(workflow_id, "reserved", "dispatching")
            client = codex_factory(
                CodexConfig(
                    cwd=temporary,
                    launch_args_override=launch_args,
                )
            )
            thread = client.thread_start(
                approval_mode=ApprovalMode.deny_all,
                base_instructions=SYSTEM_PROMPT,
                config={
                    "features": {
                        "apps": False,
                        "multi_agent": False,
                        "plugins": False,
                        "remote_plugin": False,
                        "shell_tool": False,
                        "skill_search": False,
                    },
                    "model_provider": "crawl_openai",
                    "model_providers": {
                        "crawl_openai": {
                            "name": "OpenAI",
                            "request_max_retries": 0,
                            "requires_openai_auth": True,
                            "stream_max_retries": 0,
                            "wire_api": "responses",
                        }
                    },
                    "tools": {"view_image": False},
                    "web_search": WebSearchMode.disabled.value,
                },
                cwd=temporary,
                ephemeral=True,
                model=model_name,
                sandbox=Sandbox.read_only,
            )
            effect = transition(workflow_id, "dispatching", "thread_started", thread_id=thread.id)
            turn = thread.turn(
                prompt,
                approval_mode=ApprovalMode.deny_all,
                cwd=temporary,
                effort=ReasoningEffort.medium,
                model=model_name,
                output_schema=EvidenceBrief.model_json_schema(),
                sandbox=Sandbox.read_only,
            )
            effect = transition(workflow_id, "thread_started", "turn_started", turn_id=turn.id)
            result = turn.run()
            if str(getattr(result.status, "value", result.status)) != "completed":
                hold_unknown(effect, "bound_turn_not_completed")
            raw = result.final_response
            if not raw:
                hold_unknown(effect, "bound_turn_has_no_response")
            try:
                brief = validate(raw)
            except ValueError:
                invalid_output = True
            else:
                effect = transition(
                    workflow_id,
                    "turn_started",
                    "returned",
                    result=brief.model_dump(mode="json"),
                )
                transition(workflow_id, "returned", "reconciled")
                return brief
        except AmbiguousEffectError:
            raise
        except Exception as error:
            provider_failure = _provider_error_token(error)
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:  # noqa: S110 -- never persist raw provider cleanup errors
                    pass

        if invalid_output:
            if effect.state == "turn_started":
                transition(workflow_id, "turn_started", "failed", hold_reason="invalid_output")
            raise BriefGenerationError("Codex did not produce a valid grounded brief") from None
        if provider_failure is not None:
            if effect.state in {"dispatching", "thread_started", "turn_started"}:
                hold_unknown(effect, f"{provider_failure}_after_{effect.state}")
            raise BriefGenerationError("Codex provider request failed") from None
        raise BriefGenerationError("Codex provider request failed") from None


def _crawl_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    del info
    raw_packet = None
    for message in reversed(messages):
        for part in reversed(message.parts):
            if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                raw_packet = part.content
                break
        if raw_packet is not None:
            break
    if raw_packet is None:
        raise BriefGenerationError("Crawl model packet is missing")
    packet = _CrawlModelPacket.model_validate_json(raw_packet)
    brief = _run_codex(
        packet.prompt,
        packet.sources,
        packet.codex_home,
        packet.model_name,
        packet.workflow_id,
        packet.request_digest,
    )
    return ModelResponse(parts=[TextPart(brief.model_dump_json())])


_crawl_durability = DBOSDurability(
    name="crawl_observe_agent",
    model_step_config={"retries_allowed": False},
    parallel_execution_mode="sequential",
    register_legacy_workflows=False,
)

_crawl_agent = Agent(
    FunctionModel(_crawl_model, model_name="codex-subscription-adapter"),
    name="crawl_observe_agent",
    output_type=EvidenceBrief,
    retries=0,
    capabilities=[_crawl_durability],
)

crawl_observe_queue = Queue(
    "crawl-observe-v1",
    concurrency=1,
    worker_concurrency=1,
)


@DBOS.workflow()
async def evidence_brief_workflow(
    payload: dict[str, Any],
    workflow_id: str,
    codex_home: str,
    model_name: str,
) -> dict[str, Any]:
    packet = _CrawlModelPacket(
        prompt=build_user_prompt(str(payload["question"]), payload["sources"]),
        sources=payload["sources"],
        codex_home=codex_home,
        model_name=model_name,
        workflow_id=workflow_id,
        request_digest=str(payload["request_digest"]),
    )
    brief = (await _crawl_agent.run(packet.model_dump_json(), retries=0)).output
    markdown = render_markdown(brief)
    response = {
        **brief.model_dump(mode="json"),
        "request_digest": payload["request_digest"],
        "workflow_id": workflow_id,
        "markdown": markdown,
    }
    return response
