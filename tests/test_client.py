from __future__ import annotations

import http.client
import io
import json
import os
import stat
import tempfile
import threading
import traceback
import unittest
import urllib.error
import uuid
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from glupta_agi.client import (
    MAX_RESPONSE_BYTES,
    ClientError,
    _NoRedirect,
    _validate_endpoint,
    _validate_token_metadata,
    main,
    submit,
    submit_inline,
)
from glupta_agi.contracts import DISCLOSURE_NOTICE_DIGEST, EvidenceBrief
from glupta_agi.intake import admit_inline_request
from tests.helpers import provider_audit


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


def _assert_client_trace_sanitized(
    case: unittest.TestCase, error: BaseException, expected_frames: list[str], *markers: str,
) -> None:
    case.assertIsNone(error.__cause__)
    case.assertIsNone(error.__context__)
    captured = traceback.TracebackException.from_exception(error, capture_locals=True)
    product_frames: list[str] = []
    cursor = error.__traceback__
    while cursor is not None:
        frame = cursor.tb_frame
        if "/src/glupta_agi/" in frame.f_code.co_filename:
            product_frames.append(frame.f_code.co_name)
            captured_frame = next(
                item for item in captured.stack
                if item.filename == frame.f_code.co_filename and item.lineno == cursor.tb_lineno
            )
            for marker in markers:
                case.assertNotIn(marker, repr(frame.f_locals))
                case.assertNotIn(marker, repr(captured_frame.locals))
        cursor = cursor.tb_next
    for marker in markers:
        case.assertNotIn(marker, str(error))
        case.assertNotIn(marker, repr(vars(error)))
        case.assertNotIn(marker, "".join(traceback.format_exception(error)))
    case.assertEqual(product_frames, expected_frames)


