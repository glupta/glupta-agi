from __future__ import annotations

import json
import os
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch

from glupta_agi.inference import PINNED_MODEL, usd_upper_bound
from glupta_agi.settings import Settings, SettingsError, get_settings
from tests.helpers import private_file, release_profile, write_profile


def _assert_product_exception_sanitized(error: BaseException, *markers: str) -> None:
    case = unittest.TestCase()
    current: BaseException | None = error
    while current is not None:
        for marker in markers:
            case.assertNotIn(marker, str(current))
            case.assertNotIn(marker, repr(vars(current)))
            case.assertNotIn(marker, "".join(traceback.format_exception(current)))
        case.assertIsNone(current.__cause__)
        case.assertIsNone(current.__context__)
        captured = traceback.TracebackException.from_exception(current, capture_locals=True)
        traceback_cursor = current.__traceback__
        while traceback_cursor is not None:
            frame = traceback_cursor.tb_frame
            if "/src/glupta_agi/" in frame.f_code.co_filename:
                captured_frame = next(
                    item for item in captured.stack if item.filename == frame.f_code.co_filename
                    and item.lineno == traceback_cursor.tb_lineno
                )
                for marker in markers:
                    case.assertNotIn(marker, repr(frame.f_locals))
                    case.assertNotIn(marker, repr(captured_frame.locals))
            traceback_cursor = traceback_cursor.tb_next
        current = current.__cause__ or current.__context__


class SettingsTests(unittest.TestCase):
    def test_regional_endpoint_and_uplifted_price_are_frozen(self) -> None:
        self.assertEqual(usd_upper_bound(270_000, 4_000), 1_988_250)
        self.assertEqual(usd_upper_bound(1, 0), 7)
        self.assertEqual(release_profile(region="europe", endpoint="https://eu.api.openai.com/v1").region, "europe")  # noqa: E501
        for changes in (
            {"region": "europe"},
            {"schema_version": "crawl-openai-release-v1"},
            {"max_usd_micros": 1_850_000},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                release_profile(**changes)

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

    def test_loads_complete_release_profile_and_validates_key_identity(self) -> None:
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
            self.assertEqual(opened, [profile_path, key, token])

    def test_startup_rejects_key_bytes_that_do_not_match_release_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = private_file(root, "intake-token", "t" * 32)
            key = private_file(root, "api-key", "wrong-api-key-" + "x" * 32)
            with (
                patch.dict(os.environ, {"GLUPTA_INTAKE_TOKEN_FILE": str(token),
                    "GLUPTA_RELEASE_PROFILE_FILE": str(write_profile(root)),
                    "GLUPTA_OPENAI_API_KEY_FILE": str(key),
                    "GLUPTA_CREDENTIAL_GENERATION": "1"}, clear=True),
                self.assertRaisesRegex(SettingsError, "does not match release evidence"),
            ):
                Settings.from_environment()

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

    def test_private_file_and_configuration_rejections_release_secret_locals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile_path = write_profile(root)
            key = private_file(root, "api-key", "synthetic-key-material")
            base = {
                "GLUPTA_RELEASE_PROFILE_FILE": str(profile_path),
                "GLUPTA_OPENAI_API_KEY_FILE": str(key),
                "GLUPTA_CREDENTIAL_GENERATION": "1",
            }
            for name, value, marker in (
                ("short-token", "R10_SHORT_TOKEN", "R10_SHORT_TOKEN"),
                ("oversized-token", "R10_PRIVATE_VALUE" + "x" * 4097, "R10_PRIVATE_VALUE"),
            ):
                token = private_file(root, name, value)
                with (
                    self.subTest(path=name),
                    patch.dict(
                        os.environ, {**base, "GLUPTA_INTAKE_TOKEN_FILE": str(token)}, clear=True
                    ),
                    self.assertRaises(SettingsError) as caught,
                ):
                    Settings.from_environment()
                _assert_product_exception_sanitized(caught.exception, marker)

            token_marker = "R10_VALID_TOKEN_" + "t" * 32
            token = private_file(root, "valid-marked-token", token_marker)
            real_open = os.open
            opened: list[Path] = []

            def observe(path: object, flags: int, *args: object, **kwargs: object) -> int:
                opened.append(Path(path))
                return real_open(path, flags, *args, **kwargs)

            with (
                patch.dict(
                    os.environ,
                    {**base, "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                     "GLUPTA_CREDENTIAL_GENERATION": "2"},
                    clear=True,
                ),
                patch("glupta_agi.settings.os.open", side_effect=observe),
                self.assertRaises(SettingsError) as caught,
            ):
                Settings.from_environment()
            self.assertEqual(opened, [profile_path])
            _assert_product_exception_sanitized(caught.exception, token_marker)

            database_marker = "R10_DATABASE_MARKER"
            password = private_file(root, "postgres-password", database_marker)
            with (
                patch.dict(
                    os.environ,
                    {"GLUPTA_POSTGRES_PASSWORD_FILE": str(password),
                     "GLUPTA_POSTGRES_HOST": "remote.invalid"},
                    clear=True,
                ),
                patch("glupta_agi.settings.os.open") as private_open,
                self.assertRaises(SettingsError) as caught,
            ):
                Settings.dbos_system_database_url()
            private_open.assert_not_called()
            _assert_product_exception_sanitized(caught.exception, database_marker)

            oversized_password = private_file(
                root, "oversized-postgres-password", database_marker + "p" * 512
            )
            with (
                patch.dict(
                    os.environ, {"GLUPTA_POSTGRES_PASSWORD_FILE": str(oversized_password)},
                    clear=True,
                ),
                self.assertRaises(SettingsError) as caught,
            ):
                Settings.dbos_system_database_url()
            _assert_product_exception_sanitized(caught.exception, database_marker)

            explicit_marker = "R10_EXPLICIT_PASSWORD"
            with (
                patch.dict(
                    os.environ,
                    {"DBOS_SYSTEM_DATABASE_URL":
                     f"postgresql://user:{explicit_marker}@remote.invalid/database"},
                    clear=True,
                ),
                self.assertRaises(SettingsError) as caught,
            ):
                Settings.dbos_system_database_url()
            _assert_product_exception_sanitized(caught.exception, explicit_marker)

    def test_database_must_be_local_postgresql(self) -> None:
        settings = Settings(input_root=Path("/inputs"), token="t" * 32)
        for url in ("sqlite:///crawl.db", "postgresql://u:p@db.example.com/crawl"):
            with (
                patch.dict(os.environ, {"DBOS_SYSTEM_DATABASE_URL": url}, clear=True),
                self.assertRaises(SettingsError),
            ):
                settings.dbos_system_database_url()
