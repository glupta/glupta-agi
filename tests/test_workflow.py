from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from glupta_agi.workflow import BriefGenerationError, _run_codex


def _completed(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    del kwargs
    output_path = Path(command[command.index("--output-last-message") + 1])
    output_path.write_text(
        json.dumps(
            {
                "answer": "Grounded answer.",
                "citations": [
                    {
                        "path": "compose.txt",
                        "line_start": 1,
                        "line_end": 1,
                        "quote": "model quote",
                    }
                ],
                "uncertainties": [],
                "next_decisions": [],
            }
        ),
        encoding="utf-8",
    )
    return subprocess.CompletedProcess(command, 0, "", "")


class CodexBriefTests(unittest.TestCase):
    @patch("glupta_agi.workflow.subprocess.run", side_effect=_completed)
    def test_runs_secondary_codex_without_tools_and_resolves_quote(self, run: object) -> None:
        result = _run_codex(
            "question",
            [{"path": "compose.txt", "content": "services:"}],
            "/Users/glupta/.local/bin/codex",
            "/Users/glupta/.codex-secondary",
            "gpt-5.4-mini",
        )

        call = run.call_args  # type: ignore[attr-defined]
        command = call.args[0]
        self.assertIn("--ephemeral", command)
        self.assertIn("features.shell_tool=false", command)
        self.assertEqual(call.kwargs["env"]["CODEX_HOME"], "/Users/glupta/.codex-secondary")
        self.assertEqual(result.citations[0].quote, "services:")

    @patch(
        "glupta_agi.workflow.subprocess.run",
        side_effect=subprocess.TimeoutExpired("codex", 300),
    )
    def test_provider_failure_is_generic(self, run: object) -> None:
        del run
        with self.assertRaisesRegex(BriefGenerationError, "valid grounded brief"):
            _run_codex(
                "question",
                [{"path": "compose.txt", "content": "services:"}],
                "/Users/glupta/.local/bin/codex",
                "/Users/glupta/.codex-secondary",
                "gpt-5.4-mini",
            )
