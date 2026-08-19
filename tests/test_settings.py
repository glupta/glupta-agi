from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from glupta_agi.settings import Settings, SettingsError, get_settings
from tests.helpers import private_file, release_profile, write_profile


def _codex_home(root: Path, *, mode: int = 0o700) -> Path:
    home = root / "codex"
    home.mkdir(mode=mode)
    private_file(home, "auth.json", "opaque-auth-state")
    return home


class SettingsTests(unittest.TestCase):
    def test_release_profile_is_complete_and_rejects_usage_based_or_policy_drift(self) -> None:
        raw = release_profile().model_dump(mode="json")
        for field in raw:
            with self.subTest(missing=field), self.assertRaises(ValueError):
                type(release_profile()).model_validate({k: v for k, v in raw.items() if k != field})
        for change in (
            {"subscription_plan": "self_serve_business_usage_based"},
            {"model": "gpt-5.6"},
            {"reasoning_effort": "high"},
            {"request_retries": 1},
            {"max_calls": 2},
            {"max_input_bytes": 262_145},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                release_profile(**change)

    def test_loads_private_subscription_profile_without_reading_auth_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = private_file(root, "intake-token", "t" * 32)
            profile_path, home = write_profile(root), _codex_home(root)
            real_open, opened = os.open, []

            def observe(path: object, flags: int, *args: object, **kwargs: object) -> int:
                opened.append(Path(path))
                return real_open(path, flags, *args, **kwargs)

            with (
                patch.dict(
                    os.environ,
                    {
                        "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                        "GLUPTA_RELEASE_PROFILE_FILE": str(profile_path),
                        "GLUPTA_CODEX_HOME": str(home),
                        "GLUPTA_AUTH_GENERATION": "1",
                    },
                    clear=True,
                ),
                patch("glupta_agi.settings.os.open", side_effect=observe),
            ):
                settings = Settings.from_environment()
            self.assertTrue(settings.authenticates("t" * 32))
            self.assertEqual(settings.codex_home, home)
            self.assertEqual(opened, [profile_path, token])

    def test_auth_home_metadata_generation_and_expiry_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = private_file(root, "intake-token", "t" * 32)
            home = _codex_home(root)
            base = {
                "GLUPTA_INTAKE_TOKEN_FILE": str(token),
                "GLUPTA_CODEX_HOME": str(home),
                "GLUPTA_AUTH_GENERATION": "1",
            }
            cases = [
                (write_profile(root, release_profile(auth_generation=2)), base),
                (
                    private_file(
                        root,
                        "expired.json",
                        json.dumps(
                            release_profile(auth_expires_at="2020-01-01T00:00:00Z").model_dump(
                                mode="json"
                            )
                        ),
                    ),
                    base,
                ),
            ]
            for profile_path, environment in cases:
                with (
                    self.subTest(profile=profile_path),
                    patch.dict(
                        os.environ,
                        {**environment, "GLUPTA_RELEASE_PROFILE_FILE": str(profile_path)},
                        clear=True,
                    ),
                    self.assertRaises(SettingsError),
                ):
                    Settings.from_environment()
            (home / "auth.json").chmod(0o640)
            with (
                patch.dict(
                    os.environ,
                    {**base, "GLUPTA_RELEASE_PROFILE_FILE": str(write_profile(root))},
                    clear=True,
                ),
                self.assertRaisesRegex(SettingsError, "not private"),
            ):
                Settings.from_environment()

    def test_profile_cache_and_generation_revalidation(self) -> None:
        expected = Settings(input_root=Path("/inputs"), token="t" * 32)
        get_settings.cache_clear()
        try:
            with patch.object(Settings, "from_environment", return_value=expected) as load:
                self.assertIs(get_settings(), expected)
                self.assertIs(get_settings(), expected)
            load.assert_called_once_with()
        finally:
            get_settings.cache_clear()
        profile = release_profile(auth_generation=2)
        settings = Settings(
            input_root=Path("/inputs"),
            token="t" * 32,
            release_profile=profile,
            release_profile_digest=profile.digest(),
            codex_home=Path("/private/codex"),
            auth_generation=1,
        )
        with self.assertRaisesRegex(SettingsError, "generation"):
            settings.require_external_profile()
