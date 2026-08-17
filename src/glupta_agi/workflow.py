"""One durable evidence workflow backed by the secondary Codex subscription."""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any

from codex_cli_bin import bundled_codex_path, bundled_path_dir
from dbos import DBOS
from openai_codex import ApprovalMode, Codex, CodexConfig, Sandbox
from openai_codex.generated.v2_all import ReasoningEffort, WebSearchMode
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent
from pydantic_ai.durable_exec.dbos import DBOSAgent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from .artifacts import persist_artifacts as persist_artifact_files
from .brief import SYSTEM_PROMPT, build_user_prompt, render_markdown, resolve_citations
from .contracts import EvidenceBrief
from .effects import AmbiguousEffectError, hold_unknown, reserve, transition


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


def _codex_launch_args(environment: dict[str, str]) -> tuple[str, ...]:
    env_binary = shutil.which("env", path=os.defpath)
    if env_binary is None:
        raise BriefGenerationError("clean Codex environment launcher is unavailable")
    assignments = tuple(f"{key}={value}" for key, value in sorted(environment.items()))
    return (
        env_binary,
        "-i",
        *assignments,
        str(bundled_codex_path()),
        "app-server",
        "--listen",
        "stdio://",
    )


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
        brief = validate(effect.result)
        if effect.state == "returned":
            transition(workflow_id, "returned", "reconciled")
        return brief
    if effect.state == "failed":
        raise BriefGenerationError("recorded model effect failed validation")
    if effect.state in {"dispatching", "thread_started", "unknown"}:
        hold_unknown(effect, f"recovery_from_{effect.state}")

    with tempfile.TemporaryDirectory(prefix="glupta-crawl-") as temporary:
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
        launch_args = _codex_launch_args(environment)
        client = None
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
                ephemeral=False,
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
            brief = validate(raw)
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
        except ValueError as exc:
            if effect.state == "turn_started":
                transition(workflow_id, "turn_started", "failed", hold_reason="invalid_output")
            raise BriefGenerationError("Codex did not produce a valid grounded brief") from exc
        except Exception as exc:
            if effect.state in {"dispatching", "thread_started", "turn_started"}:
                hold_unknown(effect, f"provider_error_after_{effect.state}")
            raise BriefGenerationError("Codex provider request failed") from exc
        finally:
            if client is not None:
                client.close()


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


_crawl_agent = DBOSAgent(
    Agent(
        FunctionModel(_crawl_model, model_name="codex-subscription-adapter"),
        name="crawl_observe_agent",
        output_type=EvidenceBrief,
        retries=0,
    ),
    name="crawl_observe_agent",
    model_step_config={"retries_allowed": False},
    parallel_execution_mode="sequential",
)


@DBOS.step(retries_allowed=False)
def persist_artifacts(
    workflow_id: str, artifact_root: str, result: dict[str, Any], markdown: str
) -> None:
    persist_artifact_files(workflow_id, artifact_root, result, markdown)


@DBOS.workflow()
async def evidence_brief_workflow(
    payload: dict[str, Any],
    workflow_id: str,
    artifact_root: str,
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
    if payload["write_artifacts"]:
        persist_artifacts(workflow_id, artifact_root, response, markdown)
    return response
