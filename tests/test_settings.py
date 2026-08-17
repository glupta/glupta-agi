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
