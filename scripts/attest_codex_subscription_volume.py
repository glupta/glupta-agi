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
APP_GID = 65532
MIGRATION_MARKER_SIZE = 3
SCHEMA_VERSION = "glupta-codex-volume-attestation-v4"
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
PRE_USE_ROOT_INVENTORY = ["auth.json", "log", "tmp"]
POST_USE_ROOT_INVENTORY = [
    "auth.json",
    "installation_id",
    "log",
    "models_cache.json",
    "skills",
    "tmp",
]
POST_MIGRATION_ROOT_INVENTORY = [".sandbox_migration", *POST_USE_ROOT_INVENTORY]
EXPECTED_SYSTEM_ROOT_INVENTORY = [".system"]
EXPECTED_SYSTEM_INVENTORY = [
    ".codex-system-skills.marker",
    "imagegen",
    "openai-docs",
    "plugin-creator",
    "review-agent",
    "skill-creator",
    "skill-installer",
]
# Derived twice from Codex 0.147.0 in the exact release image: once from a
# networkless disposable native app-server materialization and once from the
# observed post-use volume. The digest binds every relative path, directory
# inventory, and non-secret regular-file SHA-256 under skills/.system.
EXPECTED_SYSTEM_SKILL_MANIFEST = "cd34b112152e00ddbdfe5e86d99564dc2cfd50947dca6636946670565aeb4f03"
_PROBE_TEMPLATE = """import hashlib, json, os, re, stat
base = '/run/codex'
names = sorted(os.listdir(base))
app_uid = __APP_UID__
app_gid = __APP_GID__
migration_marker_size = __MIGRATION_MARKER_SIZE__
pre_use_root = __PRE_USE_ROOT__
post_use_root = __POST_USE_ROOT__
post_migration_root = __POST_MIGRATION_ROOT__
if names not in (pre_use_root, post_use_root, post_migration_root):
    raise SystemExit(2)
runtime_materialized = names in (post_use_root, post_migration_root)
post_migration = names == post_migration_root
paths = {
    'root': base,
    'auth': base + '/auth.json',
    'log': base + '/log',
    'login_log': base + '/log/codex-login.log',
    'tmp': base + '/tmp',
    'arg0': base + '/tmp/arg0',
}
if runtime_materialized:
    paths.update({
        'installation_id': base + '/installation_id',
        'models_cache': base + '/models_cache.json',
    })
if post_migration:
    paths['sandbox_migration'] = base + '/.sandbox_migration'
stats = {name: os.lstat(path) for name, path in paths.items()}
if not all(stat.S_ISDIR(stats[name].st_mode) for name in ('root', 'log', 'tmp', 'arg0')):
    raise SystemExit(2)
if post_migration:
    migration_marker = stats['sandbox_migration']
    if not all((
        stat.S_ISREG(migration_marker.st_mode),
        migration_marker.st_uid == app_uid,
        migration_marker.st_gid == app_gid,
        stat.S_IMODE(migration_marker.st_mode) == 0o600,
        migration_marker.st_nlink == 1,
        migration_marker.st_size == migration_marker_size,
    )):
        raise SystemExit(2)
inventories = {
    'root': names,
    'log': sorted(os.listdir(paths['log'])),
    'tmp': sorted(os.listdir(paths['tmp'])),
    'arg0': sorted(os.listdir(paths['arg0'])),
}
if runtime_materialized:
    skill_root = base + '/skills'
    if not stat.S_ISDIR(os.lstat(skill_root).st_mode):
        raise SystemExit(2)
    manifest = hashlib.sha256()
    for current, directories, files in os.walk(skill_root, followlinks=False):
        directories.sort()
        files.sort()
        relative = os.path.relpath(current, skill_root)
        key = 'skills' if relative == '.' else 'skills/' + relative
        paths[key] = current
        stats[key] = os.lstat(current)
        inventories[key] = sorted(directories + files)
        manifest.update(b'D\\0' + relative.encode() + b'\\0')
        manifest.update(b'\\0'.join(name.encode() for name in directories + files) + b'\\0')
        if not all(stat.S_ISDIR(os.lstat(current + '/' + name).st_mode) for name in directories):
            raise SystemExit(2)
        for filename in files:
            path = current + '/' + filename
            child = key + '/' + filename
            paths[child] = path
            stats[child] = os.lstat(path)
            if not stat.S_ISREG(stats[child].st_mode) or stats[child].st_nlink != 1:
                raise SystemExit(2)
            content = hashlib.sha256()
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (stats[child].st_dev, stats[child].st_ino):
                os.close(descriptor)
                raise SystemExit(2)
            with os.fdopen(descriptor, 'rb') as stream:
                while chunk := stream.read(65536):
                    content.update(chunk)
            manifest.update(b'F\\0' + os.path.relpath(path, skill_root).encode() + b'\\0')
            manifest.update(content.hexdigest().encode() + b'\\0')
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
def node(value, path, include_size_and_gid=False):
    if stat.S_ISDIR(value.st_mode):
        kind = 'directory'
    elif stat.S_ISREG(value.st_mode):
        kind = 'regular'
    elif stat.S_ISLNK(value.st_mode):
        kind = 'symlink'
    else:
        kind = 'other'
    result = {
        'type': kind, 'uid': value.st_uid,
        'mode': format(stat.S_IMODE(value.st_mode), '04o'), 'nlink': value.st_nlink,
    }
    if include_size_and_gid:
        result['gid'] = value.st_gid
        result['size'] = value.st_size
    if kind == 'symlink':
        result['target'] = os.readlink(path)
    return result
node_paths = {**paths, 'session': session_path}
node_paths.update({key: session_path + '/' + filename for key, filename in helper_names.items()})
print(json.dumps({
    'session_name': session_name,
    'inventories': inventories,
    'nodes': {
        name: node(value, node_paths[name], name == 'sandbox_migration')
        for name, value in stats.items()
    },
    'system_skill_manifest': manifest.hexdigest() if runtime_materialized else None,
}, sort_keys=True))
"""
PROBE = (
    _PROBE_TEMPLATE.replace("__APP_UID__", repr(APP_UID))
    .replace("__APP_GID__", repr(APP_GID))
    .replace("__MIGRATION_MARKER_SIZE__", repr(MIGRATION_MARKER_SIZE))
    .replace("__PRE_USE_ROOT__", repr(PRE_USE_ROOT_INVENTORY))
    .replace("__POST_USE_ROOT__", repr(POST_USE_ROOT_INVENTORY))
    .replace("__POST_MIGRATION_ROOT__", repr(POST_MIGRATION_ROOT_INVENTORY))
)


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
    nlink: int,
    mode: str | None = None,
    private_directory: bool = False,
    target: str | None = None,
) -> bool:
    if not isinstance(nodes, dict) or not isinstance(nodes.get(name), dict):
        return False
    value = nodes[name]
    expected_keys = {"type", "uid", "mode", "nlink"}
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
            type(value.get("nlink")) is int,
            value.get("nlink") == nlink,
            target is None or value.get("target") == target,
        )
    )


