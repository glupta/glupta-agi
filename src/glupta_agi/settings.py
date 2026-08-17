"""Runtime settings with file-backed capability loading."""

from __future__ import annotations

import hmac
import os
import stat
from dataclasses import dataclass
from pathlib import Path


class SettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    input_root: Path
    artifact_root: Path
    token: str
    ollama_base_url: str
    ollama_model: str = "qwen3.6:27b"

    @classmethod
    def from_environment(cls) -> "Settings":
        token_path = Path(os.environ.get("GLUPTA_INTAKE_TOKEN_FILE", "/run/secrets/intake-token"))
        try:
            token_fd = os.open(token_path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                metadata = os.fstat(token_fd)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
                    raise SettingsError("intake capability file must be private and regular")
                with os.fdopen(token_fd, "r", encoding="utf-8") as token_file:
                    token_fd = -1
                    token = token_file.read(4097).strip()
            finally:
                if token_fd >= 0:
                    os.close(token_fd)
        except OSError as exc:
            raise SettingsError("intake capability file is unavailable") from exc
        if not 32 <= len(token) <= 4096:
            raise SettingsError("intake capability length is invalid")
        return cls(
            input_root=Path(os.environ.get("GLUPTA_INPUT_ROOT", "/inputs")),
            artifact_root=Path(os.environ.get("GLUPTA_ARTIFACT_ROOT", "/artifacts")),
            token=token,
            ollama_base_url=os.environ.get("GLUPTA_OLLAMA_URL", "http://ollama:11434/v1"),
        )

    def authenticates(self, candidate: str) -> bool:
        return hmac.compare_digest(self.token.encode(), candidate.encode())
