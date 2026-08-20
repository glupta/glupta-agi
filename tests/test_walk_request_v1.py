# ruff: noqa: S101
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.walk_request_v1 import artifact_bytes, main, read_artifact
from tests.helpers import walk_release_profile


def args(root: Path, output: Path) -> SimpleNamespace:
    return SimpleNamespace(input_root=root, files=["source.md"], question="Question?",
        family="walk_state_synthesis_v1", decision_owner="Akshay",
        deliverable_type=None, expected_disposition=None,
        release_profile_digest=walk_release_profile().digest(),
        ack_external_disclosure=True, output=output)


def test_create_verify_and_execute_bind_exact_approved_bytes_before_submit() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root, output = Path(directory), Path(directory) / "artifact.json"
        (root / "source.md").write_text("grounded", encoding="utf-8")
        raw = artifact_bytes(args(root, output))
        digest = hashlib.sha256(raw).hexdigest()
        assert main(["create", "source.md", "--input-root", str(root), "--question",
            "Question?", "--family", "walk_state_synthesis_v1", "--decision-owner",
            "Akshay", "--release-profile-digest", walk_release_profile().digest(),
            "--ack-external-disclosure", "--output", str(output)]) == 0
        assert os.stat(output).st_mode & 0o777 == 0o600
        assert read_artifact(output, digest) == raw
        assert main(["verify", str(output), "--artifact-sha256", digest]) == 0
        with patch("scripts.walk_request_v1.submit_walk_artifact",
            return_value={"workflow_id": "w"}) as submit:
            assert main(["execute", str(output), "--artifact-sha256", digest]) == 0
        assert submit.call_args.args[:2] == (raw, digest)


def test_verify_rejects_non_private_artifact_metadata() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root, output = Path(directory), Path(directory) / "artifact.json"
        (root / "source.md").write_text("grounded", encoding="utf-8")
        raw = artifact_bytes(args(root, output))
        output.write_bytes(raw)
        output.chmod(0o644)
        with pytest.raises(ValueError, match="unavailable, unsafe"):
            read_artifact(output, hashlib.sha256(raw).hexdigest())


def test_changed_artifact_or_source_shape_never_reaches_submit() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root, output = Path(directory), Path(directory) / "artifact.json"
        (root / "source.md").write_text("grounded", encoding="utf-8")
        raw = artifact_bytes(args(root, output))
        output.write_bytes(raw + b" ")
        with (patch("scripts.walk_request_v1.submit_walk_artifact") as submit,
              pytest.raises(ValueError, match="does not match approval")):
            read_artifact(output, hashlib.sha256(raw).hexdigest())
        submit.assert_not_called()
