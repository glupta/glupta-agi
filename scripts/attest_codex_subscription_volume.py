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
SCHEMA_VERSION = "glupta-codex-volume-attestation-v1"
IMAGE_ID_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
VOLUME_PATTERN = re.compile(r"glupta-codex-subscription-g([1-9][0-9]*)-[0-9a-f]{32}\Z")
EXPECTED_LABELS = {
    "com.glupta.private": "true",
    "com.glupta.purpose": "codex-subscription",
}
PROBE = """import json, os, stat
root = os.lstat('/run/codex')
names = sorted(os.listdir('/run/codex'))
auth = os.lstat('/run/codex/auth.json') if names == ['auth.json'] else None
valid = all((
    stat.S_ISDIR(root.st_mode), stat.S_IMODE(root.st_mode) == 0o700,
    root.st_uid == 65532, auth is not None,
    auth is not None and stat.S_ISREG(auth.st_mode),
    auth is not None and stat.S_IMODE(auth.st_mode) == 0o600,
    auth is not None and auth.st_uid == 65532,
))
if not valid:
    raise SystemExit(2)
print(json.dumps({
    'root_uid': root.st_uid, 'root_mode': format(stat.S_IMODE(root.st_mode), '04o'),
    'auth_uid': auth.st_uid, 'auth_mode': format(stat.S_IMODE(auth.st_mode), '04o'),
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
        "inventory": ["auth.json"],
    }
    if probe != expected_probe:
        raise AttestationError("Codex subscription volume metadata is invalid")
    return {
        "schema_version": SCHEMA_VERSION,
        "volume": volume,
        "generation": generation,
        "image_id": image_id,
        **expected_probe,
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
