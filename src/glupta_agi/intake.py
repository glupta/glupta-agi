"""Fail-closed intake for explicitly selected local text files."""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from .contracts import DISCLOSURE_NOTICE_DIGEST, canonical_digest

MAX_FILES, MAX_TOTAL_BYTES = 20, 256 * 1024
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
    disclosure_profile: str
    disclosure_notice_digest: str
    external_disclosure_ack: bool
    sources: tuple[SourceDocument, ...]
    request_digest: str

    def workflow_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["sources"] = list(payload["sources"])
        return payload

    def matches_recorded_payload(self, recorded: object) -> bool:
        return recorded == self.workflow_payload()


def _canonical_request(
    question: str, sources: tuple[SourceDocument, ...], disclosure_profile: str,
    disclosure_notice_digest: str, external_disclosure_ack: bool,
) -> CanonicalRequest:
    if not isinstance(question, str):
        raise IntakeError("question is invalid")
    if disclosure_profile != "external_disclosed_v1":
        raise IntakeError("unsupported disclosure profile")
    if disclosure_notice_digest != DISCLOSURE_NOTICE_DIGEST or external_disclosure_ack is not True:
        raise IntakeError("external disclosure acknowledgement is invalid")
    normalized = question.strip()
    if not normalized or len(normalized.encode()) > 32 * 1024:
        raise IntakeError("question must contain between 1 and 32768 UTF-8 bytes")
    if not sources or len(sources) > MAX_FILES or len({item.path for item in sources}) != len(sources):  # noqa: E501
        raise IntakeError(f"select between 1 and {MAX_FILES} unique source files")
    total = 0
    for source in sources:
        _validate_relative_path(source.path)
        encoded = source.content.encode()
        total += len(encoded)
        if (type(source.byte_size) is not int or source.byte_size != len(encoded)
                or source.sha256 != hashlib.sha256(encoded).hexdigest()
                or total > MAX_TOTAL_BYTES):
            raise IntakeError("source metadata or total bytes are invalid")
    digest_payload = {"question": normalized, "disclosure_profile": disclosure_profile,
        "disclosure_notice_digest": disclosure_notice_digest,
        "external_disclosure_ack": external_disclosure_ack,
        "sources": [{"path": item.path, "sha256": item.sha256, "byte_size": item.byte_size}
                    for item in sources],
    }
    return CanonicalRequest(question=normalized, disclosure_profile=disclosure_profile,
                            disclosure_notice_digest=disclosure_notice_digest,
                            external_disclosure_ack=external_disclosure_ack, sources=sources,
                            request_digest=canonical_digest(digest_payload))


def admit_inline_request(
    *, question: str, sources: Iterable[dict[str, object]], disclosure_profile: str,
    disclosure_notice_digest: str, external_disclosure_ack: bool,
) -> CanonicalRequest:
    documents: list[SourceDocument] = []
    for source in sources:
        if set(source) != {"path", "content"} or not all(
                isinstance(source[name], str) for name in ("path", "content")):
            raise IntakeError("inline source is invalid")
        content, path = str(source["content"]), str(source["path"])
        encoded = content.encode()
        documents.append(SourceDocument(path, hashlib.sha256(encoded).hexdigest(),
                                        len(encoded), content))
    return _canonical_request(question, tuple(documents), disclosure_profile,
                              disclosure_notice_digest, external_disclosure_ack)


def validate_workflow_payload(payload: object) -> CanonicalRequest:
    expected = {"question", "disclosure_profile", "disclosure_notice_digest",
                "external_disclosure_ack", "sources", "request_digest"}
    if (not isinstance(payload, dict) or set(payload) != expected
            or not isinstance(payload["sources"], list)):
        raise IntakeError("admitted request payload is invalid")
    invalid_payload = False
    try:
        sources = tuple(SourceDocument(**item) for item in payload["sources"])
        canonical = _canonical_request(payload["question"], sources, payload["disclosure_profile"],
                                       payload["disclosure_notice_digest"],
                                       payload["external_disclosure_ack"])
    except (AttributeError, KeyError, TypeError, UnicodeError):
        invalid_payload = True
    if invalid_payload:
        raise IntakeError("admitted request payload is invalid") from None
    if payload["request_digest"] != canonical.request_digest:
        raise IntakeError("admitted request digest is invalid")
    return canonical


def _validate_relative_path(raw: str) -> tuple[str, ...]:
    if (not isinstance(raw, str) or not raw or "\\" in raw
            or any(ord(character) < 32 or ord(character) == 127 for character in raw)):
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
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=directory_fd)
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
            if len(data) != before.st_size or any(getattr(before, field) != getattr(after, field)
                                                  for field in stable_fields):
                raise IntakeError("source changed while being read")
            return data
        finally:
            os.close(file_fd)
    except OSError:
        raise IntakeError("source path is missing, inaccessible, or not a regular file") from None
    finally:
        os.close(directory_fd)


def load_request(
    *, input_root: Path, question: str, selected_paths: Iterable[str],
    disclosure_profile: str = "external_disclosed_v1",
    disclosure_notice_digest: str = DISCLOSURE_NOTICE_DIGEST,
    external_disclosure_ack: bool = True,
) -> CanonicalRequest:
    paths = tuple(selected_paths)
    if not paths or len(paths) > MAX_FILES:
        raise IntakeError(f"select between 1 and {MAX_FILES} source files")
    if len(set(paths)) != len(paths):
        raise IntakeError("duplicate source paths are not permitted")

    try:
        root_fd = os.open(input_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise IntakeError("input root is unavailable or unsafe") from None

    total = 0
    sources: list[SourceDocument] = []
    try:
        for raw_path in paths:
            parts = _validate_relative_path(raw_path)
            data = _read_regular_file(root_fd, parts)
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise IntakeError("selected sources exceed 256 KiB")
            invalid_encoding = False
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError:
                invalid_encoding = True
            if invalid_encoding:
                raise IntakeError(f"source is not valid UTF-8: {raw_path}") from None
            sources.append(SourceDocument(path=raw_path,
                sha256=hashlib.sha256(data).hexdigest(), byte_size=len(data), content=content))
    finally:
        os.close(root_fd)

    return _canonical_request(question, tuple(sources), disclosure_profile,
                              disclosure_notice_digest, external_disclosure_ack)
