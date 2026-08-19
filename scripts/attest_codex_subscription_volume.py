#!/usr/bin/python3
"""Attest a local Codex subscription volume without reading authentication bytes."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any

APP_UID = 65532
SCHEMA_VERSION = "glupta-codex-volume-attestation-v2"
IMAGE_ID_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
VOLUME_PATTERN = re.compile(r"glupta-codex-subscription-g([1-9][0-9]*)-[0-9a-f]{32}\Z")
EXPECTED_LABELS = {
    "com.glupta.private": "true",
    "com.glupta.purpose": "codex-subscription",
}
PROBE = """import json, os, stat
base = '/run/codex'
root = os.lstat(base)
names = sorted(os.listdir(base))
auth = os.lstat(base + '/auth.json') if names == ['auth.json', 'log', 'tmp'] else None
log = os.lstat(base + '/log') if auth is not None else None
tmp = os.lstat(base + '/tmp') if auth is not None else None
log_names = (
    sorted(os.listdir(base + '/log'))
    if log is not None and stat.S_ISDIR(log.st_mode) else None
)
tmp_names = (
    sorted(os.listdir(base + '/tmp'))
    if tmp is not None and stat.S_ISDIR(tmp.st_mode) else None
)
login_log = os.lstat(base + '/log/codex-login.log') if log_names == ['codex-login.log'] else None
arg0 = os.lstat(base + '/tmp/arg0') if tmp_names == ['arg0'] else None
arg0_names = (
    sorted(os.listdir(base + '/tmp/arg0'))
    if arg0 is not None and stat.S_ISDIR(arg0.st_mode) else None
)
directory_mode = lambda item: stat.S_IMODE(item.st_mode)
private_created_dir = lambda item: all((
    stat.S_ISDIR(item.st_mode), item.st_uid == 65532,
    directory_mode(item) & 0o700 == 0o700,
    directory_mode(item) & 0o7022 == 0,
))
valid = all((
    stat.S_ISDIR(root.st_mode), stat.S_IMODE(root.st_mode) == 0o700,
    root.st_uid == 65532, auth is not None,
    auth is not None and stat.S_ISREG(auth.st_mode),
    auth is not None and stat.S_IMODE(auth.st_mode) == 0o600,
    auth is not None and auth.st_uid == 65532, auth is not None and auth.st_nlink == 1,
    log is not None and private_created_dir(log),
    tmp is not None and private_created_dir(tmp),
    login_log is not None and stat.S_ISREG(login_log.st_mode),
    login_log is not None and stat.S_IMODE(login_log.st_mode) == 0o600,
    login_log is not None and login_log.st_uid == 65532,
    login_log is not None and login_log.st_nlink == 1,
    arg0 is not None and stat.S_ISDIR(arg0.st_mode),
    arg0 is not None and stat.S_IMODE(arg0.st_mode) == 0o700,
    arg0 is not None and arg0.st_uid == 65532, arg0_names == [],
))
if not valid:
    raise SystemExit(2)