class ClientTests(unittest.TestCase):
    def _token(self, root: Path, value: str = "secret-" + "x" * 40) -> Path:
        path = root / "intake-token"
        path.write_text(value, encoding="utf-8")
        path.chmod(0o600)
        return path

    def test_submit_sends_bounded_request_and_returns_typed_response(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            token = self._token(Path(temporary))
            workflow_id = "01a01407-fe3e-72aa-9b8f-7666915df735"
            request_digest = "d" * 64
            brief = EvidenceBrief(
                answer="grounded", citations=[], uncertainties=[], next_decisions=[]
            )
            body = json.dumps(
                {
                    **brief.model_dump(mode="json"),
                    "request_digest": request_digest,
                    "workflow_id": workflow_id,
                    "markdown": "# Evidence brief\n",
                    "provider_audit": provider_audit(
                        brief, workflow_id=workflow_id, request_digest=request_digest
                    ).model_dump(mode="json"),
                }
            ).encode()
            seen = {}

            def open_request(request: object, timeout: int) -> _Response:
                seen["request"] = request
                seen["timeout"] = timeout
                return _Response(body)

            result = submit(
                question="What changed?",
                files=["one.md", "nested/two.txt"],
                endpoint="http://127.0.0.1:8765",
                token_file=token,
                idempotency_key=workflow_id,
                external_disclosure_ack=True,
                opener=open_request,
            )

            request = seen["request"]
            payload = json.loads(request.data)
            self.assertEqual(
                payload,
                {
                    "question": "What changed?",
                    "files": ["one.md", "nested/two.txt"],
                    "disclosure_profile": "external_disclosed_v1",
                    "disclosure_notice_digest": DISCLOSURE_NOTICE_DIGEST,
                    "external_disclosure_ack": True,
                },
            )
            self.assertEqual(request.full_url, "http://127.0.0.1:8765/v1/evidence-brief")
            self.assertEqual(request.get_header("Authorization"), "Bearer secret-" + "x" * 40)
            generated = request.get_header("Idempotency-key")
            self.assertEqual(generated, workflow_id)
            self.assertEqual(seen["timeout"], 330)
            self.assertEqual(result["markdown"], "# Evidence brief\n")

    def test_submit_inline_sends_exact_validated_source_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            token = self._token(Path(temporary))
            workflow_id, request_digest = (
                "01a01407-fe3e-72aa-9b8f-7666915df735", "d" * 64
            )
            brief = EvidenceBrief(
                answer="grounded", citations=[], uncertainties=[], next_decisions=[]
            )
            body = json.dumps({
                **brief.model_dump(mode="json"),
                "request_digest": request_digest,
                "workflow_id": workflow_id,
                "markdown": "# Evidence brief\n",
                "provider_audit": provider_audit(
                    brief, workflow_id=workflow_id, request_digest=request_digest
                ).model_dump(mode="json"),
            }).encode()
            seen: dict[str, object] = {}

            def open_request(request: object, timeout: int) -> _Response:
                seen["request"], seen["timeout"] = request, timeout
                return _Response(body)

            canonical = admit_inline_request(
                question="What changed?",
                sources=[{"path": "packet.txt", "content": "approved bytes\n"}],
                disclosure_profile="external_disclosed_v1",
                disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
                external_disclosure_ack=True,
            )
            submit_inline(
                canonical, "http://127.0.0.1:8765", token, workflow_id, opener=open_request
            )

        payload = json.loads(seen["request"].data)  # type: ignore[union-attr]
        self.assertEqual(
            payload["sources"], [{"path": "packet.txt", "content": "approved bytes\n"}]
        )
        self.assertNotIn("files", payload)

    def test_http_protocol_failures_are_safe_outside_source_and_bearer_frames(self) -> None:
        source_marker = "INLINE_CLIENT_PRIVATE_SOURCE_MARKER"
        bearer_marker = "INLINE_CLIENT_PRIVATE_BEARER_" + "b" * 32
        canonical = admit_inline_request(
            question="q",
            sources=[{"path": "safe.md", "content": source_marker}],
            disclosure_profile="external_disclosed_v1",
            disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
            external_disclosure_ack=True,
        )
        failures = (
            http.client.IncompleteRead(source_marker.encode(), 999),
            http.client.BadStatusLine(bearer_marker),
        )
        with tempfile.TemporaryDirectory() as temporary:
            token = self._token(Path(temporary), bearer_marker)
            for failure in failures:
                def fail_transport(
                    *_args: object,
                    _failure: http.client.HTTPException = failure,
                    **_kwargs: object,
                ) -> object:
                    raise _failure

                with self.subTest(failure=type(failure).__name__):
                    try:
                        submit_inline(
                            canonical, "http://127.0.0.1:8765", token,
                            opener=fail_transport,
                        )
                    except ClientError as error:
                        caught = error
                    else:
                        self.fail("expected ClientError")
                    self.assertEqual(str(caught), "Crawl API is unavailable")
                    _assert_client_trace_sanitized(
                        self, caught, ["submit_inline"], source_marker, bearer_marker
                    )

    def test_external_disclosure_must_be_explicit_before_capability_read_or_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            token = self._token(Path(temporary))
            for acknowledgement in (1, 1.0, False, "true"):
                with (
                    self.subTest(acknowledgement=acknowledgement),
                    patch("glupta_agi.client._read_capability") as capability,
                    self.assertRaisesRegex(ClientError, "acknowledgement"),
                ):
                    submit(
                        "q", ["one.md"], "http://127.0.0.1:8765", token,
                        external_disclosure_ack=acknowledgement,
                        opener=lambda *_a, **_k: self.fail("network dispatch"),
                    )
                capability.assert_not_called()

    def test_legacy_submit_failures_release_request_bearer_and_response_locals(self) -> None:
        question_marker = "LEGACY_PRIVATE_QUESTION_MARKER"
        bearer_marker = "LEGACY_PRIVATE_BEARER_" + "b" * 32
        response_marker = "LEGACY_PRIVATE_RESPONSE_MARKER"
        workflow_id = "01a01407-fe3e-72aa-9b8f-7666915df735"
        other_id = "01a01407-fe3e-72aa-9b8f-7666915df736"
        brief = EvidenceBrief(
            answer=response_marker, citations=[], uncertainties=[], next_decisions=[]
        )
        mismatched = json.dumps({
            **brief.model_dump(mode="json"),
            "request_digest": "d" * 64,
            "workflow_id": other_id,
            "markdown": response_marker,
            "provider_audit": provider_audit(
                brief, workflow_id=other_id, request_digest="d" * 64
            ).model_dump(mode="json"),
        }).encode()
        cases = (
            (lambda *_a, **_k: (_ for _ in ()).throw(
                ClientError("server redirect rejected")), "server redirect rejected"),
            (lambda *_a, **_k: (_ for _ in ()).throw(
                urllib.error.HTTPError("url", 503, bearer_marker, {}, None)),
             f"server returned HTTP 503 for workflow {workflow_id}"),
            (lambda *_a, **_k: _Response(
                response_marker.encode() * (MAX_RESPONSE_BYTES // len(response_marker) + 1)),
             "server response exceeds the client limit"),
            (lambda *_a, **_k: _Response(response_marker.encode()),
             "server returned an invalid evidence brief"),
            (lambda *_a, **_k: _Response(mismatched),
             "server returned a mismatched workflow result"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            token = self._token(Path(temporary), bearer_marker)
            for opener, message in cases:
                with self.subTest(message=message):
                    try:
                        submit(
                            question_marker, ["one.md"], "http://127.0.0.1:8765", token,
                            workflow_id, external_disclosure_ack=True, opener=opener,
                        )
                    except ClientError as error:
                        caught = error
                    else:
                        self.fail("expected ClientError")
                    self.assertEqual(str(caught), message)
                    _assert_client_trace_sanitized(
                        self, caught, ["submit"],
                        question_marker, bearer_marker, response_marker,
                    )

    def test_response_audit_and_requested_workflow_are_cross_bound(self) -> None:
        workflow_id, request_digest = "01a01407-fe3e-72aa-9b8f-7666915df735", "d" * 64
        brief = EvidenceBrief(answer="grounded", citations=[], uncertainties=[], next_decisions=[])
        audit = provider_audit(brief, workflow_id=workflow_id, request_digest=request_digest)
        valid = {
            **brief.model_dump(mode="json"),
            "request_digest": request_digest,
            "workflow_id": workflow_id,
            "markdown": "# Evidence brief\n",
            "provider_audit": audit.model_dump(mode="json"),
        }
        with tempfile.TemporaryDirectory() as temporary:
            token = self._token(Path(temporary))
            tampered = {**valid, "provider_audit": {**valid["provider_audit"], "response_id": "x"}}
            with self.assertRaisesRegex(ClientError, "invalid evidence brief"):
                submit(
                    "q", ["one.md"], "http://127.0.0.1:8765", token, workflow_id,
                    external_disclosure_ack=True,
                    opener=lambda *_a, **_k: _Response(json.dumps(tampered).encode()),
                )
            other_id = "01a01407-fe3e-72aa-9b8f-7666915df736"
            other = {
                **valid,
                "workflow_id": other_id,
                "provider_audit": provider_audit(
                    brief, workflow_id=other_id, request_digest=request_digest
                ).model_dump(mode="json"),
            }
            with self.assertRaisesRegex(ClientError, "mismatched workflow"):
                submit(
                    "q", ["one.md"], "http://127.0.0.1:8765", token, workflow_id,
                    external_disclosure_ack=True,
                    opener=lambda *_a, **_k: _Response(json.dumps(other).encode()),
                )

    def test_main_prints_markdown_or_json_without_capability(self) -> None:
        result = {"markdown": "# Brief\n", "workflow_id": "id"}
        with patch("glupta_agi.client.submit", return_value=result):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(["--question", "q", "--ack-external-disclosure", "facts.md"]), 0
                )
            self.assertEqual(output.getvalue(), "# Brief\n")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(
                        [
                            "--question",
                            "q",
                            "--ack-external-disclosure",
                            "--json",
                            "facts.md",
                        ]
                    ),
                    0,
                )
            self.assertEqual(json.loads(output.getvalue()), result)

    def test_capability_metadata_and_file_fail_closed(self) -> None:
        valid = SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=os.geteuid(), st_size=40)
        _validate_token_metadata(valid)
        for invalid in (
            SimpleNamespace(st_mode=stat.S_IFLNK | 0o600, st_uid=os.geteuid(), st_size=40),
            SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=os.geteuid(), st_size=40),
            SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=os.geteuid() + 1, st_size=40),
            SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=os.geteuid(), st_size=5000),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ClientError):
                    _validate_token_metadata(invalid)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            short = self._token(root, "short")
            target = root / "target"
            target.write_text("secret-" + "x" * 40, encoding="utf-8")
            target.chmod(0o600)
            link = root / "link"
            link.symlink_to(target)
            group_readable = root / "group-readable"
            group_readable.write_text("secret-" + "x" * 40, encoding="utf-8")
            group_readable.chmod(0o640)
            oversized = root / "oversized"
            oversized.write_text("x" * 4097, encoding="utf-8")
            oversized.chmod(0o600)
            for invalid_path in (short, link, group_readable, oversized, root / "missing", root):
                with self.subTest(invalid_path=invalid_path):
                    with self.assertRaises(ClientError):
                        submit(
                            "q",
                            ["one.md"],
                            "http://127.0.0.1:8765",
                            invalid_path,
                            external_disclosure_ack=True,
                            opener=lambda *_a, **_k: self.fail("network dispatch"),
                        )

    def test_endpoint_source_and_idempotency_validation_precede_dispatch(self) -> None:
        for endpoint in (
            "https://127.0.0.1:8765",
            "http://localhost:8765",
            "http://example.com:8765",
            "http://user@127.0.0.1:8765",
            "http://127.0.0.1:8765/path",
            "http://127.0.0.1:8765?query=1",
        ):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ClientError):
                    _validate_endpoint(endpoint)

        with tempfile.TemporaryDirectory() as temporary:
            token = self._token(Path(temporary))
            for files, key in (
                (["../bad.md"], None),
                (["one.md", "one.md"], None),
                (["one.md"], str(uuid.uuid4())),
            ):
                with self.subTest(files=files, key=key):
                    with self.assertRaises(ClientError):
                        submit(
                            "q",
                            files,
                            "http://127.0.0.1:8765",
                            token,
                            key,
                            external_disclosure_ack=True,
                            opener=lambda *_a, **_k: self.fail("network dispatch"),
                        )

    def test_redirects_are_not_followed(self) -> None:
        with self.assertRaisesRegex(ClientError, "redirect rejected"):
            _NoRedirect().redirect_request(None, None, 302, "redirect", {}, "url")

    def test_hostile_ambient_proxy_cannot_receive_loopback_bearer(self) -> None:
        seen = {"target": False, "proxy": False, "proxy_auth": False}
        workflow_id, request_digest = "01a01407-fe3e-72aa-9b8f-7666915df735", "d" * 64
        brief = EvidenceBrief(answer="grounded", citations=[], uncertainties=[], next_decisions=[])
        body = json.dumps(
            {
                **brief.model_dump(mode="json"),
                "request_digest": request_digest,
                "workflow_id": workflow_id,
                "markdown": "# Evidence brief\n",
                "provider_audit": provider_audit(
                    brief, workflow_id=workflow_id, request_digest=request_digest
                ).model_dump(mode="json"),
            }
        ).encode()

        def handler(label: str) -> type[BaseHTTPRequestHandler]:
            class Handler(BaseHTTPRequestHandler):
                def do_POST(self) -> None:
                    seen[label] = True
                    seen[f"{label}_auth"] = bool(self.headers.get("Authorization"))
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, *_args: object) -> None:
                    pass

            return Handler

        target = ThreadingHTTPServer(("127.0.0.1", 0), handler("target"))
        proxy = ThreadingHTTPServer(("127.0.0.1", 0), handler("proxy"))
        threads = [threading.Thread(target=server.serve_forever) for server in (target, proxy)]
        for thread in threads:
            thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary, patch.dict(
                os.environ,
                {
                    "HTTP_PROXY": f"http://127.0.0.1:{proxy.server_port}",
                    "http_proxy": f"http://127.0.0.1:{proxy.server_port}",
                    "HTTPS_PROXY": f"http://127.0.0.1:{proxy.server_port}",
                    "https_proxy": f"http://127.0.0.1:{proxy.server_port}",
                },
                clear=True,
            ):
                submit(
                    "q", ["one.md"], f"http://127.0.0.1:{target.server_port}",
                    self._token(Path(temporary)), workflow_id,
                    external_disclosure_ack=True,
                )
        finally:
            for server in (target, proxy):
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join()
        self.assertTrue(seen["target"])
        self.assertFalse(seen["proxy"])
        self.assertFalse(seen["proxy_auth"])

    def test_transport_failures_are_bounded_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            secret = "do-not-disclose-" + "x" * 32
            token = self._token(Path(temporary), secret)
            workflow_id = "01a01407-fe3e-72aa-9b8f-7666915df735"

            def http_error(*_args: object, **_kwargs: object) -> object:
                raise urllib.error.HTTPError("url", 503, secret, {}, None)

            with self.assertRaises(ClientError) as caught:
                submit(
                    "q",
                    ["one.md"],
                    "http://127.0.0.1:8765",
                    token,
                    workflow_id,
                    external_disclosure_ack=True,
                    opener=http_error,
                )
            self.assertEqual(
                str(caught.exception),
                f"server returned HTTP 503 for workflow {workflow_id}",
            )
            self.assertNotIn(secret, str(caught.exception))
            self.assertIsNone(caught.exception.__cause__)
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn(secret, repr(vars(caught.exception)))
            self.assertNotIn(secret, "".join(traceback.format_exception(caught.exception)))

            with self.assertRaises(ClientError):
                submit(
                    "q",
                    ["one.md"],
                    "http://127.0.0.1:8765",
                    token,
                    external_disclosure_ack=True,
                    opener=lambda *_a, **_k: _Response(b"x" * (2 * 1024 * 1024 + 1)),
                )

            with self.assertRaises(ClientError):
                submit(
                    "q",
                    ["one.md"],
                    "http://127.0.0.1:8765",
                    token,
                    external_disclosure_ack=True,
                    opener=lambda *_a, **_k: _Response(b"not-json"),
                )

            with self.assertRaises(ClientError):
                submit(
                    "q",
                    ["one.md"],
                    "http://127.0.0.1:8765",
                    token,
                    external_disclosure_ack=True,
                    opener=lambda *_a, **_k: _Response(b'{"markdown":"incomplete"}'),
                )

    def test_main_reports_safe_error(self) -> None:
        error = ClientError("server returned HTTP 503")
        with patch("glupta_agi.client.submit", side_effect=error):
            output = io.StringIO()
            with redirect_stderr(output):
                self.assertEqual(
                    main(["--question", "q", "--ack-external-disclosure", "facts.md"]), 2
                )
            self.assertEqual(output.getvalue(), "error: server returned HTTP 503\n")
