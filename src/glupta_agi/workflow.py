"""One durable evidence workflow backed by the secondary Codex subscription."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any

from dbos import DBOS

from .artifacts import persist_artifacts as persist_artifact_files
from .brief import SYSTEM_PROMPT, build_user_prompt, render_markdown, resolve_citations
from .contracts import EvidenceBrief


class BriefGenerationError(RuntimeError):
    """Codex did not produce a valid source-grounded brief."""


def _run_codex(
    prompt: str,
    sources: list[dict[str, Any]],
    codex_binary: str,
    codex_home: str,
    model_name: str,
) -> EvidenceBrief:
    with tempfile.TemporaryDirectory(prefix="glupta-crawl-") as temporary:
        schema_path = os.path.join(temporary, "schema.json")
        output_path = os.path.join(temporary, "output.json")
        with open(schema_path, "w", encoding="utf-8") as schema_file:
            json.dump(EvidenceBrief.model_json_schema(), schema_file)
        command = [
            codex_binary,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--model",
            model_name,
            "-c",
            'approval_policy="never"',
            "-c",
            'model_reasoning_effort="medium"',
            "-c",
            "features.shell_tool=false",
            "-c",
            "features.remote_plugin=false",
            "-c",
            "features.plugins=false",
            "-c",
            "features.apps=false",
            "-c",
            "features.skill_search=false",
            "-c",
            "features.multi_agent=false",
            "-c",
            "features.multi_agent_v2=false",
            "-c",
            "tools.view_image=false",
            "--sandbox",
            "read-only",
            "-C",
            temporary,
            "--output-schema",
            schema_path,
            "--output-last-message",
            output_path,
            "-",
        ]
        environment = {
            "CODEX_HOME": codex_home,
            "HOME": os.path.dirname(codex_home),
            "LANG": "C.UTF-8",
            "TMPDIR": tempfile.gettempdir(),
        }
        try:
            subprocess.run(  # noqa: S603 -- executable path is pinned by validated settings
                command,
                input=f"{SYSTEM_PROMPT}\n\n{prompt}",
                text=True,
                capture_output=True,
                check=True,
                timeout=300,
                env=environment,
            )
            with open(output_path, encoding="utf-8") as output_file:
                brief = EvidenceBrief.model_validate_json(output_file.read())
            return resolve_citations(brief, sources)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise BriefGenerationError("Codex did not produce a valid grounded brief") from exc


@DBOS.step()
def generate_brief(
    payload: dict[str, Any], codex_binary: str, codex_home: str, model_name: str
) -> dict[str, Any]:
    brief = _run_codex(
        build_user_prompt(str(payload["question"]), payload["sources"]),
        payload["sources"],
        codex_binary,
        codex_home,
        model_name,
    )
    return brief.model_dump(mode="json")


@DBOS.step()
def persist_artifacts(
    workflow_id: str, artifact_root: str, result: dict[str, Any], markdown: str
) -> None:
    persist_artifact_files(workflow_id, artifact_root, result, markdown)


@DBOS.workflow()
async def evidence_brief_workflow(
    payload: dict[str, Any],
    workflow_id: str,
    artifact_root: str,
    codex_binary: str,
    codex_home: str,
    model_name: str,
) -> dict[str, Any]:
    raw = generate_brief(payload, codex_binary, codex_home, model_name)
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
