"""Fail-closed intake for explicitly selected local text files."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

MAX_FILES = 20
MAX_TOTAL_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = {".md", ".txt"}


class IntakeError(ValueError):
    """The request does not satisfy the frozen Crawl intake contract."""


@dataclass(frozen=True)
class SourceDocument:
    path: str
    sha256: str
    byte_size: int
    content: str

    @property
    def lines(self) -> tuple[str, ...]:
        return tuple(self.content.splitlines())


@dataclass(frozen=True)
class CanonicalRequest:
    question: str
    sources: tuple[SourceDocument, ...]
    request_digest: str
    write_artifacts: bool

    def workflow_payload(self) -> dict[str, object]:
        return {
            "question": self.question,
            "sources": [asdict(source) for source in self.sources],
            "request_digest": self.request_digest,
            "write_artifacts": self.write_artifacts,
        }


def _validate_relative_path(raw: str) -> tuple[str, ...]:
    if not raw or "\\" in raw or any(ord(character) < 32 or ord(character) == 127 for character in raw):
        raise IntakeError("source path is invalid")
    if "://" in raw:
        raise IntakeError("URLs are not permitted")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise IntakeError("source path must be a normalized relative path")
    if any(part.startswith(".") for part in path.parts):
        raise IntakeError("hidden paths are not permitted")
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise IntakeError("only .md and .txt sources are permitted")
    normalized = path.as_posix()
    if normalized != raw:
        raise IntakeError("source path must use canonical POSIX spelling")
    return path.parts


def _read_regular_file(root_fd: int, parts: tuple[str, ...]) -> bytes:
    directory_fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            next_fd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        try:
            before = os.fstat(file_fd)
            if not stat.S_ISREG(before.st_mode):
                raise IntakeError("source must be a regular file")
            if before.st_size > MAX_TOTAL_BYTES:
                raise IntakeError("source exceeds the total request byte limit")
            chunks: list[bytes] = []
            remaining = MAX_TOTAL_BYTES + 1
            while remaining:
                chunk = os.read(file_fd, min(1024 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            after = os.fstat(file_fd)
            stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
            if len(data) != before.st_size or any(
                getattr(before, field) != getattr(after, field) for field in stable_fields
            ):
                raise IntakeError("source changed while being read")
            return data
        finally:
            os.close(file_fd)
    except OSError as exc:
        raise IntakeError("source path is missing, inaccessible, or not a regular file") from exc
    finally:
        os.close(directory_fd)


def load_request(
    *,
    input_root: Path,
    question: str,
    selected_paths: Iterable[str],
    write_artifacts: bool = False,
) -> CanonicalRequest:
    normalized_question = question.strip()
    if not normalized_question:
        raise IntakeError("question must not be empty")
    if len(normalized_question.encode("utf-8")) > 32 * 1024:
        raise IntakeError("question is too large")

    paths = tuple(selected_paths)
    if not paths or len(paths) > MAX_FILES:
        raise IntakeError(f"select between 1 and {MAX_FILES} source files")
    if len(set(paths)) != len(paths):
        raise IntakeError("duplicate source paths are not permitted")

    try:
        root_fd = os.open(input_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise IntakeError("input root is unavailable or unsafe") from exc

    total = 0
    sources: list[SourceDocument] = []
    try:
        for raw_path in paths:
            parts = _validate_relative_path(raw_path)
            data = _read_regular_file(root_fd, parts)
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise IntakeError("selected sources exceed 10 MiB")
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise IntakeError(f"source is not valid UTF-8: {raw_path}") from exc
            sources.append(
                SourceDocument(
                    path=raw_path,
                    sha256=hashlib.sha256(data).hexdigest(),
                    byte_size=len(data),
                    content=content,
                )
            )
    finally:
        os.close(root_fd)

    digest_payload = {
        "question": normalized_question,
        "sources": [
            {"path": item.path, "sha256": item.sha256, "byte_size": item.byte_size}
            for item in sources
        ],
        "write_artifacts": bool(write_artifacts),
    }
    encoded = json.dumps(
        digest_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return CanonicalRequest(
        question=normalized_question,
        sources=tuple(sources),
        request_digest=hashlib.sha256(encoded).hexdigest(),
        write_artifacts=bool(write_artifacts),
    )
