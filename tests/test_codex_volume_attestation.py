# ruff: noqa: S101
from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from itertools import pairwise
from unittest.mock import patch

import pytest

from scripts import attest_codex_subscription_volume as attestation

IMAGE_ID = "sha256:" + "a" * 64
VOLUME = "glupta-codex-subscription-g7-" + "b" * 32
SESSION_NAME = "codex-arg06IEJpF"


def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout, "")


def _probe() -> dict[str, object]:
    def node(
        kind: str,
        mode: str,
        *,
        nlink: int | None = None,
        target: str | None = None,
    ) -> dict[str, object]:
        result: dict[str, object] = {"type": kind, "uid": 65532, "mode": mode}
        if nlink is not None:
            result["nlink"] = nlink
        if target is not None:
            result["target"] = target
        return result

    return {
        "session_name": SESSION_NAME,
        "inventories": {
            "root": ["auth.json", "log", "tmp"],
            "log": ["codex-login.log"],
            "tmp": ["arg0"],
            "arg0": [SESSION_NAME],
            "session": attestation.EXPECTED_SESSION_INVENTORY,
        },
        "nodes": {
            "root": node("directory", "0700"),
            "auth": node("regular", "0600", nlink=1),
            "log": node("directory", "0755"),
            "login_log": node("regular", "0600", nlink=1),
            "tmp": node("directory", "0755"),
            "arg0": node("directory", "0700"),
            "session": node("directory", "0755"),
            "lock": node("regular", "0644", nlink=1),
            "apply_patch": node("symlink", "0777", nlink=1, target=attestation.CODEX_BINARY_TARGET),
            "applypatch": node("symlink", "0777", nlink=1, target=attestation.CODEX_BINARY_TARGET),
            "codex_execve_wrapper": node(
                "symlink", "0777", nlink=1, target=attestation.CODEX_BINARY_TARGET
            ),
            "codex_linux_sandbox": node(
                "symlink", "0777", nlink=1, target=attestation.CODEX_BINARY_TARGET
            ),
        },
    }


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
    probe = _probe()

    def run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((arguments, kwargs))
        if "volume" in arguments:
            return _completed(json.dumps(volume))
        if "image" in arguments:
            return _completed(IMAGE_ID + "\n")
        return _completed(json.dumps(probe) + "\n")

    with (
        patch.object(attestation.shutil, "which", return_value="/reviewed/bin/docker") as which,
        patch.object(attestation.subprocess, "run", side_effect=run),
        patch.dict(attestation.os.environ, {"HOME": "/reviewed/home"}, clear=True),
    ):
        result = attestation.main(["--volume", VOLUME, "--generation", "7", "--image-id", IMAGE_ID])
        assert result == 0
        which.assert_called_once_with("docker")

    receipt = json.loads(capsys.readouterr().out)
    assert receipt == {
        "generation": 7,
        "image_id": IMAGE_ID,
        "inventories": {
            "arg0": [SESSION_NAME],
            "log": ["codex-login.log"],
            "root": ["auth.json", "log", "tmp"],
            "session": attestation.EXPECTED_SESSION_INVENTORY,
            "tmp": ["arg0"],
        },
        "modes": {
            "apply_patch": "0777",
            "applypatch": "0777",
            "arg0": "0700",
            "auth": "0600",
            "codex_execve_wrapper": "0777",
            "codex_linux_sandbox": "0777",
            "lock": "0644",
            "log": "0755",
            "login_log": "0600",
            "root": "0700",
            "session": "0755",
            "tmp": "0755",
        },
        "schema_version": "glupta-codex-volume-attestation-v2",
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
    assert "os.lstat" in attestation.PROBE
    assert "os.listdir" in attestation.PROBE
    assert "os.readlink" in attestation.PROBE
    assert "open(" not in attestation.PROBE
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


def _invalid_probe(case: str) -> dict[str, object]:
    probe = deepcopy(_probe())
    inventories = probe["inventories"]
    nodes = probe["nodes"]
    assert isinstance(inventories, dict)
    assert isinstance(nodes, dict)
    mutations = {
        "pre_auth": lambda: inventories.__setitem__("root", ["log", "tmp"]),
        "auth_only": lambda: inventories.__setitem__("root", ["auth.json"]),
        "extra_root": lambda: inventories.__setitem__(
            "root", ["auth.json", "config.toml", "log", "tmp"]
        ),
        "missing_log": lambda: inventories.__setitem__("log", []),
        "extra_tmp": lambda: inventories.__setitem__("tmp", ["arg0", "state"]),
        "empty_arg0": lambda: inventories.__setitem__("arg0", []),
        "two_sessions": lambda: inventories.__setitem__("arg0", [SESSION_NAME, "codex-arg0ABC123"]),
        "bad_session_name": lambda: (
            probe.__setitem__("session_name", "codex-arg0-stale"),
            inventories.__setitem__("arg0", ["codex-arg0-stale"]),
        ),
        "extra_helper": lambda: inventories.__setitem__(
            "session", [*attestation.EXPECTED_SESSION_INVENTORY, "config.toml"]
        ),
        "wrong_type": lambda: nodes["auth"].__setitem__("type", "symlink"),
        "wrong_uid": lambda: nodes["session"].__setitem__("uid", 0),
        "wrong_root_mode": lambda: nodes["root"].__setitem__("mode", "0755"),
        "unsafe_tmp_mode": lambda: nodes["tmp"].__setitem__("mode", "0775"),
        "special_log_mode": lambda: nodes["log"].__setitem__("mode", "2755"),
        "wrong_session_mode": lambda: nodes["session"].__setitem__("mode", "0700"),
        "wrong_lock_mode": lambda: nodes["lock"].__setitem__("mode", "0600"),
        "wrong_nlink": lambda: nodes["login_log"].__setitem__("nlink", 2),
        "alias_regular": lambda: nodes["apply_patch"].__setitem__("type", "regular"),
        "alias_wrong_target": lambda: nodes["apply_patch"].__setitem__(
            "target", "/unapproved/codex"
        ),
        "alias_relative_target": lambda: nodes["apply_patch"].__setitem__(
            "target", "../../bin/codex"
        ),
        "alias_wrong_mode": lambda: nodes["apply_patch"].__setitem__("mode", "0755"),
        "extra_probe_node": lambda: nodes.__setitem__(
            "extra", {"type": "regular", "uid": 65532, "mode": "0600", "nlink": 1}
        ),
    }
    mutations[case]()
    return probe


@pytest.mark.parametrize(
    "case",
    [
        "pre_auth",
        "auth_only",
        "extra_root",
        "missing_log",
        "extra_tmp",
        "empty_arg0",
        "two_sessions",
        "bad_session_name",
        "extra_helper",
        "wrong_type",
        "wrong_uid",
        "wrong_root_mode",
        "unsafe_tmp_mode",
        "special_log_mode",
        "wrong_session_mode",
        "wrong_lock_mode",
        "wrong_nlink",
        "alias_regular",
        "alias_wrong_target",
        "alias_relative_target",
        "alias_wrong_mode",
        "extra_probe_node",
    ],
)
def test_rejects_incomplete_extra_or_unsafe_native_layout(case: str) -> None:
    probe = _invalid_probe(case)
    volume = {
        "Name": VOLUME,
        "Labels": {
            **attestation.EXPECTED_LABELS,
            "com.glupta.generation": "7",
        },
    }
    responses = iter((json.dumps(volume), IMAGE_ID + "\n", json.dumps(probe)))
    with (
        patch.object(attestation, "_run", side_effect=lambda _arguments: next(responses)),
        pytest.raises(attestation.AttestationError, match="metadata is invalid"),
    ):
        attestation._attest("/reviewed/bin/docker", VOLUME, 7, IMAGE_ID)


def test_probe_failure_covers_wrong_type_or_symlink_without_exposing_metadata(capsys) -> None:
    marker = "private-path-marker"
    volume = {
        "Name": VOLUME,
        "Labels": {
            **attestation.EXPECTED_LABELS,
            "com.glupta.generation": "7",
        },
    }
    calls = 0

    def run(arguments, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _completed(json.dumps(volume))
        if calls == 2:
            return _completed(IMAGE_ID + "\n")
        return subprocess.CompletedProcess([], 2, marker, marker)

    with (
        patch.object(attestation.shutil, "which", return_value="/reviewed/bin/docker"),
        patch.object(attestation.subprocess, "run", side_effect=run),
    ):
        assert (
            attestation.main(["--volume", VOLUME, "--generation", "7", "--image-id", IMAGE_ID]) == 1
        )
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err
    assert captured.err == "Codex subscription volume attestation failed\n"


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
        result = attestation.main(["--volume", VOLUME, "--generation", "7", "--image-id", IMAGE_ID])
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
        result = attestation.main(["--volume", VOLUME, "--generation", "7", "--image-id", IMAGE_ID])
        assert result == 1
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err
    assert captured.err == "Codex subscription volume attestation failed\n"
