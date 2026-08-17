from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from glupta_agi.settings import Settings, SettingsError


class SettingsTests(unittest.TestCase):
    def test_private_file_capability_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / "token"
            token_path.write_text("a" * 32, encoding="utf-8")
            token_path.chmod(0o600)
            with patch.dict(os.environ, {"GLUPTA_INTAKE_TOKEN_FILE": str(token_path)}):
                settings = Settings.from_environment()
            self.assertTrue(settings.authenticates("a" * 32))
            self.assertFalse(settings.authenticates("b" * 32))
            self.assertEqual(settings.ollama_model, "qwen3.8:27b")

    def test_group_readable_or_short_capability_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / "token"
            token_path.write_text("short", encoding="utf-8")
            token_path.chmod(0o640)
            with patch.dict(os.environ, {"GLUPTA_INTAKE_TOKEN_FILE": str(token_path)}):
                with self.assertRaises(SettingsError):
                    Settings.from_environment()

    def test_symlink_capability_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            link = Path(directory) / "link"
            target.write_text("a" * 32, encoding="utf-8")
            target.chmod(0o600)
            link.symlink_to(target)
            with patch.dict(os.environ, {"GLUPTA_INTAKE_TOKEN_FILE": str(link)}):
                with self.assertRaises(SettingsError):
                    Settings.from_environment()

    def test_builds_dbos_url_from_private_password_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = root / "token"
            token.write_text("t" * 32)
            token.chmod(0o600)
            password = root / "postgres-password"
            password.write_text("a b/c")
            password.chmod(0o600)
            with patch.dict(
                os.environ,
                {
                    "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                    "GLUPTA_POSTGRES_PASSWORD_FILE": str(password),
                    "GLUPTA_POSTGRES_USER": "glupta user",
                    "GLUPTA_POSTGRES_DB": "glupta/db",
                },
                clear=True,
            ):
                settings = Settings.from_environment()
                self.assertEqual(
                    settings.dbos_system_database_url(),
                    "postgresql://glupta%20user:a%20b%2Fc@postgres:5432/glupta%2Fdb",
                )

    def test_remote_model_and_database_endpoints_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            token = Path(temporary) / "token"
            token.write_text("t" * 32)
            token.chmod(0o600)
            with patch.dict(
                os.environ,
                {
                    "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                    "GLUPTA_OLLAMA_URL": "https://models.example.com/v1",
                },
                clear=True,
            ):
                with self.assertRaisesRegex(SettingsError, "local endpoint"):
                    Settings.from_environment()

            with patch.dict(
                os.environ,
                {
                    "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                    "GLUPTA_OLLAMA_URL": "https://localhost/v1",
                },
                clear=True,
            ):
                with self.assertRaisesRegex(SettingsError, "local endpoint"):
                    Settings.from_environment()

            with patch.dict(
                os.environ,
                {
                    "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                    "DBOS_SYSTEM_DATABASE_URL": "postgresql://user:pass@db.example.com/glupta",
                },
                clear=True,
            ):
                settings = Settings.from_environment()
                with self.assertRaisesRegex(SettingsError, "must be local"):
                    settings.dbos_system_database_url()
