"""Private, immutable local artifact persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _write_once(root_fd: int, name: str, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        fd = os.open(name, flags, 0o600, dir_fd=root_fd)
    except FileExistsError:
        existing_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            existing = bytearray()
            while len(existing) <= len(data):
                chunk = os.read(existing_fd, min(1024 * 1024, len(data) + 1 - len(existing)))
                if not chunk:
                    break
                existing.extend(chunk)
        finally:
            os.close(existing_fd)
        if bytes(existing) != data:
            raise RuntimeError(f"artifact collision: {name}") from None
        return
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise RuntimeError(f"artifact write failed: {name}")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def persist_artifacts(
    workflow_id: str, artifact_root: str, result: dict[str, Any], markdown: str
) -> None:
    root = Path(artifact_root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(root_fd)
        if metadata.st_mode & 0o077:
            raise RuntimeError("artifact root permissions are not private")
        _write_once(
            root_fd,
            f"{workflow_id}.json",
            (json.dumps(result, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        _write_once(root_fd, f"{workflow_id}.md", markdown.encode("utf-8"))
        os.fsync(root_fd)
    finally:
        os.close(root_fd)
