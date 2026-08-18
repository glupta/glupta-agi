from __future__ import annotations

import json
import os
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch

from glupta_agi.inference import PINNED_MODEL
from glupta_agi.settings import Settings, SettingsError, get_settings
from tests.helpers import private_file, release_profile, write_profile


class SettingsTests(unittest.TestCase):
    def test_every_release_profile_field_is_required_and_frozen_policy_cannot_drift(self) -> None:
        raw = release_profile().model_dump(mode="json")
        for field in raw:
            with self.subTest(missing=field):
                candidate = {key: value for key, value in raw.items() if key != field}
                with self.assertRaises(ValueError):
                    type(release_profile()).model_validate(candidate)
        for field, value in (
            ("model", "gpt-5.6"),
            ("max_usd_micros", 1_850_001),
            ("sdk_retries", 1),
            ("store", True),
            ("endpoint", "https://example.com/v1"),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                release_profile(**{field: value})

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

    def test_loads_complete_release_profile_without_reading_key_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = private_file(root, "intake-token", "t" * 32)
            profile_path = write_profile(root)
            key = private_file(root, "api-key", "secret-api-key-" + "x" * 32)
            real_open = os.open
            opened: list[Path] = []

            def observe(path: object, flags: int, *args: object, **kwargs: object) -> int:
                opened.append(Path(path))
                return real_open(path, flags, *args, **kwargs)

            with (
                patch.dict(
                    os.environ,
                    {
                        "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                        "GLUPTA_RELEASE_PROFILE_FILE": str(profile_path),
                        "GLUPTA_OPENAI_API_KEY_FILE": str(key),
                        "GLUPTA_CREDENTIAL_GENERATION": "1",
                    },
                    clear=True,
                ),
                patch("glupta_agi.settings.os.open", side_effect=observe),
            ):
                settings = Settings.from_environment()

            self.assertTrue(settings.authenticates("t" * 32))
            self.assertEqual(settings.model, PINNED_MODEL)
            self.assertEqual(settings.release_profile_digest, release_profile().digest())
            self.assertEqual(opened, [token, profile_path])

    def test_missing_unsafe_or_expired_release_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = private_file(root, "intake-token", "t" * 32)
            key = private_file(root, "api-key", "secret-api-key-" + "x" * 32)
            base = {
                "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                "GLUPTA_OPENAI_API_KEY_FILE": str(key),
                "GLUPTA_CREDENTIAL_GENERATION": "1",
            }
            for profile_path in (root / "missing", write_profile(root)):
                if profile_path.exists():
                    profile_path.chmod(0o640)
                with (
                    self.subTest(profile_path=profile_path),
                    patch.dict(
                        os.environ,
                        {**base, "GLUPTA_RELEASE_PROFILE_FILE": str(profile_path)},
                        clear=True,
                    ),
                    self.assertRaises(SettingsError),
                ):
                    Settings.from_environment()

            expired = release_profile(
                credential_expires_at="2020-01-01T00:00:00Z",
                evidence_expires_at="2020-01-01T00:00:00Z",
            )
            expired_path = private_file(
                root, "expired.json", json.dumps(expired.model_dump(mode="json"))
            )
            with (
                patch.dict(
                    os.environ,
                    {**base, "GLUPTA_RELEASE_PROFILE_FILE": str(expired_path)},
                    clear=True,
                ),
                self.assertRaisesRegex(SettingsError, "expired"),
            ):
                Settings.from_environment()

    def test_key_must_be_absolute_private_regular_and_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = private_file(root, "intake-token", "t" * 32)
            profile_path = write_profile(root)
            key = private_file(root, "api-key", "secret-api-key-" + "x" * 32)
            key.chmod(0o640)
            with (
                patch.dict(
                    os.environ,
                    {
                        "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                        "GLUPTA_RELEASE_PROFILE_FILE": str(profile_path),
                        "GLUPTA_OPENAI_API_KEY_FILE": str(key),
                        "GLUPTA_CREDENTIAL_GENERATION": "1",
                    },
                    clear=True,
                ),
                self.assertRaises(SettingsError),
            ):
                Settings.from_environment()

    def test_credential_generation_must_match_approved_runtime_config(self) -> None:
        profile = release_profile(credential_generation=2)
        settings = Settings(
            input_root=Path("/inputs"),
            token="t" * 32,
            release_profile=profile,
            release_profile_digest=profile.digest(),
            openai_api_key_file=Path("/private/key"),
            credential_generation=1,
        )
        with self.assertRaisesRegex(SettingsError, "generation"):
            settings.require_external_profile()

    def test_invalid_private_bytes_and_noncanonical_generation_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = root / "intake-token"
            token.write_bytes(b"\xffRAW_PRIVATE_BYTES" + b"x" * 32)
            token.chmod(0o600)
            with (
                patch.dict(os.environ, {"GLUPTA_INTAKE_TOKEN_FILE": str(token)}, clear=True),
                self.assertRaises(SettingsError) as caught,
            ):
                Settings.from_environment()
            self.assertIsNone(caught.exception.__cause__)
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn(
                "RAW_PRIVATE_BYTES", "".join(traceback.format_exception(caught.exception))
            )

            valid_token = private_file(root, "valid-token", "t" * 32)
            profile_path = write_profile(root)
            key = private_file(root, "api-key", "secret-api-key-" + "x" * 32)
            base = {
                "GLUPTA_INTAKE_TOKEN_FILE": str(valid_token),
                "GLUPTA_RELEASE_PROFILE_FILE": str(profile_path),
                "GLUPTA_OPENAI_API_KEY_FILE": str(key),
            }
            for generation in ("01", "+1", " 1"):
                with (
                    self.subTest(generation=generation),
                    patch.dict(
                        os.environ,
                        {**base, "GLUPTA_CREDENTIAL_GENERATION": generation},
                        clear=True,
                    ),
                    self.assertRaisesRegex(SettingsError, "generation"),
                ):
                    Settings.from_environment()

    def test_database_must_be_local_postgresql(self) -> None:
        settings = Settings(input_root=Path("/inputs"), token="t" * 32)
        for url in ("sqlite:///crawl.db", "postgresql://u:p@db.example.com/crawl"):
            with (
                patch.dict(os.environ, {"DBOS_SYSTEM_DATABASE_URL": url}, clear=True),
                self.assertRaises(SettingsError),
            ):
                settings.dbos_system_database_url()
