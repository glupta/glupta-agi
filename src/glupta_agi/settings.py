"""Fail-closed runtime settings and file-backed capability metadata."""

from __future__ import annotations

import hmac
import os
import stat
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlsplit

from .inference import PINNED_MODEL, ReleaseProfile

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "postgres"})


class SettingsError(RuntimeError):
    pass


def _read_private_file(path: Path, *, label: str, maximum_bytes: int) -> str:
    file_fd, unavailable = -1, False
    try:
        file_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        metadata = os.fstat(file_fd)
        if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_uid != os.geteuid()):
            raise SettingsError(f"{label} file must be owned, regular, and mode 0600")
        with os.fdopen(file_fd, encoding="utf-8") as private_file:
            file_fd = -1
            value = private_file.read(maximum_bytes + 1).strip()
    except SettingsError:
        raise
    except (OSError, UnicodeError):
        unavailable = True
    finally:
        if file_fd >= 0:
            os.close(file_fd)
    if unavailable:
        raise SettingsError(f"{label} file is unavailable") from None
    if not value or len(value.encode()) > maximum_bytes:
        raise SettingsError(f"{label} length is invalid")
    return value


def _validate_private_path(path: Path, *, label: str) -> None:
    if not path.is_absolute():
        raise SettingsError(f"{label} path must be absolute")
    try:
        metadata = path.lstat()
    except OSError:
        raise SettingsError(f"{label} file is unavailable") from None
    if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.geteuid()):
        raise SettingsError(f"{label} file must be owned, regular, and mode 0600")


@dataclass(frozen=True)
class Settings:
    input_root: Path
    token: str
    release_profile: ReleaseProfile | None = None
    release_profile_digest: str = ""
    openai_api_key_file: Path | None = None
    credential_generation: int = 0
    model: str = PINNED_MODEL

    @classmethod
    def from_environment(cls) -> Settings:
        token_path = Path(os.environ.get("GLUPTA_INTAKE_TOKEN_FILE", "/run/private/intake-token"))
        token = _read_private_file(token_path, label="intake capability", maximum_bytes=4096)
        if not 32 <= len(token.encode()) <= 4096:
            raise SettingsError("intake capability length is invalid")
        profile_path = Path(os.environ.get(
            "GLUPTA_RELEASE_PROFILE_FILE", "/run/private/release-profile.json"))
        invalid_profile = False
        try:
            profile = ReleaseProfile.model_validate_json(_read_private_file(
                profile_path, label="release profile", maximum_bytes=32_768))
        except ValueError:
            invalid_profile = True
        if invalid_profile:
            raise SettingsError("release profile is invalid") from None
        if not profile.current_at():
            raise SettingsError("release profile evidence is expired")
        credential_path = Path(os.environ.get(
            "GLUPTA_OPENAI_API_KEY_FILE", "/run/private/openai-api-key"))
        _validate_private_path(credential_path, label="OpenAI credential")
        try:
            raw_generation = os.environ["GLUPTA_CREDENTIAL_GENERATION"]
            generation = int(raw_generation)
            if (not raw_generation.isascii() or not raw_generation.isdecimal()
                    or str(generation) != raw_generation):
                raise ValueError
        except (KeyError, ValueError):
            raise SettingsError("credential generation is unavailable") from None
        if generation < 1 or generation != profile.credential_generation:
            raise SettingsError("credential generation does not match the release profile")
        return cls(input_root=Path(os.environ.get("GLUPTA_INPUT_ROOT", "/data/inputs")),
                   token=token, release_profile=profile,
                   release_profile_digest=profile.digest(),
                   openai_api_key_file=credential_path, credential_generation=generation)

    def require_external_profile(self) -> tuple[ReleaseProfile, Path, int]:
        if self.release_profile is None or self.openai_api_key_file is None:
            raise SettingsError("external inference release profile is unavailable")
        if self.release_profile.digest() != self.release_profile_digest:
            raise SettingsError("external inference release profile changed")
        if not self.release_profile.current_at():
            raise SettingsError("release profile evidence is expired")
        if self.credential_generation != self.release_profile.credential_generation:
            raise SettingsError("credential generation does not match the release profile")
        return self.release_profile, self.openai_api_key_file, self.credential_generation

    def dbos_system_database_url(self) -> str:
        explicit = os.environ.get("DBOS_SYSTEM_DATABASE_URL")
        if explicit:
            parsed = urlsplit(explicit)
            if parsed.scheme != "postgresql" or parsed.hostname not in LOCAL_HOSTS:
                raise SettingsError("DBOS system database must be local PostgreSQL")
            return explicit
        password_path = Path(os.environ.get(
            "GLUPTA_POSTGRES_PASSWORD_FILE", "/run/private/postgres-password"))
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_environment()