print(json.dumps({
    'root_uid': root.st_uid, 'root_mode': format(stat.S_IMODE(root.st_mode), '04o'),
    'auth_uid': auth.st_uid,
    'auth_mode': format(stat.S_IMODE(auth.st_mode), '04o'),
    'auth_nlink': auth.st_nlink,
    'log_uid': log.st_uid,
    'log_mode': format(directory_mode(log), '04o'),
    'log_inventory': log_names,
    'login_log_uid': login_log.st_uid,
    'login_log_mode': format(stat.S_IMODE(login_log.st_mode), '04o'),
    'login_log_nlink': login_log.st_nlink,
    'tmp_uid': tmp.st_uid,
    'tmp_mode': format(directory_mode(tmp), '04o'),
    'tmp_inventory': tmp_names,
    'arg0_uid': arg0.st_uid,
    'arg0_mode': format(stat.S_IMODE(arg0.st_mode), '04o'),
    'arg0_inventory': arg0_names,
    'inventory': names,
}, sort_keys=True))
"""


class AttestationError(RuntimeError):
    pass


def _environment() -> dict[str, str]:
    return {"HOME": os.environ.get("HOME", "/nonexistent"), "PATH": os.defpath}


def _run(arguments: list[str]) -> str:
    completed = subprocess.run(  # noqa: S603
        arguments,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=_environment(),
    )
    if completed.returncode:
        raise AttestationError("Docker subscription-volume inspection failed")
    return completed.stdout


def _parse(argv: list[str]) -> tuple[str, int, str]:
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument("--volume", required=True)
    parser.add_argument("--generation", required=True)
    parser.add_argument("--image-id", required=True)
    try:
        options = parser.parse_args(argv)
        generation = int(options.generation)
    except (argparse.ArgumentError, SystemExit, ValueError):
        raise ValueError from None
    match = VOLUME_PATTERN.fullmatch(options.volume)
    if (
        match is None
        or int(match.group(1)) != generation
        or str(generation) != options.generation
        or IMAGE_ID_PATTERN.fullmatch(options.image_id) is None
    ):
        raise ValueError
    return options.volume, generation, options.image_id


def _json(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        raise AttestationError("Docker subscription-volume response is invalid") from None
    if not isinstance(parsed, dict):
        raise AttestationError("Docker subscription-volume response is invalid")
    return parsed


def _private_created_directory_mode(value: Any) -> bool:
    if not isinstance(value, str) or re.fullmatch(r"0[0-7]{3}", value) is None:
        return False
    mode = int(value, 8)
    return mode & 0o700 == 0o700 and mode & 0o7022 == 0


def _attest(docker: str, volume: str, generation: int, image_id: str) -> dict[str, Any]:
    prefix = [docker, "--context", "colima"]
    metadata = _json(
        _run([*prefix, "volume", "inspect", volume, "--format", "{{json .}}"])
    )
    labels = metadata.get("Labels")
    expected = {**EXPECTED_LABELS, "com.glupta.generation": str(generation)}
    invalid_labels = not isinstance(labels, dict) or any(
        labels.get(key) != value for key, value in expected.items()
    )
    if metadata.get("Name") != volume or invalid_labels:
        raise AttestationError("Codex subscription volume identity is invalid")
    observed_image = _run(
        [*prefix, "image", "inspect", image_id, "--format", "{{.Id}}"]
    ).strip()
    if observed_image != image_id:
        raise AttestationError("Codex subscription image identity is invalid")
    probe = _json(
        _run(
            [
                *prefix,
                "run",
                "--rm",
                "--pull",
                "never",
                "--network",
                "none",
                "--read-only",
                "--security-opt",
                "no-new-privileges:true",
                "--cap-drop",
                "ALL",
                "--user",
                f"{APP_UID}:{APP_UID}",
                "--mount",
                f"type=volume,src={volume},dst=/run/codex,readonly",
                "--entrypoint",
                "/app/.venv/bin/python",
                image_id,
                "-c",
                PROBE,
            ]
        )
    )
    expected_probe = {
        "root_uid": APP_UID,
        "root_mode": "0700",
        "auth_uid": APP_UID,
        "auth_mode": "0600",
        "auth_nlink": 1,
        "inventory": ["auth.json", "log", "tmp"],
        "log_uid": APP_UID,
        "log_inventory": ["codex-login.log"],
        "login_log_uid": APP_UID,
        "login_log_mode": "0600",
        "login_log_nlink": 1,
        "tmp_uid": APP_UID,
        "tmp_inventory": ["arg0"],
        "arg0_uid": APP_UID,
        "arg0_mode": "0700",
        "arg0_inventory": [],
    }
    observed_modes = {key: probe.get(key) for key in ("log_mode", "tmp_mode")}
    without_observed_modes = {
        key: value for key, value in probe.items() if key not in observed_modes
    }
    if (
        without_observed_modes != expected_probe
        or not all(_private_created_directory_mode(value) for value in observed_modes.values())
    ):
        raise AttestationError("Codex subscription volume metadata is invalid")
    return {
        "schema_version": SCHEMA_VERSION,
        "volume": volume,
        "generation": generation,
        "image_id": image_id,
        **expected_probe,
        **observed_modes,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        volume, generation, image_id = _parse(list(sys.argv[1:] if argv is None else argv))
    except ValueError:
        print(
            "usage: attest_codex_subscription_volume.py --volume NAME "
            "--generation N --image-id sha256:HEX",
            file=sys.stderr,
        )
        return 2
    docker = shutil.which("docker")
    if docker is None:
        print("Codex subscription volume attestation failed", file=sys.stderr)
        return 1
    try:
        receipt = _attest(docker, volume, generation, image_id)
    except (AttestationError, OSError, subprocess.SubprocessError):
        print("Codex subscription volume attestation failed", file=sys.stderr)
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
