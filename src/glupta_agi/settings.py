"""Runtime settings with file-backed capability loading."""

from __future__ import annotations

import hmac
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "postgres"})
PINNED_CODEX_MODEL = "gpt-5.6-sol"
DEFAULT_CODEX_HOME = Path("/run/codex")


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


def _validate_codex_runtime(home: Path) -> None:
    if not home.is_absolute() or not (home / "auth.json").is_file():
        raise SettingsError("Crawl must use the configured secondary Codex subscription")


@dataclass(frozen=True)
class Settings:
    input_root: Path
    artifact_root: Path
    token: str
    codex_home: Path = DEFAULT_CODEX_HOME
    codex_model: str = PINNED_CODEX_MODEL

    @classmethod
    def from_environment(cls) -> Settings:
        token_path = Path(os.environ.get("GLUPTA_INTAKE_TOKEN_FILE", "/run/secrets/intake-token"))
        token = _read_private_file(token_path, label="intake capability", maximum_bytes=4096)
        if not 32 <= len(token) <= 4096:
            raise SettingsError("intake capability length is invalid")
        codex_home = Path(os.environ.get("GLUPTA_CODEX_HOME", str(DEFAULT_CODEX_HOME)))
        codex_model = os.environ.get("GLUPTA_CODEX_MODEL", PINNED_CODEX_MODEL)
        _validate_codex_runtime(codex_home)
        if codex_model != PINNED_CODEX_MODEL:
            raise SettingsError("Crawl must use the pinned Codex model")
        return cls(
            input_root=Path(os.environ.get("GLUPTA_INPUT_ROOT", "/inputs")),
            artifact_root=Path(os.environ.get("GLUPTA_ARTIFACT_ROOT", "/artifacts")),
            token=token,
            codex_home=codex_home,
            codex_model=codex_model,
        )

    def dbos_system_database_url(self) -> str:
        explicit = os.environ.get("DBOS_SYSTEM_DATABASE_URL")
        if explicit:
            parsed = urlsplit(explicit)
            if parsed.scheme != "postgresql":
                raise SettingsError("DBOS system database must be PostgreSQL")
            if parsed.hostname not in LOCAL_HOSTS:
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
