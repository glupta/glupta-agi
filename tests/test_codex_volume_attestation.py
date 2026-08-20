# ruff: noqa: S101
from __future__ import annotations

import io
import json
import os
import stat
import subprocess
from contextlib import redirect_stdout
from copy import deepcopy
from itertools import pairwise
from pathlib import Path
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
        "system_skill_manifest": None,
        "inventories": {
            "root": ["auth.json", "log", "tmp"],
            "log": ["codex-login.log"],
            "tmp": ["arg0"],
            "arg0": [SESSION_NAME],
            "session": attestation.EXPECTED_SESSION_INVENTORY,
        },
        "nodes": {
            "root": node("directory", "0700", nlink=4),
            "auth": node("regular", "0600", nlink=1),
            "log": node("directory", "0755", nlink=2),
            "login_log": node("regular", "0600", nlink=1),
            "tmp": node("directory", "0755", nlink=3),
            "arg0": node("directory", "0700", nlink=3),
            "session": node("directory", "0755", nlink=2),
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


def _post_use_probe() -> dict[str, object]:
    probe = _probe()
    inventories = probe["inventories"]
    nodes = probe["nodes"]
    assert isinstance(inventories, dict)
    assert isinstance(nodes, dict)
    inventories["root"] = attestation.POST_USE_ROOT_INVENTORY
    inventories["skills"] = attestation.EXPECTED_SYSTEM_ROOT_INVENTORY
    inventories["skills/.system"] = attestation.EXPECTED_SYSTEM_INVENTORY
    for name in attestation.EXPECTED_SYSTEM_INVENTORY:
        if name != ".codex-system-skills.marker":
            inventories[f"skills/.system/{name}"] = []
    inventories["skills/.system/review-agent"] = ["SKILL.md"]
    probe["system_skill_manifest"] = attestation.EXPECTED_SYSTEM_SKILL_MANIFEST
    nodes["root"]["nlink"] = 5
    nodes["installation_id"] = {
        "type": "regular",
        "uid": 65532,
        "mode": "0644",
        "nlink": 1,
    }
    nodes["models_cache"] = {
        "type": "regular",
        "uid": 65532,
        "mode": "0644",
        "nlink": 1,
    }
    skill_directories = {name for name in inventories if name.startswith("skills")}
    for name in skill_directories:
        inventory = inventories[name]
        child_directories = sum(f"{name}/{child}" in skill_directories for child in inventory)
        nodes[name] = {
            "type": "directory",
            "uid": 65532,
            "mode": "0755",
            "nlink": 2 + child_directories,
        }
    for name in (
        "skills/.system/.codex-system-skills.marker",
        "skills/.system/review-agent/SKILL.md",
    ):
        nodes[name] = {
            "type": "regular",
            "uid": 65532,
            "mode": "0644",
            "nlink": 1,
        }
    return probe


def _native_volume_tree(tmp_path: Path, *, runtime_materialized: bool) -> tuple[Path, Path]:
    root = tmp_path / "codex"
    log = root / "log"
    arg0 = root / "tmp" / "arg0"
    session = arg0 / SESSION_NAME
    log.mkdir(parents=True)
    session.mkdir(parents=True)
    root.chmod(0o700)
    log.chmod(0o755)
    (root / "tmp").chmod(0o755)
    arg0.chmod(0o700)
    session.chmod(0o755)
    for path, content, mode in (
        (root / "auth.json", b"controlled-auth-bytes", 0o600),
        (log / "codex-login.log", b"controlled-log-bytes", 0o600),
        (session / ".lock", b"", 0o644),
    ):
        path.write_bytes(content)
        path.chmod(mode)
    for helper in attestation.EXPECTED_SESSION_INVENTORY:
        if helper != ".lock":
            (session / helper).symlink_to(attestation.CODEX_BINARY_TARGET)
    migration_marker = root / ".sandbox_migration"
    migration_marker.write_bytes(b"v1\n")
    migration_marker.chmod(0o600)
    if runtime_materialized:
        for filename in ("installation_id", "models_cache.json"):
            path = root / filename
            path.write_bytes(b"controlled-runtime-bytes")
            path.chmod(0o644)
        system_skills = root / "skills" / ".system"
        system_skills.mkdir(parents=True)
        (root / "skills").chmod(0o755)
        system_skills.chmod(0o755)
        system_marker = system_skills / ".codex-system-skills.marker"
        system_marker.write_bytes(b"controlled-system-skill-bytes")
        system_marker.chmod(0o644)
        for skill in attestation.EXPECTED_SYSTEM_INVENTORY:
            if skill != ".codex-system-skills.marker":
                path = system_skills / skill
                path.mkdir()
                path.chmod(0o755)
    return root, migration_marker


def _execute_post_migration_probe(
    root: Path,
    migration_marker: Path,
    *,
    invalid_marker_field: str | None = None,
) -> tuple[dict[str, object] | None, list[Path], int | None]:
    probe = attestation.PROBE.replace("base = '/run/codex'", f"base = {str(root)!r}", 1)
    real_lstat = os.lstat
    real_open = os.open
    opened: list[Path] = []

    def reviewed_lstat(path: os.PathLike[str] | str) -> os.stat_result:
        observed = real_lstat(path)
        values = list(observed)
        values[4] = attestation.APP_UID
        values[5] = attestation.APP_GID
        if stat.S_ISDIR(values[0]):
            values[3] = 2 + sum(entry.is_dir(follow_symlinks=False) for entry in os.scandir(path))
        elif stat.S_ISLNK(values[0]):
            values[0] = stat.S_IFLNK | 0o777
        if Path(path) == migration_marker:
            if invalid_marker_field == "type":
                values[0] = stat.S_IFIFO | stat.S_IMODE(values[0])
            elif invalid_marker_field == "uid":
                values[4] = 0
            elif invalid_marker_field == "gid":
                values[5] = 0
            elif invalid_marker_field == "mode":
                values[0] = stat.S_IFREG | 0o644
            elif invalid_marker_field == "nlink":
                values[3] = 2
            elif invalid_marker_field == "size":
                values[6] = attestation.MIGRATION_MARKER_SIZE + 1
        return os.stat_result(values)

    def reviewed_open(path: os.PathLike[str] | str, flags: int, mode: int = 0o777) -> int:
        opened.append(Path(path))
        return real_open(path, flags, mode)

    output = io.StringIO()
    with (
        patch.object(attestation.os, "lstat", side_effect=reviewed_lstat),
        patch.object(attestation.os, "open", side_effect=reviewed_open),
        redirect_stdout(output),
    ):
        try:
            exec(compile(probe, "<volume-probe>", "exec"), {})  # noqa: S102
        except SystemExit as stopped:
            assert isinstance(stopped.code, int)
            return None, opened, stopped.code
    return json.loads(output.getvalue()), opened, None


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
        "layout": "completed-login",
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
        "schema_version": "glupta-codex-volume-attestation-v4",
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
    assert "open(path, 'rb')" not in attestation.PROBE
    assert "os.open(path, os.O_RDONLY | os.O_NOFOLLOW)" in attestation.PROBE
    assert "os.fstat(descriptor)" in attestation.PROBE
    assert "os.fdopen(descriptor, 'rb')" in attestation.PROBE
    assert "open(paths[" not in attestation.PROBE
    assert all(
        kwargs["env"] == {"HOME": "/reviewed/home", "PATH": attestation.os.defpath}
        for _, kwargs in calls
    )


def test_attests_exact_post_use_runtime_metadata() -> None:
    receipt = attestation._validate_probe(_post_use_probe())

    assert receipt["layout"] == "post-use"
    assert receipt["inventories"] == {
        "root": attestation.POST_USE_ROOT_INVENTORY,
        "log": ["codex-login.log"],
        "tmp": ["arg0"],
        "arg0": [SESSION_NAME],
        "session": attestation.EXPECTED_SESSION_INVENTORY,
        "skills": attestation.EXPECTED_SYSTEM_ROOT_INVENTORY,
        "skills/.system": attestation.EXPECTED_SYSTEM_INVENTORY,
        **{
            f"skills/.system/{name}": (["SKILL.md"] if name == "review-agent" else [])
            for name in attestation.EXPECTED_SYSTEM_INVENTORY
            if name != ".codex-system-skills.marker"
        },
    }
    assert receipt["system_skill_manifest"] == attestation.EXPECTED_SYSTEM_SKILL_MANIFEST
    assert receipt["modes"]["installation_id"] == "0644"
    assert receipt["modes"]["models_cache"] == "0644"
    assert all(
        receipt["modes"][name] == "0755"
        for name in receipt["inventories"]
        if name.startswith("skills")
    )
    assert receipt["modes"]["skills/.system/review-agent/SKILL.md"] == "0644"


def test_executable_probe_attests_exact_native_post_migration_metadata(tmp_path: Path) -> None:
    root, migration_marker = _native_volume_tree(tmp_path, runtime_materialized=True)
    probe, opened, exit_code = _execute_post_migration_probe(root, migration_marker)
    assert probe is not None
    assert exit_code is None
    system_manifest = probe["system_skill_manifest"]

    with patch.object(attestation, "EXPECTED_SYSTEM_SKILL_MANIFEST", system_manifest):
        receipt = attestation._validate_probe(probe)

    assert receipt["layout"] == "post-migration"
    assert receipt["inventories"]["root"] == attestation.POST_MIGRATION_ROOT_INVENTORY
    assert receipt["modes"]["sandbox_migration"] == "0600"
    assert probe["nodes"]["sandbox_migration"] == {
        "type": "regular",
        "uid": attestation.APP_UID,
        "gid": attestation.APP_GID,
        "mode": "0600",
        "nlink": 1,
        "size": attestation.MIGRATION_MARKER_SIZE,
    }
    assert opened == [root / "skills" / ".system" / ".codex-system-skills.marker"]
    assert migration_marker not in opened
    assert not {
        root / "auth.json",
        root / "log" / "codex-login.log",
        root / "installation_id",
        root / "models_cache.json",
    }.intersection(opened)


@pytest.mark.parametrize("invalid_marker_field", ["type", "uid", "gid", "mode", "nlink", "size"])
def test_executable_probe_rejects_wrong_native_migration_marker_metadata(
    tmp_path: Path, invalid_marker_field: str
) -> None:
    root, migration_marker = _native_volume_tree(tmp_path, runtime_materialized=True)
    probe, opened, exit_code = _execute_post_migration_probe(
        root,
        migration_marker,
        invalid_marker_field=invalid_marker_field,
    )

    assert probe is None
    assert exit_code == 2
    assert opened == []
    assert migration_marker not in opened
    assert not {
        root / "auth.json",
        root / "log" / "codex-login.log",
        root / "installation_id",
        root / "models_cache.json",
    }.intersection(opened)


def test_executable_probe_rejects_migration_marker_mixed_with_pre_use_root(
    tmp_path: Path,
) -> None:
    root, _migration_marker = _native_volume_tree(tmp_path, runtime_materialized=False)
    probe = attestation.PROBE.replace("base = '/run/codex'", f"base = {str(root)!r}", 1)

    with (
        patch.object(attestation.os, "open") as open_file,
        pytest.raises(SystemExit) as stopped,
    ):
        exec(compile(probe, "<volume-probe>", "exec"), {})  # noqa: S102

    assert stopped.value.code == 2
    open_file.assert_not_called()


def test_probe_rejects_top_level_skills_symlink_without_opening_target(tmp_path) -> None:
    root = tmp_path / "codex"
    log = root / "log"
    arg0 = root / "tmp" / "arg0"
    log.mkdir(parents=True)
    arg0.mkdir(parents=True)
    (root / "auth.json").touch()
    (root / "installation_id").touch()
    (root / "models_cache.json").touch()
    (log / "codex-login.log").write_text("controlled-target-marker", encoding="utf-8")
    (root / "skills").symlink_to(log, target_is_directory=True)
    probe = attestation.PROBE.replace("base = '/run/codex'", f"base = {str(root)!r}", 1)

    with (
        patch.object(attestation.os, "open") as open_file,
        pytest.raises(SystemExit) as stopped,
    ):
        exec(compile(probe, "<volume-probe>", "exec"), {})  # noqa: S102

    assert stopped.value.code == 2
    open_file.assert_not_called()


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


@pytest.mark.parametrize(
    "case",
    [
        "partial_root",
        "missing_runtime_node",
        "extra_system_skill",
        "extra_nested_file",
        "wrong_skill_manifest",
        "skill_symlink",
        "wrong_skill_directory_nlink",
        "wrong_skill_file_nlink",
    ],
)
def test_rejects_partial_mixed_or_extra_post_use_layout(case: str) -> None:
    probe = _post_use_probe()
    inventories = probe["inventories"]
    nodes = probe["nodes"]
    assert isinstance(inventories, dict)
    assert isinstance(nodes, dict)
    if case == "partial_root":
        inventories["root"] = ["auth.json", "installation_id", "log", "tmp"]
    elif case == "missing_runtime_node":
        nodes.pop("installation_id")
    elif case == "extra_system_skill":
        inventories["skills/.system"].append("unapproved")
    elif case == "extra_nested_file":
        inventories["skills/.system/review-agent"].append("config.toml")
    elif case == "wrong_skill_manifest":
        probe["system_skill_manifest"] = "0" * 64
    elif case == "skill_symlink":
        nodes["skills/.system/review-agent/SKILL.md"] = {
            "type": "symlink",
            "uid": 65532,
            "mode": "0777",
            "nlink": 1,
            "target": "/unapproved",
        }
    elif case == "wrong_skill_directory_nlink":
        nodes["skills/.system/review-agent"]["nlink"] = 4
    else:
        nodes["skills/.system/review-agent/SKILL.md"]["nlink"] = 2

    with pytest.raises(attestation.AttestationError, match="metadata is invalid"):
        attestation._validate_probe(probe)


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
