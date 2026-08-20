from __future__ import annotations

import argparse
import http.client
import json
import os
import secrets
import stat
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .contracts import DISCLOSURE_NOTICE_DIGEST, EvidenceBriefResponse
from .intake import CanonicalRequest, IntakeError, _validate_relative_path

MAX_RESPONSE_BYTES, REQUEST_TIMEOUT_SECONDS = 2 * 1024 * 1024, 330


class ClientError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        raise ClientError("server redirect rejected")


def _validate_token_metadata(metadata: os.stat_result | Any) -> None:
    if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.geteuid() or not 32 <= metadata.st_size <= 4096):
        raise ClientError("intake capability file must be owned, regular, and mode 0600")


def _read_capability(path: Path) -> str:
    file_fd, unavailable = -1, False
    try:
        file_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        _validate_token_metadata(os.fstat(file_fd))
        with os.fdopen(file_fd, encoding="utf-8") as capability_file:
            file_fd = -1
            capability = capability_file.read(4097).strip()
    except (OSError, UnicodeError):
        unavailable = True
    finally:
        if file_fd >= 0:
            os.close(file_fd)
    if unavailable:
        raise ClientError("intake capability file is unavailable or invalid") from None
    if not 32 <= len(capability.encode()) <= 4096:
        raise ClientError("intake capability length is invalid")
    return capability


def _validate_endpoint(raw: str) -> str:
    try:
        parsed = urlsplit(raw)
        _ = parsed.port
    except ValueError:
        raise ClientError("endpoint must be an HTTP loopback URL") from None
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ClientError("endpoint must be an HTTP loopback URL")
    return raw.rstrip("/")


def _uuid7() -> str:
    timestamp = (time.time_ns() // 1_000_000) & ((1 << 48) - 1)
    value = (timestamp << 80) | (0x7 << 76) | (secrets.randbits(12) << 64)
    value |= (0b10 << 62) | secrets.randbits(62)
    return str(uuid.UUID(int=value))


def _workflow_id(raw: str | None) -> str:
    candidate = raw or _uuid7()
    try:
        parsed = uuid.UUID(candidate)
    except (AttributeError, ValueError):
        raise ClientError("idempotency key must be a canonical lowercase UUIDv7") from None
    if parsed.version != 7 or str(parsed) != candidate:
        raise ClientError("idempotency key must be a canonical lowercase UUIDv7")
    return candidate


def _disclosure_payload(question: str, selection: dict[str, object]) -> bytes:
    body = {
        "question": question, **selection,
        "disclosure_profile": "external_disclosed_v1",
        "disclosure_notice_digest": DISCLOSURE_NOTICE_DIGEST,
        "external_disclosure_ack": True,
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()


def _request_payload(question: str, files: Sequence[str], *, ack: bool) -> bytes:
    if not ack:
        raise ClientError("external disclosure acknowledgement is required")
    normalized_question = question.strip()
    if not normalized_question or len(normalized_question.encode()) > 32 * 1024:
        raise ClientError("question must contain between 1 and 32768 UTF-8 bytes")
    if not files or len(files) > 20 or len(set(files)) != len(files):
        raise ClientError("select between 1 and 20 unique source files")
    try:
        for path in files:
            _validate_relative_path(path)
    except IntakeError as exc:
        raise ClientError(str(exc)) from None
    return _disclosure_payload(normalized_question, {"files": list(files)})


def _submit_payload(payload: bytes, endpoint: str, token_file: Path,
                    idempotency_key: str | None,
                    opener: Callable[..., Any] | None) -> dict[str, Any]:
    base_url = _validate_endpoint(endpoint)
    workflow_id = _workflow_id(idempotency_key)
    capability = _read_capability(token_file)
    headers = {"Authorization": f"Bearer {capability}", "Content-Type": "application/json",
               "Idempotency-Key": workflow_id}
    request = urllib.request.Request(  # noqa: S310 -- URL is validated loopback HTTP
        f"{base_url}/v1/evidence-brief", data=payload, headers=headers, method="POST")
    failure = None
    try:
        open_request = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()).open
        with open_request(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        failure = f"server returned HTTP {exc.code} for workflow {workflow_id}"
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError):
        failure = "Crawl API is unavailable"
    del payload, capability, headers, request, open_request
    if failure is not None:
        raise ClientError(failure) from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise ClientError("server response exceeds the client limit")
    invalid_response = False
    try:
        result = EvidenceBriefResponse.model_validate_json(body)
    except ValueError:
        invalid_response = True
    if invalid_response:
        raise ClientError("server returned an invalid evidence brief") from None
    if result.workflow_id != workflow_id:
        raise ClientError("server returned a mismatched workflow result")
    return result.model_dump(mode="json")


def submit(question: str, files: Sequence[str], endpoint: str, token_file: Path,
           idempotency_key: str | None = None, *, external_disclosure_ack: bool = False,
           opener: Callable[..., Any] | None = None) -> dict[str, Any]:
    payload = _request_payload(question, files, ack=external_disclosure_ack)
    return _submit_payload(payload, endpoint, token_file, idempotency_key, opener)


def submit_inline(canonical: CanonicalRequest, endpoint: str, token_file: Path,
                  idempotency_key: str | None = None, *,
                  opener: Callable[..., Any] | None = None) -> dict[str, Any]:
    sources = [{"path": source.path, "content": source.content} for source in canonical.sources]
    payload = _disclosure_payload(canonical.question, {"sources": sources})
    error = None
    try:
        result = _submit_payload(payload, endpoint, token_file, idempotency_key, opener)
    except ClientError as exc:
        error = str(exc)
    del canonical, sources, payload
    if error is not None:
        raise ClientError(error) from None
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit a read-only Crawl evidence brief")
    parser.add_argument("files", metavar="FILE", nargs="+")
    parser.add_argument("--question", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8765")
    parser.add_argument("--token-file", type=Path, default=Path("runtime/intake-token"))
    parser.add_argument("--idempotency-key")
    parser.add_argument("--ack-external-disclosure", action="store_true",
                        help="acknowledge that selected source bytes and question are sent to OpenAI")  # noqa: E501
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = submit(
            args.question,
            args.files,
            args.endpoint,
            args.token_file,
            args.idempotency_key,
            external_disclosure_ack=args.ack_external_disclosure,
        )
    except ClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["markdown"], end="" if result["markdown"].endswith("\n") else "\n")
    return 0
