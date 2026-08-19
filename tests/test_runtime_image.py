# ruff: noqa: S101,S108,S603,S607
from __future__ import annotations

import os
import subprocess
import textwrap

import pytest

IMAGE = os.environ.get("GLUPTA_RUNTIME_IMAGE")


@pytest.mark.skipif(IMAGE is None, reason="set GLUPTA_RUNTIME_IMAGE to verify a built image")
def test_exact_runtime_image_initializes_clean_sdk_without_a_turn() -> None:
    probe = textwrap.dedent(
        """
        import asyncio
        import os
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path

        from openai_codex import AsyncCodex, CodexConfig
        from glupta_agi.codex_adapter import _launch_args

        assert os.getuid() == os.getgid() == 65532
        env_path = shutil.which("env", path=os.defpath)
        assert env_path is not None
        assert Path(env_path).resolve() == Path("/usr/bin/env")
        assert os.access(env_path, os.X_OK)
        assert subprocess.run(
            ["/usr/bin/env", "-i", "/usr/bin/env"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout == ""
        assert not any(Path(path).exists() for path in (
            "/bin/sh", "/bin/ash", "/bin/bash", "/bin/busybox", "/bin/dash", "/bin/zsh",
            "/usr/bin/sh", "/usr/bin/ash", "/usr/bin/bash", "/usr/bin/dash", "/usr/bin/zsh",
        ))
        try:
            Path("/runtime-write-probe").write_text("denied", encoding="utf-8")
        except OSError:
            pass
        else:
            raise AssertionError("runtime root is writable")

        async def initialize() -> None:
            with tempfile.TemporaryDirectory() as root:
                codex_home = Path(root, "codex")
                state_home = Path(root, "state")
                codex_home.mkdir()
                state_home.mkdir()
                config = CodexConfig(
                    cwd=root,
                    launch_args_override=_launch_args(codex_home, state_home),
                )
                async with AsyncCodex(config) as client:
                    assert client.metadata is not None

        asyncio.run(initialize())
        """
    )
    result = subprocess.run(
        [
            "docker", "run", "--rm", "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--user", "65532:65532", "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=67108864,uid=65532,gid=65532,mode=0700",
            "--entrypoint", "/app/.venv/bin/python", IMAGE, "-c", probe,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