def _migration_marker_node(nodes: object) -> bool:
    if not isinstance(nodes, dict) or not isinstance(nodes.get("sandbox_migration"), dict):
        return False
    value = nodes["sandbox_migration"]
    return all(
        (
            set(value) == {"type", "uid", "gid", "mode", "nlink", "size"},
            value.get("type") == "regular",
            type(value.get("uid")) is int,
            value.get("uid") == APP_UID,
            type(value.get("gid")) is int,
            value.get("gid") == APP_GID,
            value.get("mode") == "0600",
            type(value.get("nlink")) is int,
            value.get("nlink") == 1,
            type(value.get("size")) is int,
            value.get("size") == MIGRATION_MARKER_SIZE,
        )
    )


def _validate_probe(probe: dict[str, Any]) -> dict[str, Any]:
    session_name = probe.get("session_name")
    inventories = probe.get("inventories")
    nodes = probe.get("nodes")
    system_skill_manifest = probe.get("system_skill_manifest")
    common_inventories = {
        "log": ["codex-login.log"],
        "tmp": ["arg0"],
        "arg0": [session_name],
        "session": EXPECTED_SESSION_INVENTORY,
    }
    if isinstance(inventories, dict) and inventories.get("root") == PRE_USE_ROOT_INVENTORY:
        layout = "completed-login"
        expected_inventories = {"root": PRE_USE_ROOT_INVENTORY, **common_inventories}
        root_nlink = 4
        skill_directories: set[str] = set()
        skill_files: set[str] = set()
    elif isinstance(inventories, dict) and inventories.get("root") in (
        POST_USE_ROOT_INVENTORY,
        POST_MIGRATION_ROOT_INVENTORY,
    ):
        post_migration = inventories.get("root") == POST_MIGRATION_ROOT_INVENTORY
        layout = "post-migration" if post_migration else "post-use"
        root_nlink = 5
        skill_inventories = {
            name: inventory for name, inventory in inventories.items() if name.startswith("skills")
        }
        skill_directories = set(skill_inventories)
        valid_skill_names = all(
            isinstance(inventory, list)
            and all(
                isinstance(name, str) and name not in {"", ".", ".."} and "/" not in name
                for name in inventory
            )
            and inventory == sorted(inventory)
            and len(inventory) == len(set(inventory))
            for inventory in skill_inventories.values()
        )
        discovered = {
            f"{directory}/{name}"
            for directory, inventory in skill_inventories.items()
            for name in inventory
        }
        reachable_directories = {"skills"} | {
            name for name in discovered if name in skill_directories
        }
        skill_files = discovered - skill_directories
        expected_system_directories = {
            f"skills/.system/{name}"
            for name in EXPECTED_SYSTEM_INVENTORY
            if name != ".codex-system-skills.marker"
        }
        valid_skill_tree = all(
            (
                valid_skill_names,
                skill_inventories.get("skills") == EXPECTED_SYSTEM_ROOT_INVENTORY,
                skill_inventories.get("skills/.system") == EXPECTED_SYSTEM_INVENTORY,
                skill_directories == reachable_directories,
                expected_system_directories <= skill_directories,
                "skills/.system/.codex-system-skills.marker" in skill_files,
                system_skill_manifest == EXPECTED_SYSTEM_SKILL_MANIFEST,
            )
        )
        if not valid_skill_tree:
            raise AttestationError("Codex subscription volume metadata is invalid")
        expected_inventories = {
            "root": POST_MIGRATION_ROOT_INVENTORY if post_migration else POST_USE_ROOT_INVENTORY,
            **common_inventories,
            **skill_inventories,
        }
    else:
        raise AttestationError("Codex subscription volume metadata is invalid")
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
    runtime_materialized = layout in {"post-use", "post-migration"}
    if runtime_materialized:
        node_names.update(
            {
                "installation_id",
                "models_cache",
                *skill_directories,
                *skill_files,
            }
        )
    if layout == "post-migration":
        node_names.add("sandbox_migration")
    valid = all(
        (
            set(probe) == {"session_name", "inventories", "nodes", "system_skill_manifest"},
            runtime_materialized == isinstance(system_skill_manifest, str),
            isinstance(session_name, str),
            isinstance(session_name, str) and SESSION_PATTERN.fullmatch(session_name) is not None,
            inventories == expected_inventories,
            isinstance(nodes, dict) and set(nodes) == node_names,
            _node(nodes, "root", kind="directory", mode="0700", nlink=root_nlink),
            _node(nodes, "auth", kind="regular", mode="0600", nlink=1),
            _node(nodes, "log", kind="directory", nlink=2, private_directory=True),
            _node(nodes, "login_log", kind="regular", mode="0600", nlink=1),
            _node(nodes, "tmp", kind="directory", nlink=3, private_directory=True),
            _node(nodes, "arg0", kind="directory", mode="0700", nlink=3),
            _node(nodes, "session", kind="directory", mode="0755", nlink=2),
            _node(nodes, "lock", kind="regular", mode="0644", nlink=1),
            all(
                _node(
                    nodes,
                    name,
                    kind="symlink",
                    mode="0777",
                    nlink=1,
                    target=CODEX_BINARY_TARGET,
                )
                for name in aliases
            ),
            not runtime_materialized
            or all(
                (
                    _node(nodes, "installation_id", kind="regular", mode="0644", nlink=1),
                    _node(nodes, "models_cache", kind="regular", mode="0644", nlink=1),
                    all(
                        _node(
                            nodes,
                            name,
                            kind="directory",
                            mode="0755",
                            nlink=2
                            + sum(
                                f"{name}/{child}" in skill_directories
                                for child in expected_inventories[name]
                            ),
                        )
                        for name in skill_directories
                    ),
                    all(
                        _node(nodes, name, kind="regular", mode="0644", nlink=1)
                        for name in skill_files
                    ),
                )
            ),
            layout != "post-migration" or _migration_marker_node(nodes),
        )
    )
    if not valid:
        raise AttestationError("Codex subscription volume metadata is invalid")
    result = {
        "layout": layout,
        "inventories": expected_inventories,
        "modes": {name: nodes[name]["mode"] for name in sorted(node_names)},
    }
    if runtime_materialized:
        result["system_skill_manifest"] = system_skill_manifest
    return result


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
                    f"{APP_UID}:{APP_GID}",
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
