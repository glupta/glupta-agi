from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from glupta_agi.settings import Settings, SettingsError


def _private_file(root: Path, name: str, value: str) -> Path:
    path = root / name
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


class SettingsTests(unittest.TestCase):
    def test_private_file_capability_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            token_path = _private_file(root, "token", "a" * 32)
            with patch.dict(
                os.environ,
                {"GLUPTA_INTAKE_TOKEN_FILE": str(token_path)},
                clear=True,
            ), patch("glupta_agi.settings._validate_codex_runtime"):
                settings = Settings.from_environment()
            self.assertTrue(settings.authenticates("a" * 32))
            self.assertFalse(settings.authenticates("b" * 32))
            self.assertEqual(settings.codex_model, "gpt-5.4-mini")

    def test_group_readable_or_short_capability_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / "token"
            token_path.write_text("short", encoding="utf-8")
            token_path.chmod(0o640)
            with patch.dict(os.environ, {"GLUPTA_INTAKE_TOKEN_FILE": str(token_path)}, clear=True):
                with self.assertRaises(SettingsError):
                    Settings.from_environment()

    def test_symlink_capability_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            link = Path(directory) / "link"
            target.write_text("a" * 32, encoding="utf-8")
            target.chmod(0o600)
            link.symlink_to(target)
            with patch.dict(os.environ, {"GLUPTA_INTAKE_TOKEN_FILE": str(link)}, clear=True):
                with self.assertRaises(SettingsError):
                    Settings.from_environment()

    def test_builds_dbos_url_from_private_password_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = _private_file(root, "token", "t" * 32)
            password = _private_file(root, "postgres-password", "a b/c")
            with patch.dict(
                os.environ,
                {
                    "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                    "GLUPTA_POSTGRES_PASSWORD_FILE": str(password),
                    "GLUPTA_POSTGRES_USER": "glupta user",
                    "GLUPTA_POSTGRES_DB": "glupta/db",
                },
                clear=True,
            ), patch("glupta_agi.settings._validate_codex_runtime"):
                settings = Settings.from_environment()
                self.assertEqual(
                    settings.dbos_system_database_url(),
                    "postgresql://glupta%20user:a%20b%2Fc@postgres:5432/glupta%2Fdb",
                )

    def test_unpinned_model_and_remote_database_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = _private_file(root, "token", "t" * 32)
            with patch.dict(
                os.environ,
                {
                    "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                    "GLUPTA_CODEX_MODEL": "unpinned-model",
                },
                clear=True,
            ), patch("glupta_agi.settings._validate_codex_runtime"):
                with self.assertRaisesRegex(SettingsError, "pinned Codex model"):
                    Settings.from_environment()

            with patch.dict(
                os.environ,
                {
                    "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                    "DBOS_SYSTEM_DATABASE_URL": "postgresql://user:pass@db.example.com/glupta",
                },
                clear=True,
            ), patch("glupta_agi.settings._validate_codex_runtime"):
                settings = Settings.from_environment()
                with self.assertRaisesRegex(SettingsError, "must be local"):
                    settings.dbos_system_database_url()
