"""Stage one immutable synthetic or broker-provided Compose secret bundle."""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import tarfile
import uuid

STAGER_IMAGE = (
    "cgr.dev/chainguard/python:latest-dev@sha256:"
    "91418fa26adfd56d959d80e5da0d7470b5653e4f00ba698ef5d8212e58e3f7f8"
)
APP_FILES = {
    "intake-token": ("GLUPTA_INTAKE_TOKEN", 32, 4096),
    "postgres-password": ("GLUPTA_POSTGRES_PASSWORD", 1, 512),
    "release-profile.json": ("GLUPTA_RELEASE_PROFILE_JSON", 1, 32768),
}


class StagingError(RuntimeError):
    pass


def _docker_environment() -> dict[str, str]:
    allowed = ("HOME", "PATH", "DOCKER_CONFIG", "DOCKER_CONTEXT", "DOCKER_HOST")
    return {name: os.environ[name] for name in allowed if name in os.environ}


def _bundle(files: dict[str, str], uid: int) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, value in sorted(files.items()):
            payload = value.encode("utf-8")
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode, entry.uid, entry.gid = len(payload), 0o600, uid, uid
            entry.mtime = 0
            archive.addfile(entry, io.BytesIO(payload))
    return output.getvalue()


def _run(arguments: list[str], *, payload: bytes | None = None) -> None:
    completed = subprocess.run(  # noqa: S603
        arguments, input=payload, capture_output=True, check=False, env=_docker_environment()
    )
    if completed.returncode:
        raise StagingError("Docker private-volume staging failed")


def _stage(docker: str, volume: str, purpose: str, payload: bytes, generation: int) -> None:
    _run(
        [
            docker,
            "volume",
            "create",
            "--label",
            "com.glupta.private=true",
            "--label",
            f"com.glupta.purpose={purpose}",
            "--label",
            f"com.glupta.generation={generation}",
            volume,
        ]
    )
    try:
        _run(
            [
                docker,
                "run",
                "--rm",
                "--interactive",
                "--network",
                "none",
                "--security-opt",
                "no-new-privileges:true",
                "--cap-drop",
                "ALL",
                "--cap-add",
                "CHOWN",
                "--user",
                "0:0",
                "--mount",
                f"type=volume,src={volume},dst=/target",
                "--entrypoint",
                "/usr/bin/tar",
                STAGER_IMAGE,
                "-x",
                "-f",
                "-",
                "-C",
                "/target",
            ],
            payload=payload,
        )
    except StagingError:
        _run([docker, "volume", "rm", volume])
        raise


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-only", action="store_true")
    options = parser.parse_args(argv)
    try:
        raw_generation = os.environ["GLUPTA_AUTH_GENERATION"]
        generation = int(raw_generation)
        if generation < 1 or str(generation) != raw_generation:
            raise ValueError
        files = {name: os.environ[source] for name, (source, _, _) in APP_FILES.items()}
        if any(
            not minimum <= len(files[name].encode()) <= maximum
            for name, (_, minimum, maximum) in APP_FILES.items()
        ):
            raise ValueError
    except (KeyError, ValueError):
        raise StagingError("private bundle inputs are missing or invalid") from None
    docker = shutil.which("docker")
    if docker is None:
        raise StagingError("Docker CLI is unavailable")
    suffix = uuid.uuid4().hex
    app_volume = f"glupta-app-private-g{generation}-{suffix}"
    postgres_volume = (
        None if options.app_only else f"glupta-postgres-private-g{generation}-{suffix}"
    )
    staged: list[str] = []
    try:
        _stage(docker, app_volume, "app", _bundle(files, 65532), generation)
        staged.append(app_volume)
        if postgres_volume is not None:
            _stage(
                docker,
                postgres_volume,
                "postgres",
                _bundle({"postgres-password": files["postgres-password"]}, 999),
                generation,
            )
            staged.append(postgres_volume)
    except StagingError:
        for volume in staged:
            _run([docker, "volume", "rm", volume])
        raise
    print(
        json.dumps(
            {
                "generation": generation,
                "app_volume": app_volume,
                "postgres_volume": postgres_volume,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
