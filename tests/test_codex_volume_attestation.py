# ruff: noqa: S101
from __future__ import annotations

import json
import subprocess
from itertools import pairwise
from unittest.mock import patch

import pytest

from scripts import attest_codex_subscription_volume as attestation

IMAGE_ID = "sha256:" + "a" * 64
VOLUME = "glupta-codex-subscription-g7-" + "b" * 32


def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout, "")


def test_attests_exact_labeled_volume_with_metadata_only_probe(capsys) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    volume = {
        "Name": VOLUME,
        "Labels": {
            "com.glupta.private": "true",
            "com.glupta.purpose": "codex-subscription",
            "com.glupta.generation": "7",
        },
    }
    probe = {
        "root_uid": 65532,
        "root_mode": "0700",
        "auth_uid": 65532,
        "auth_mode": "0600",
        "inventory": ["auth.json"],
    }

    def run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((arguments, kwargs))
        if "volume" in arguments:
            return _completed(json.dumps(volume))
        if "image" in arguments:
            return _completed(IMAGE_ID + "\n")
        return _completed(json.dumps(probe) + "\n")

    with (
        patch.object(
            attestation.shutil, "which", return_value="/reviewed/bin/docker"
        ) as which,
        patch.object(attestation.subprocess, "run", side_effect=run),
        patch.dict(attestation.os.environ, {"HOME": "/reviewed/home"}, clear=True),
    ):
        result = attestation.main(
            ["--volume", VOLUME, "--generation", "7", "--image-id", IMAGE_ID]
        )
        assert result == 0
        which.assert_called_once_with("docker")

    receipt = json.loads(capsys.readouterr().out)
    assert receipt == {
        "auth_mode": "0600",
        "auth_uid": 65532,
        "generation": 7,
        "image_id": IMAGE_ID,
        "inventory": ["auth.json"],
        "root_mode": "0700",
        "root_uid": 65532,
        "schema_version": "glupta-codex-volume-attestation-v1",
        "volume": VOLUME,
    }
    probe_arguments, _probe_kwargs = calls[2]
    pairs = set(pairwise(probe_arguments))
    assert {("--network", "none"), ("--cap-drop", "ALL"), ("--pull", "never")} <= pairs
    assert "--read-only" in probe_arguments
    assert ("--security-opt", "no-new-privileges:true") in pairs
    assert ("--user", "65532:65532") in pairs
    assert ("--mount", f"type=volume,src={VOLUME},dst=/run/codex,readonly") in pairs
    assert probe_arguments[-3:] == [IMAGE_ID, "-c", attestation.PROBE]
    assert all(
        kwargs["env"] == {"HOME": "/reviewed/home", "PATH": attestation.os.defpath}
        for _, kwargs in calls
    )


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--volume", VOLUME, "--generation", "0", "--image-id", IMAGE_ID],
        ["--volume", VOLUME, "--generation", "07", "--image-id", IMAGE_ID],
        ["--volume", "other-volume", "--generation", "7", "--image-id", IMAGE_ID],
        ["--volume", VOLUME, "--generation", "7", "--image-id", "latest"],
    ],
)
def test_rejects_noncanonical_arguments_before_docker(arguments, capsys) -> None:
    with patch.object(attestation.subprocess, "run") as run:
        assert attestation.main(arguments) == 2
    run.assert_not_called()
    assert "usage:" in capsys.readouterr().err


def test_label_or_probe_mismatch_fails_closed_without_sensitive_output(capsys) -> None:
    marker = "raw-auth-marker"
    bad_volume = {
        "Name": VOLUME,
        "Labels": {
            "com.glupta.private": "true",
            "com.glupta.purpose": "codex-subscription",
            "com.glupta.generation": "8",
        },
    }
    with (
        patch.object(attestation.shutil, "which", return_value="/reviewed/bin/docker"),
        patch.object(
            attestation.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, json.dumps(bad_volume), marker),
        ) as run,
    ):
        result = attestation.main(
            ["--volume", VOLUME, "--generation", "7", "--image-id", IMAGE_ID]
        )
        assert result == 1
    assert run.call_count == 1
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err
    assert captured.err == "Codex subscription volume attestation failed\n"


def test_docker_or_json_failure_is_sanitized(capsys) -> None:
    marker = "raw-auth-marker"
    with (
        patch.object(attestation.shutil, "which", return_value="/reviewed/bin/docker"),
        patch.object(
            attestation.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 1, marker, marker),
        ),
    ):
        result = attestation.main(
            ["--volume", VOLUME, "--generation", "7", "--image-id", IMAGE_ID]
        )
        assert result == 1
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err
    assert captured.err == "Codex subscription volume attestation failed\n"
