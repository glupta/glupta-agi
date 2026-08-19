from __future__ import annotations

import io
import json
import subprocess
import tarfile
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import pytest

from scripts import stage_private_volumes as staging


def _environment() -> dict[str, str]:
    return {
        "GLUPTA_CREDENTIAL_GENERATION": "7",
        "GLUPTA_INTAKE_TOKEN": "intake-" + "x" * 32,
        "GLUPTA_POSTGRES_PASSWORD": "database-marker",
        "GLUPTA_RELEASE_PROFILE_JSON": '{"profile":"marker"}',
        "GLUPTA_OPENAI_API_KEY": "openai-key-" + "x" * 32,
        "PATH": "/reviewed/bin",
        "HOME": "/reviewed/home",
    }


def _entries(payload: bytes) -> dict[str, tuple[tarfile.TarInfo, bytes]]:
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        return {entry.name: (entry, archive.extractfile(entry).read()) for entry in archive}


def test_staging_streams_exact_private_files_without_child_environment_disclosure() -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append((arguments, kwargs))
        return subprocess.CompletedProcess(arguments, 0, b"", b"")

    output = io.StringIO()
    with (
        patch.dict(staging.os.environ, _environment(), clear=True),
        patch.object(staging.shutil, "which", return_value="/reviewed/bin/docker"),
        patch.object(staging.uuid, "uuid4", return_value=SimpleNamespace(hex="a" * 32)),
        patch.object(staging.subprocess, "run", side_effect=run),
        redirect_stdout(output),
    ):
        staging.main([])

    case = TestCase()
    receipt = json.loads(output.getvalue())
    case.assertEqual(receipt["generation"], 7)
    case.assertTrue(receipt["app_volume"].endswith("a" * 32))
    case.assertEqual(len(calls), 4)
    for arguments, kwargs in calls:
        joined = repr(arguments)
        case.assertTrue(all(marker not in joined for marker in
            ("database-marker", "profile", "openai-key")))
        case.assertEqual(kwargs["env"], {"HOME": "/reviewed/home", "PATH": "/reviewed/bin"})
    app = _entries(calls[1][1]["input"])
    case.assertIn("--interactive", calls[1][0])
    case.assertEqual(set(app), set(staging.APP_FILES))
    case.assertTrue(all(entry.uid == entry.gid == 65532 and entry.mode == 0o600
        for entry, _ in app.values()))
    postgres = _entries(calls[3][1]["input"])
    entry, contents = postgres["postgres-password"]
    case.assertTrue(entry.uid == entry.gid == 999 and entry.mode == 0o600)
    case.assertEqual(contents, b"database-marker")


def test_missing_bundle_fails_before_docker() -> None:
    with (
        patch.dict(staging.os.environ, {}, clear=True),
        patch.object(staging.subprocess, "run") as run,
        pytest.raises(staging.StagingError, match="missing or invalid"),
    ):
        staging.main([])
    run.assert_not_called()


def test_app_only_stages_no_postgres_volume() -> None:
    calls: list[list[str]] = []

    def run(arguments: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, b"", b"")

    output = io.StringIO()
    with (
        patch.dict(staging.os.environ, _environment(), clear=True),
        patch.object(staging.shutil, "which", return_value="/reviewed/bin/docker"),
        patch.object(staging.uuid, "uuid4", return_value=SimpleNamespace(hex="b" * 32)),
        patch.object(staging.subprocess, "run", side_effect=run),
        redirect_stdout(output),
    ):
        staging.main(["--app-only"])

    case = TestCase()
    receipt = json.loads(output.getvalue())
    case.assertIsNone(receipt["postgres_volume"])
    case.assertEqual(len(calls), 2)
    case.assertTrue(all("postgres-private" not in repr(arguments) for arguments in calls))
