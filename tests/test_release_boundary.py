from __future__ import annotations

import tomllib
from importlib.metadata import metadata
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from glupta_agi import __version__
from glupta_agi.__main__ import main
from glupta_agi.api import app

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "src" / "glupta_agi"


class ReleaseBoundaryTests(TestCase):
    def test_project_review_policy_is_bounded_and_does_not_recurse_per_byte(self) -> None:
        policy = " ".join((ROOT / "AGENTS.md").read_text(encoding="utf-8").split())

        self.assertIn("at most two candidate hashes and one remediation pass", policy)
        self.assertIn("Never create R3/R4/etc. autonomously", policy)
        self.assertIn("Deterministically verified fixes may land", policy)
        self.assertNotIn(
            "Any reviewed-byte change invalidates the approval and restarts review", policy
        )
        self.assertNotIn("Every Glupta version-identity change requires", policy)

    def test_package_runtime_api_and_dbos_share_one_version_identity(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(project["project"]["version"], __version__)
        self.assertEqual(metadata("glupta-agi")["Version"], __version__)
        self.assertNotIn('"0.3.0"', (SOURCE / "__init__.py").read_text(encoding="utf-8"))
        self.assertEqual(app.version, __version__)
        settings = SimpleNamespace(dbos_system_database_url=lambda: "postgresql://local/runtime")
        with (
            patch("glupta_agi.__main__.get_settings", return_value=settings),
            patch("glupta_agi.__main__.DBOS") as dbos,
            patch("glupta_agi.effects.initialize"),
            patch("glupta_agi.__main__.uvicorn.run"),
        ):
            main()
        self.assertEqual(dbos.call_args.kwargs["config"]["application_version"], __version__)

    def test_production_boundary_excludes_consumer_codex_and_eval_harness(self) -> None:
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        sources = {path.name: path.read_text(encoding="utf-8") for path in SOURCE.glob("*.py")}
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
        count = sum(bool(line.strip()) and not line.lstrip().startswith("#") for line in lines)
        self.assertLessEqual(count, 1500)

    def test_container_and_database_bases_are_digest_pinned(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertEqual(dockerfile.count("@sha256:"), 2)
        self.assertIn("--no-install-project", dockerfile)
        self.assertIn("COPY --from=build --chown=10001:10001 /app/.venv /app/.venv", dockerfile)
        self.assertIn("postgres:17.6-bookworm@sha256:", compose)
        self.assertIn("GLUPTA_CREDENTIAL_GENERATION:?", compose)
