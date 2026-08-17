"""Single-route durable evidence workflow."""

from __future__ import annotations

from typing import Any

from dbos import DBOS
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider

from .artifacts import persist_artifacts as persist_artifact_files
from .brief import SYSTEM_PROMPT, build_user_prompt, render_markdown, validate_citations
from .contracts import EvidenceBrief


def _agent(base_url: str, model_name: str) -> Agent[None, EvidenceBrief]:
    model = OllamaModel(model_name, provider=OllamaProvider(base_url=base_url))
    return Agent(
        model,
        output_type=NativeOutput(EvidenceBrief),
        system_prompt=SYSTEM_PROMPT,
        retries=1,
    )


@DBOS.step()
async def generate_brief(payload: dict[str, Any], base_url: str, model_name: str) -> dict[str, Any]:
    result = await _agent(base_url, model_name).run(
        build_user_prompt(str(payload["question"]), payload["sources"])
    )
    brief = result.output
    validate_citations(brief, payload["sources"])
    return brief.model_dump(mode="json")


@DBOS.step()
def persist_artifacts(
    workflow_id: str, artifact_root: str, result: dict[str, Any], markdown: str
) -> None:
    persist_artifact_files(workflow_id, artifact_root, result, markdown)


@DBOS.workflow()
async def evidence_brief_workflow(
    payload: dict[str, Any], workflow_id: str, artifact_root: str, base_url: str, model_name: str
) -> dict[str, Any]:
    raw = await generate_brief(payload, base_url, model_name)
    brief = EvidenceBrief.model_validate(raw)
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
