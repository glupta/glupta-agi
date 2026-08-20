#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from glupta_agi.client import ClientError, submit_walk_artifact
from glupta_agi.contracts import DISCLOSURE_NOTICE_DIGEST
from glupta_agi.intake import IntakeError, load_request
from glupta_agi.walk import DELIVERABLE_TYPES, WALK_FAMILIES, WalkArtifact

MAX_ARTIFACT_BYTES = 512 * 1024


def _artifact_bytes(args: argparse.Namespace) -> bytes:
    if args.ack_external_disclosure is not True:
        raise ValueError("external disclosure acknowledgement is required")
    canonical = load_request(input_root=args.input_root, selected_paths=args.files,
        question=args.question, disclosure_profile="external_disclosed_v1",
        disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
        external_disclosure_ack=True)
    body: dict[str, Any] = {
        "schema_version": "glupta-walk-request-artifact-v1",
        "workflow_family": args.family,
        "question": canonical.question,
        "decision_owner": args.decision_owner,
        "deliverable_type": args.deliverable_type,
        "expected_disposition": args.expected_disposition,
        "disclosure_profile": canonical.disclosure_profile,
        "disclosure_notice_digest": canonical.disclosure_notice_digest,
        "external_disclosure_ack": True,
        "release_profile_digest": args.release_profile_digest,
        "sources": [source.__dict__ for source in canonical.sources],
    }
    artifact = WalkArtifact.model_validate(body)
    return json.dumps(artifact.model_dump(mode="json"), ensure_ascii=False,
        separators=(",", ":"), sort_keys=True).encode()


def artifact_bytes(args: argparse.Namespace) -> bytes:
    error = None
    try:
        raw = _artifact_bytes(args)
    except (IntakeError, ValueError):
        error = "Walk artifact could not be created from the selected input"
    del args
    if error is not None:
        raise ValueError(error) from None
    return raw


def _read_artifact(path: Path, expected_digest: str) -> bytes:
    if (len(expected_digest) != 64
            or any(character not in "0123456789abcdef" for character in expected_digest)):
        raise ValueError("approved Walk artifact digest is invalid")
    file_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(file_fd)
        if (not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode) != 0o600
                or before.st_uid != os.geteuid() or before.st_size > MAX_ARTIFACT_BYTES):
            raise ValueError("Walk artifact file is invalid")
        chunks: list[bytes] = []
        remaining = MAX_ARTIFACT_BYTES + 1
        while remaining:
            chunk = os.read(file_fd, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(file_fd)
        stable = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if len(raw) != before.st_size or any(
                getattr(before, field) != getattr(after, field) for field in stable):
            raise ValueError("Walk artifact changed while being read")
    finally:
        os.close(file_fd)
    if hashlib.sha256(raw).hexdigest() != expected_digest:
        raw = b""
        raise ValueError("Walk artifact does not match its approved digest")
    try:
        WalkArtifact.model_validate_json(raw)
    except ValueError:
        raw = b""
        raise ValueError("Walk artifact is invalid") from None
    return raw


def read_artifact(path: Path, expected_digest: str) -> bytes:
    error, raw = None, b""
    try:
        raw = _read_artifact(path, expected_digest)
    except (OSError, ValueError):
        error = "Walk artifact is unavailable, unsafe, invalid, or does not match approval"
    del path, expected_digest
    if error is not None:
        raw = b""
        raise ValueError(error) from None
    return raw


def write_artifact(path: Path, raw: bytes) -> None:
    file_fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(file_fd, "wb") as output:
            file_fd = -1
            output.write(raw)
    finally:
        if file_fd >= 0:
            os.close(file_fd)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Create, verify, or execute a Glupta Walk artifact")
    commands = root.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("files", nargs="+")
    create.add_argument("--input-root", type=Path, required=True)
    create.add_argument("--question", required=True)
    create.add_argument("--family", choices=WALK_FAMILIES, required=True)
    create.add_argument("--decision-owner", required=True)
    create.add_argument("--deliverable-type", choices=DELIVERABLE_TYPES)
    create.add_argument("--expected-disposition", choices=("PASS", "HOLD"))
    create.add_argument("--release-profile-digest", required=True)
    create.add_argument("--ack-external-disclosure", action="store_true")
    create.add_argument("--output", type=Path, required=True)
    for name in ("verify", "execute"):
        command = commands.add_parser(name)
        command.add_argument("artifact", type=Path)
        command.add_argument("--artifact-sha256", required=True)
        if name == "execute":
            command.add_argument("--endpoint", default="http://127.0.0.1:8765")
            command.add_argument("--token-file", type=Path, default=Path("runtime/intake-token"))
            command.add_argument("--idempotency-key")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "create":
            raw = artifact_bytes(args)
            write_artifact(args.output, raw)
            print(hashlib.sha256(raw).hexdigest())
        else:
            raw = read_artifact(args.artifact, args.artifact_sha256)
            if args.command == "verify":
                print("PASS")
            else:
                result = submit_walk_artifact(raw, args.artifact_sha256, args.endpoint,
                    args.token_file, args.idempotency_key)
                print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ClientError, IntakeError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
