#!/usr/bin/env python3
"""Create, verify, and execute path-bound Crawl approval requests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from glupta_agi.client import ClientError, submit_inline
from glupta_agi.intake import CanonicalRequest, IntakeError, _validate_relative_path, load_request

SCHEMA = "glupta_crawl_request_v2"
PURPOSES = {"canary", "conditional_drain"}
MAX_ARTIFACT_BYTES = 64 * 1024


class RequestPreflightError(ValueError):
    pass


def _source_parts(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, str):
        raise RequestPreflightError("request path is invalid")
    try:
        return _validate_relative_path(raw)
    except IntakeError:
        raise RequestPreflightError("request path is invalid") from None


def _input_root_dir(raw: object) -> str:
    if not isinstance(raw, str):
        raise RequestPreflightError("input_root_dir is invalid")
    path = PurePosixPath(raw)
    if (len(path.parts) != 1 or path.parts[0] in {"", ".", ".."}
            or path.parts[0].startswith(".") or path.as_posix() != raw):
        raise RequestPreflightError("input_root_dir must be one canonical directory name")
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        raise RequestPreflightError("input_root_dir is invalid")
    return raw


def _preflight_artifact(artifact: object, repo_root: Path) -> CanonicalRequest:
    expected = {
        "schema", "purpose", "question", "input_root_dir", "sources",
        "external_disclosure_ack",
    }
    if (not isinstance(artifact, dict) or set(artifact) != expected
            or artifact.get("schema") != SCHEMA or artifact.get("purpose") not in PURPOSES
            or artifact.get("external_disclosure_ack") is not True
            or not isinstance(artifact.get("question"), str)
            or not isinstance(artifact.get("sources"), list)):
        raise RequestPreflightError("approval artifact is not a canonical v2 request")
    input_root_dir = _input_root_dir(artifact["input_root_dir"])
    sources = artifact["sources"]
    if not sources or len(sources) > 20:
        raise RequestPreflightError("approval artifact must bind between 1 and 20 sources")
    selected: list[str] = []
    expected_sha256: list[str] = []
    for source in sources:
        if not isinstance(source, dict) or set(source) != {
            "repo_path", "client_selected_path", "sha256"
        }:
            raise RequestPreflightError("approved source binding is invalid")
        client_parts = _source_parts(source["client_selected_path"])
        expected_repo = PurePosixPath(input_root_dir, *client_parts).as_posix()
        if source["repo_path"] != expected_repo:
            raise RequestPreflightError(
                "repo_path must equal input_root_dir/client_selected_path"
            )
        digest = source["sha256"]
        if (not isinstance(digest, str) or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)):
            raise RequestPreflightError("approved source SHA-256 is invalid")
        selected.append(source["client_selected_path"])
        expected_sha256.append(digest)
    if artifact["question"] != artifact["question"].strip():
        raise RequestPreflightError("approved question must use canonical whitespace")
    try:
        canonical = load_request(
            input_root=repo_root / input_root_dir,
            question=artifact["question"],
            selected_paths=selected,
        )
    except IntakeError as exc:
        raise RequestPreflightError(str(exc)) from None
    if tuple(source.sha256 for source in canonical.sources) != tuple(expected_sha256):
        raise RequestPreflightError("approved source SHA-256 changed")
    return canonical


def _artifact_bytes(path: Path) -> bytes:
    try:
        with path.open("rb") as artifact_file:
            raw = artifact_file.read(MAX_ARTIFACT_BYTES + 1)
    except OSError:
        raise RequestPreflightError("approval artifact is unavailable or invalid") from None
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise RequestPreflightError("approval artifact exceeds 64 KiB")
    return raw


def _verified_artifact(
    artifact_bytes: bytes, repo_root: Path, expected_artifact_sha256: str,
) -> CanonicalRequest:
    if (not isinstance(expected_artifact_sha256, str)
            or len(expected_artifact_sha256) != 64
            or any(character not in "0123456789abcdef"
                   for character in expected_artifact_sha256)):
        raise RequestPreflightError("approved artifact SHA-256 is invalid")
    if not isinstance(artifact_bytes, bytes):
        raise RequestPreflightError("approval artifact is unavailable or invalid")
    if len(artifact_bytes) > MAX_ARTIFACT_BYTES:
        raise RequestPreflightError("approval artifact exceeds 64 KiB")
    if hashlib.sha256(artifact_bytes).hexdigest() != expected_artifact_sha256:
        raise RequestPreflightError("approval artifact SHA-256 changed")
    try:
        artifact = json.loads(artifact_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RequestPreflightError("approval artifact is unavailable or invalid") from None
    return _preflight_artifact(artifact, repo_root)


def verify_artifact(
    artifact_bytes: bytes, repo_root: Path, expected_artifact_sha256: str,
) -> CanonicalRequest:
    failure = None
    try:
        canonical = _verified_artifact(artifact_bytes, repo_root, expected_artifact_sha256)
    except RequestPreflightError as exc:
        failure = str(exc)
    del artifact_bytes
    if failure is not None:
        raise RequestPreflightError(failure) from None
    return canonical


def create_artifact(
    *, repo_root: Path, input_root_dir: str, repo_paths: Sequence[str], question: str,
    purpose: str,
) -> dict[str, Any]:
    root_name = _input_root_dir(input_root_dir)
    selected: list[str] = []
    for repo_path in repo_paths:
        repo_parts = _source_parts(repo_path)
        if repo_parts[0] != root_name or len(repo_parts) == 1:
            raise RequestPreflightError("repo_path must be below input_root_dir")
        selected.append(PurePosixPath(*repo_parts[1:]).as_posix())
    try:
        canonical = load_request(
            input_root=repo_root / root_name, question=question, selected_paths=selected
        )
    except IntakeError as exc:
        raise RequestPreflightError(str(exc)) from None
    sources = [{
        "repo_path": repo_path,
        "client_selected_path": source.path,
        "sha256": source.sha256,
    } for repo_path, source in zip(repo_paths, canonical.sources, strict=True)]
    artifact = {
        "schema": SCHEMA,
        "purpose": purpose,
        "question": question.strip(),
        "input_root_dir": input_root_dir,
        "sources": sources,
        "external_disclosure_ack": True,
    }
    _preflight_artifact(artifact, repo_root)
    return artifact


def execute_artifact(
    artifact_bytes: bytes, repo_root: Path, expected_artifact_sha256: str,
    endpoint: str, token_file: Path, idempotency_key: str | None,
) -> dict[str, Any]:
    preflight_error = None
    try:
        canonical = verify_artifact(artifact_bytes, repo_root, expected_artifact_sha256)
    except RequestPreflightError as exc:
        preflight_error = str(exc)
    del artifact_bytes
    if preflight_error is not None:
        raise RequestPreflightError(preflight_error) from None
    result, client_error = None, None
    try:
        result = submit_inline(canonical, endpoint, token_file, idempotency_key)
    except ClientError as exc:
        client_error = str(exc)
    del canonical
    if client_error is not None:
        raise ClientError(client_error) from None
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("repo_paths", nargs="+")
    create.add_argument("--repo-root", type=Path, default=Path("."))
    create.add_argument("--input-root-dir", default="inputs")
    create.add_argument("--question", required=True)
    create.add_argument("--purpose", choices=sorted(PURPOSES), required=True)
    for command in ("verify", "execute"):
        selected = subparsers.add_parser(command)
        selected.add_argument("artifact", type=Path)
        selected.add_argument("--artifact-sha256", required=True)
        selected.add_argument("--repo-root", type=Path, default=Path("."))
        if command == "execute":
            selected.add_argument("--endpoint", default="http://127.0.0.1:8765")
            selected.add_argument("--token-file", type=Path, default=Path("runtime/intake-token"))
            selected.add_argument("--idempotency-key")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            result = create_artifact(
                repo_root=args.repo_root, input_root_dir=args.input_root_dir,
                repo_paths=args.repo_paths, question=args.question, purpose=args.purpose,
            )
        else:
            artifact_bytes = _artifact_bytes(args.artifact)
            if args.command == "verify":
                canonical = verify_artifact(
                    artifact_bytes, args.repo_root, args.artifact_sha256
                )
                result = {"schema": SCHEMA, "question": canonical.question,
                          "files": [source.path for source in canonical.sources]}
            else:
                result = execute_artifact(
                    artifact_bytes, args.repo_root, args.artifact_sha256, args.endpoint,
                    args.token_file, args.idempotency_key,
                )
    except (RequestPreflightError, ClientError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
