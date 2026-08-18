from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "src" / "glupta_agi"


class ReleaseBoundaryTests(TestCase):
    def test_production_boundary_excludes_consumer_codex_and_eval_harness(self) -> None:
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        sources = {
            path.name: path.read_text(encoding="utf-8") for path in SOURCE.glob("*.py")
        }
        joined = "\n".join(sources.values())
        self.assertNotIn("openai-codex", project)
        self.assertNotIn("openai_codex", joined)
        self.assertNotIn("CODEX_HOME", joined)
        self.assertNotIn("evals.py", sources)
        self.assertEqual(
            [name for name, text in sources.items() if "from openai import" in text],
            ["openai_adapter.py"],
        )

    def test_production_semantic_line_budget_is_at_most_1500(self) -> None:
        lines = (
            line
            for path in SOURCE.glob("*.py")
            for line in path.read_text(encoding="utf-8").splitlines()
        )
        count = sum(
            bool(line.strip()) and not line.lstrip().startswith("#") for line in lines
        )
        self.assertLessEqual(count, 1500)

    def test_container_and_database_bases_are_digest_pinned(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertEqual(dockerfile.count("@sha256:"), 2)
        self.assertIn("--no-install-project", dockerfile)
        self.assertIn(
            "COPY --from=build --chown=10001:10001 /app/.venv /app/.venv", dockerfile
        )
        self.assertIn("postgres:17.6-bookworm@sha256:", compose)
        self.assertIn("GLUPTA_CREDENTIAL_GENERATION:?", compose)
