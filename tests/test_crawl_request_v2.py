from __future__ import annotations

import hashlib
import json
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.crawl_request_v2 import (
    RequestPreflightError,
    create_artifact,
    execute_artifact,
    verify_artifact,
)


def _assert_script_trace_sanitized(
    case: unittest.TestCase, error: BaseException, expected_frames: list[str], *markers: str,
) -> None:
    case.assertIsNone(error.__cause__)
    case.assertIsNone(error.__context__)
    captured = traceback.TracebackException.from_exception(error, capture_locals=True)
    product_frames: list[str] = []
    cursor = error.__traceback__
    while cursor is not None:
        frame = cursor.tb_frame
        if frame.f_code.co_filename.endswith("/scripts/crawl_request_v2.py"):
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


class CrawlRequestV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        (self.repo / "inputs").mkdir()
        (self.repo / "inputs" / "packet.txt").write_text(
            "synthetic packet\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _artifact(self, purpose: str = "canary") -> dict[str, object]:
        return create_artifact(
            repo_root=self.repo,
            input_root_dir="inputs",
            repo_paths=["inputs/packet.txt"],
            question="What changed?",
            purpose=purpose,
        )

    @staticmethod
    def _approved(artifact: dict[str, object]) -> tuple[bytes, str]:
        raw = json.dumps(artifact, separators=(",", ":"), sort_keys=True).encode()
        return raw, hashlib.sha256(raw).hexdigest()

    def test_create_binds_exact_repo_path_client_path_and_sha(self) -> None:
        artifact = self._artifact()
        self.assertEqual(artifact["sources"], [{
            "repo_path": "inputs/packet.txt",
            "client_selected_path": "packet.txt",
            "sha256": hashlib.sha256(b"synthetic packet\n").hexdigest(),
        }])
        raw, digest = self._approved(artifact)
        canonical = verify_artifact(raw, self.repo, digest)
        self.assertEqual(canonical.question, "What changed?")
        self.assertEqual(tuple(source.path for source in canonical.sources), ("packet.txt",))

    def test_preflight_rejects_leading_input_root_before_dispatch(self) -> None:
        artifact = self._artifact()
        artifact["sources"][0]["client_selected_path"] = "inputs/packet.txt"  # type: ignore[index]
        raw, digest = self._approved(artifact)
        with (
            patch("scripts.crawl_request_v2.submit_inline") as dispatch,
            self.assertRaisesRegex(
                RequestPreflightError, "input_root_dir/client_selected_path"
            ),
        ):
            execute_artifact(
                raw, self.repo, digest, "http://127.0.0.1:8765", self.repo / "token", None
            )
        dispatch.assert_not_called()

    def test_execute_retains_exact_verified_bytes_when_file_changes_after_preflight(self) -> None:
        artifact = self._artifact("conditional_drain")
        raw, digest = self._approved(artifact)

        def dispatch(*_args: object, **_kwargs: object) -> dict[str, bool]:
            (self.repo / "inputs" / "packet.txt").write_text("swapped\n", encoding="utf-8")
            return {"ok": True}

        with patch("scripts.crawl_request_v2.submit_inline", side_effect=dispatch) as submitted:
            result = execute_artifact(
                raw, self.repo, digest, "http://127.0.0.1:8765", self.repo / "token",
                "workflow-id",
            )

        self.assertEqual(result, {"ok": True})
        canonical = submitted.call_args.args[0]
        self.assertEqual(canonical.sources[0].path, "packet.txt")
        self.assertEqual(canonical.sources[0].content, "synthetic packet\n")
        self.assertNotIn("inputs/packet.txt", repr(canonical.sources))

    def test_preflight_rejects_changed_bytes_and_symlinks(self) -> None:
        artifact = self._artifact()
        raw, digest = self._approved(artifact)
        (self.repo / "inputs" / "packet.txt").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(RequestPreflightError, "SHA-256 changed"):
            verify_artifact(raw, self.repo, digest)

        (self.repo / "inputs" / "packet.txt").unlink()
        (self.repo / "target.txt").write_text("synthetic packet\n", encoding="utf-8")
        (self.repo / "inputs" / "packet.txt").symlink_to(self.repo / "target.txt")
        with self.assertRaisesRegex(
            RequestPreflightError, "missing, inaccessible, or not a regular file"
        ):
            verify_artifact(raw, self.repo, digest)

    def test_changed_artifact_digest_is_sanitized_before_capability_or_submit(self) -> None:
        marker = "REJECTED_ARTIFACT_PRIVATE_MARKER"
        artifact = self._artifact()
        _approved_raw, approved_digest = self._approved(artifact)
        artifact["question"] = marker
        changed_raw, _changed_digest = self._approved(artifact)
        with (
            patch("scripts.crawl_request_v2.submit_inline") as dispatch,
            patch("glupta_agi.client._read_capability") as capability,
        ):
            try:
                execute_artifact(
                    changed_raw, self.repo, approved_digest, "http://127.0.0.1:8765",
                    self.repo / "missing-token", None,
                )
            except RequestPreflightError as error:
                caught = error
            else:
                self.fail("expected RequestPreflightError")
        self.assertEqual(str(caught), "approval artifact SHA-256 changed")
        _assert_script_trace_sanitized(self, caught, ["execute_artifact"], marker)
        dispatch.assert_not_called()
        capability.assert_not_called()

    def test_source_drift_trace_is_sanitized_before_capability_or_submit(self) -> None:
        marker = "REJECTED_DRIFTED_SOURCE_CONTENT"
        artifact = self._artifact()
        raw, digest = self._approved(artifact)
        (self.repo / "inputs" / "packet.txt").write_text(marker, encoding="utf-8")
        with (
            patch("scripts.crawl_request_v2.submit_inline") as dispatch,
            patch("glupta_agi.client._read_capability") as capability,
        ):
            try:
                execute_artifact(
                    raw, self.repo, digest, "http://127.0.0.1:8765",
                    self.repo / "missing-token", None,
                )
            except RequestPreflightError as error:
                caught = error
            else:
                self.fail("expected RequestPreflightError")
        self.assertEqual(str(caught), "approved source SHA-256 changed")
        _assert_script_trace_sanitized(self, caught, ["execute_artifact"], marker)
        dispatch.assert_not_called()
        capability.assert_not_called()
