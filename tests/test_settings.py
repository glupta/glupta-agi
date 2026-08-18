from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from glupta_agi.settings import Settings, SettingsError, _validate_codex_runtime, get_settings


def _private_file(root: Path, name: str, value: str) -> Path:
    path = root / name
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


class SettingsTests(unittest.TestCase):
    def test_codex_metadata_stabilization_is_bounded_and_fail_closed(self) -> None:
        valid = SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=os.geteuid())
        wrong_mode = SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=os.geteuid())
        wrong_owner = SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=os.geteuid() + 1)
        symlink = SimpleNamespace(st_mode=stat.S_IFLNK | 0o600, st_uid=os.geteuid())

        with (
            patch("glupta_agi.settings.Path.lstat", return_value=valid) as observe,
            patch("glupta_agi.settings.time.sleep") as wait,
        ):
            _validate_codex_runtime(Path("/run/codex"))
        self.assertEqual(observe.call_count, 1)
        wait.assert_not_called()

        for first in (OSError("unavailable"), wrong_mode):
            with self.subTest(first=type(first).__name__):
                with (
                    patch("glupta_agi.settings.Path.lstat", side_effect=[first, valid]) as observe,
                    patch("glupta_agi.settings.time.sleep") as wait,
                ):
                    _validate_codex_runtime(Path("/run/codex"))
                self.assertEqual(observe.call_count, 2)
                wait.assert_called_once_with(0.5)

        for invalid in (OSError("unavailable"), symlink, wrong_mode, wrong_owner):
            with self.subTest(invalid=type(invalid).__name__):
                with (
                    patch(
                        "glupta_agi.settings.Path.lstat", side_effect=[invalid, invalid]
                    ) as observe,
                    patch("glupta_agi.settings.time.sleep") as wait,
                ):
                    with self.assertRaisesRegex(SettingsError, "secondary Codex subscription"):
                        _validate_codex_runtime(Path("/run/codex"))
                self.assertEqual(observe.call_count, 2)
                wait.assert_called_once_with(0.5)

    def test_process_settings_are_validated_once(self) -> None:
        expected = Settings(input_root=Path("/inputs"), token="t" * 32)
        get_settings.cache_clear()
        try:
            with patch.object(Settings, "from_environment", return_value=expected) as load:
                self.assertIs(get_settings(), expected)
                self.assertIs(get_settings(), expected)
            load.assert_called_once_with()
        finally:
            get_settings.cache_clear()

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
            self.assertEqual(settings.codex_model, "gpt-5.6-sol")

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

            with patch.dict(
                os.environ,
                {
                    "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                    "DBOS_SYSTEM_DATABASE_URL": "sqlite:///crawl.db",
                },
                clear=True,
            ), patch("glupta_agi.settings._validate_codex_runtime"):
                settings = Settings.from_environment()
                with self.assertRaisesRegex(SettingsError, "must be PostgreSQL"):
                    settings.dbos_system_database_url()

    def test_codex_home_must_be_an_absolute_authenticated_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            token = _private_file(Path(temporary), "token", "t" * 32)
            with patch.dict(
                os.environ,
                {
                    "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                    "GLUPTA_CODEX_HOME": "relative-codex-home",
                },
                clear=True,
            ):
                with self.assertRaisesRegex(SettingsError, "secondary Codex subscription"):
                    Settings.from_environment()

    def test_codex_auth_file_must_be_private_regular_and_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = _private_file(root, "token", "t" * 32)
            codex_home = root / "codex"
            codex_home.mkdir()
            auth = _private_file(codex_home, "auth.json", "opaque-test-value")
            environment = {
                "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                "GLUPTA_CODEX_HOME": str(codex_home),
            }
            with patch.dict(os.environ, environment, clear=True):
                self.assertEqual(Settings.from_environment().codex_home, codex_home)

            auth.chmod(0o640)
            with patch.dict(os.environ, environment, clear=True):
                with self.assertRaisesRegex(SettingsError, "secondary Codex subscription"):
                    Settings.from_environment()

            auth.unlink()
            target = _private_file(root, "auth-target", "opaque-test-value")
            auth.symlink_to(target)
            with patch.dict(os.environ, environment, clear=True):
                with self.assertRaisesRegex(SettingsError, "secondary Codex subscription"):
                    Settings.from_environment()
