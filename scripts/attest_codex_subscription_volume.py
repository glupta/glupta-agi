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
SESSION_PATTERN = re.compile(r"codex-arg0[A-Za-z0-9]{6}\Z")
CODEX_BINARY_TARGET = "/app/.venv/lib/python3.14/site-packages/codex_cli_bin/bin/codex"
EXPECTED_SESSION_INVENTORY = [
    ".lock",
    "apply_patch",
    "applypatch",
    "codex-execve-wrapper",
    "codex-linux-sandbox",
]
PROBE = """import json, os, re, stat
base = '/run/codex'
names = sorted(os.listdir(base))
if names != ['auth.json', 'log', 'tmp']:
    raise SystemExit(2)
paths = {
    'root': base,
    'auth': base + '/auth.json',
    'log': base + '/log',
    'login_log': base + '/log/codex-login.log',
    'tmp': base + '/tmp',
    'arg0': base + '/tmp/arg0',
}
stats = {name: os.lstat(path) for name, path in paths.items()}
if not all(stat.S_ISDIR(stats[name].st_mode) for name in ('root', 'log', 'tmp', 'arg0')):
    raise SystemExit(2)
inventories = {
    'root': names,
    'log': sorted(os.listdir(paths['log'])),
    'tmp': sorted(os.listdir(paths['tmp'])),
    'arg0': sorted(os.listdir(paths['arg0'])),
}
if inventories['log'] != ['codex-login.log'] or inventories['tmp'] != ['arg0']:
    raise SystemExit(2)
valid_session_name = (
    len(inventories['arg0']) == 1
    and re.fullmatch(r'codex-arg0[A-Za-z0-9]{6}', inventories['arg0'][0]) is not None
)
if not valid_session_name:
    raise SystemExit(2)
session_name = inventories['arg0'][0]
session_path = paths['arg0'] + '/' + session_name
stats['session'] = os.lstat(session_path)
if not stat.S_ISDIR(stats['session'].st_mode):
    raise SystemExit(2)
inventories['session'] = sorted(os.listdir(session_path))
expected_helpers = [
    '.lock', 'apply_patch', 'applypatch', 'codex-execve-wrapper', 'codex-linux-sandbox'
]
if inventories['session'] != expected_helpers:
    raise SystemExit(2)
helper_names = {
    'lock': '.lock',
    'apply_patch': 'apply_patch',
    'applypatch': 'applypatch',
    'codex_execve_wrapper': 'codex-execve-wrapper',
    'codex_linux_sandbox': 'codex-linux-sandbox',
}
for key, filename in helper_names.items():
    stats[key] = os.lstat(session_path + '/' + filename)
def node(value, path):
    if stat.S_ISDIR(value.st_mode):
        kind = 'directory'
    elif stat.S_ISREG(value.st_mode):
        kind = 'regular'
    elif stat.S_ISLNK(value.st_mode):
        kind = 'symlink'
    else:
        kind = 'other'
    result = {'type': kind, 'uid': value.st_uid, 'mode': format(stat.S_IMODE(value.st_mode), '04o')}
    if kind in ('regular', 'symlink'):
        result['nlink'] = value.st_nlink
    if kind == 'symlink':
        result['target'] = os.readlink(path)
    return result
node_paths = {**paths, 'session': session_path}
node_paths.update({key: session_path + '/' + filename for key, filename in helper_names.items()})
print(json.dumps({
    'session_name': session_name,
    'inventories': inventories,
    'nodes': {name: node(value, node_paths[name]) for name, value in stats.items()},
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


def _node(
    nodes: object,
    name: str,
    *,
    kind: str,
    mode: str | None = None,
    private_directory: bool = False,
    target: str | None = None,
) -> bool:
    if not isinstance(nodes, dict) or not isinstance(nodes.get(name), dict):
        return False
    value = nodes[name]
    expected_keys = {"type", "uid", "mode"}
    if kind in {"regular", "symlink"}:
        expected_keys.add("nlink")
    if kind == "symlink":
        expected_keys.add("target")
    return all(
        (
            set(value) == expected_keys,
            value.get("type") == kind,
            type(value.get("uid")) is int,
            value.get("uid") == APP_UID,
            mode is None or value.get("mode") == mode,
            not private_directory or _private_created_directory_mode(value.get("mode")),
            kind not in {"regular", "symlink"} or value.get("nlink") == 1,
            target is None or value.get("target") == target,
        )
    )


def _validate_probe(probe: dict[str, Any]) -> dict[str, Any]:
    session_name = probe.get("session_name")
    inventories = probe.get("inventories")
    nodes = probe.get("nodes")
    expected_inventories = {
        "root": ["auth.json", "log", "tmp"],
        "log": ["codex-login.log"],
        "tmp": ["arg0"],
        "arg0": [session_name],
        "session": EXPECTED_SESSION_INVENTORY,
    }
    aliases = {
        "apply_patch",
        "applypatch",
        "codex_execve_wrapper",
        "codex_linux_sandbox",
    }
    node_names = {
        "root",
        "auth",
        "log",
        "login_log",
        "tmp",
        "arg0",
        "session",
        "lock",
        *aliases,
    }
    valid = all(
        (
            set(probe) == {"session_name", "inventories", "nodes"},
            isinstance(session_name, str),
            isinstance(session_name, str) and SESSION_PATTERN.fullmatch(session_name) is not None,
            inventories == expected_inventories,
            isinstance(nodes, dict) and set(nodes) == node_names,
            _node(nodes, "root", kind="directory", mode="0700"),
            _node(nodes, "auth", kind="regular", mode="0600"),
            _node(nodes, "log", kind="directory", private_directory=True),
            _node(nodes, "login_log", kind="regular", mode="0600"),
            _node(nodes, "tmp", kind="directory", private_directory=True),
            _node(nodes, "arg0", kind="directory", mode="0700"),
            _node(nodes, "session", kind="directory", mode="0755"),
            _node(nodes, "lock", kind="regular", mode="0644"),
            all(
                _node(
                    nodes,
                    name,
                    kind="symlink",
                    mode="0777",
                    target=CODEX_BINARY_TARGET,
                )
                for name in aliases
            ),
        )
    )
    if not valid:
        raise AttestationError("Codex subscription volume metadata is invalid")
    return {
        "inventories": expected_inventories,
        "modes": {name: nodes[name]["mode"] for name in sorted(node_names)},
    }


def _attest(docker: str, volume: str, generation: int, image_id: str) -> dict[str, Any]:
    prefix = [docker, "--context", "colima"]
    metadata = _json(_run([*prefix, "volume", "inspect", volume, "--format", "{{json .}}"]))
    labels = metadata.get("Labels")
    expected = {**EXPECTED_LABELS, "com.glupta.generation": str(generation)}
    invalid_labels = not isinstance(labels, dict) or any(
        labels.get(key) != value for key, value in expected.items()
    )
    if metadata.get("Name") != volume or invalid_labels:
        raise AttestationError("Codex subscription volume identity is invalid")
    observed_image = _run([*prefix, "image", "inspect", image_id, "--format", "{{.Id}}"]).strip()
    if observed_image != image_id:
        raise AttestationError("Codex subscription image identity is invalid")
    probe = _validate_probe(
        _json(
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
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "volume": volume,
        "generation": generation,
        "image_id": image_id,
        **probe,
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
