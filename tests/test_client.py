from __future__ import annotations

import io
import json
import os
import stat
import tempfile
import unittest
import urllib.error
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from glupta_agi.client import (
    ClientError,
    _NoRedirect,
    _read_capability,
    _validate_endpoint,
    _validate_token_metadata,
    main,
    submit,
)


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class ClientTests(unittest.TestCase):
    def _token(self, root: Path, value: str = "secret-" + "x" * 40) -> Path:
        path = root / "intake-token"
        path.write_text(value, encoding="utf-8")
        path.chmod(0o600)
        return path

    def test_submit_sends_bounded_request_and_returns_typed_response(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            token = self._token(Path(temporary))
            body = json.dumps(
                {
                    "answer": "grounded",
                    "citations": [],
                    "uncertainties": [],
                    "next_decisions": [],
                    "request_digest": "d" * 64,
                    "workflow_id": "01a01407-fe3e-72aa-9b8f-7666915df735",
                    "markdown": "# Evidence brief\n",
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
                opener=open_request,
            )

            request = seen["request"]
            payload = json.loads(request.data)
            self.assertEqual(
                payload, {"question": "What changed?", "files": ["one.md", "nested/two.txt"]}
            )
            self.assertEqual(request.full_url, "http://127.0.0.1:8765/v1/evidence-brief")
            self.assertEqual(request.get_header("Authorization"), "Bearer secret-" + "x" * 40)
            generated = request.get_header("Idempotency-key")
            self.assertEqual(uuid.UUID(generated).version, 7)
            self.assertEqual(str(uuid.UUID(generated)), generated)
            self.assertEqual(seen["timeout"], 330)
            self.assertEqual(result["markdown"], "# Evidence brief\n")

    def test_main_prints_markdown_or_json_without_capability(self) -> None:
        result = {"markdown": "# Brief\n", "workflow_id": "id"}
        with patch("glupta_agi.client.submit", return_value=result):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--question", "q", "facts.md"]), 0)
            self.assertEqual(output.getvalue(), "# Brief\n")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--question", "q", "--json", "facts.md"]), 0)
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
            with self.assertRaises(ClientError):
                _read_capability(short)
            short.unlink()
            target = self._token(root)
            link = root / "link"
            link.symlink_to(target)
            with self.assertRaises(ClientError):
                _read_capability(link)

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
                            opener=lambda *_a, **_k: self.fail("network dispatch"),
                        )

    def test_redirects_are_not_followed(self) -> None:
        with self.assertRaisesRegex(ClientError, "redirect rejected"):
            _NoRedirect().redirect_request(None, None, 302, "redirect", {}, "url")

    def test_transport_failures_are_bounded_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            secret = "do-not-disclose-" + "x" * 32
            token = self._token(Path(temporary), secret)

            def http_error(*_args: object, **_kwargs: object) -> object:
                raise urllib.error.HTTPError("url", 503, secret, {}, None)

            with self.assertRaises(ClientError) as caught:
                submit("q", ["one.md"], "http://127.0.0.1:8765", token, opener=http_error)
            self.assertNotIn(secret, str(caught.exception))

            with self.assertRaises(ClientError):
                submit(
                    "q",
                    ["one.md"],
                    "http://127.0.0.1:8765",
                    token,
                    opener=lambda *_a, **_k: _Response(b"x" * (2 * 1024 * 1024 + 1)),
                )

            with self.assertRaises(ClientError):
                submit(
                    "q",
                    ["one.md"],
                    "http://127.0.0.1:8765",
                    token,
                    opener=lambda *_a, **_k: _Response(b"not-json"),
                )

    def test_main_reports_safe_error(self) -> None:
        error = ClientError("server returned HTTP 503")
        with patch("glupta_agi.client.submit", side_effect=error):
            output = io.StringIO()
            with redirect_stderr(output):
                self.assertEqual(main(["--question", "q", "facts.md"]), 2)
            self.assertEqual(output.getvalue(), "error: server returned HTTP 503\n")
