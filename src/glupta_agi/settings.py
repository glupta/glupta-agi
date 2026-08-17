"""Runtime settings with file-backed capability loading."""

from __future__ import annotations

import hmac
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "ollama", "postgres", "host.docker.internal"})


class SettingsError(RuntimeError):
    pass


def _read_private_file(path: Path, *, label: str, maximum_bytes: int) -> str:
    try:
        file_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
                raise SettingsError(f"{label} file must be private and regular")
            with os.fdopen(file_fd, "r", encoding="utf-8") as secret_file:
                file_fd = -1
                value = secret_file.read(maximum_bytes + 1).strip()
        finally:
            if file_fd >= 0:
                os.close(file_fd)
    except OSError as exc:
        raise SettingsError(f"{label} file is unavailable") from exc
    if not value or len(value.encode("utf-8")) > maximum_bytes:
        raise SettingsError(f"{label} length is invalid")
    return value


def _require_local_url(value: str, *, label: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOCAL_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise SettingsError(f"{label} must use an approved local endpoint")
    return value


@dataclass(frozen=True)
class Settings:
    input_root: Path
    artifact_root: Path
    token: str
    ollama_base_url: str
    ollama_model: str = "qwen3.8:27b"

    @classmethod
    def from_environment(cls) -> Settings:
        token_path = Path(os.environ.get("GLUPTA_INTAKE_TOKEN_FILE", "/run/secrets/intake-token"))
        token = _read_private_file(token_path, label="intake capability", maximum_bytes=4096)
        if not 32 <= len(token) <= 4096:
            raise SettingsError("intake capability length is invalid")
        ollama_base_url = _require_local_url(
            os.environ.get("GLUPTA_OLLAMA_URL", "http://ollama:11434/v1"),
            label="Ollama URL",
        )
        if urlsplit(ollama_base_url).path.rstrip("/") != "/v1":
            raise SettingsError("Ollama URL must end at /v1")
        return cls(
            input_root=Path(os.environ.get("GLUPTA_INPUT_ROOT", "/inputs")),
            artifact_root=Path(os.environ.get("GLUPTA_ARTIFACT_ROOT", "/artifacts")),
            token=token,
            ollama_base_url=ollama_base_url,
        )

    def dbos_system_database_url(self) -> str:
        explicit = os.environ.get("DBOS_SYSTEM_DATABASE_URL")
        if explicit:
            parsed = urlsplit(explicit)
            if parsed.scheme not in {"postgresql", "sqlite"}:
                raise SettingsError("DBOS system database must be PostgreSQL or SQLite")
            if parsed.scheme == "postgresql" and parsed.hostname not in LOCAL_HOSTS:
                raise SettingsError("DBOS PostgreSQL endpoint must be local")
            return explicit

        password_path = Path(
            os.environ.get("GLUPTA_POSTGRES_PASSWORD_FILE", "/run/secrets/postgres-password")
        )
        password = _read_private_file(password_path, label="PostgreSQL password", maximum_bytes=512)
        user = quote(os.environ.get("GLUPTA_POSTGRES_USER", "glupta"), safe="")
        host = os.environ.get("GLUPTA_POSTGRES_HOST", "postgres")
        if host not in LOCAL_HOSTS:
            raise SettingsError("PostgreSQL host must be local")
        port = int(os.environ.get("GLUPTA_POSTGRES_PORT", "5432"))
        database = quote(os.environ.get("GLUPTA_POSTGRES_DB", "glupta"), safe="")
        return f"postgresql://{user}:{quote(password, safe='')}@{host}:{port}/{database}"

    def authenticates(self, candidate: str) -> bool:
        return hmac.compare_digest(self.token.encode(), candidate.encode())
