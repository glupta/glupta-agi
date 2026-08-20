from __future__ import annotations

import hmac
import os
import stat
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlsplit

from pydantic import TypeAdapter

from .inference import PINNED_MODEL, ReleaseProfile, SubscriptionProfile, WalkReleaseProfile

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "postgres"})


class SettingsError(RuntimeError):
    pass


def _read_private_file(path: Path, *, label: str, maximum_bytes: int, minimum: int = 1) -> str:
    file_fd, unavailable = -1, False
    try:
        file_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        metadata = os.fstat(file_fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.geteuid()
        ):
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
    if not minimum <= len(value.encode()) <= maximum_bytes:
        del value, private_file
        raise SettingsError(f"{label} length is invalid")
    return value


def _validate_codex_home(path: Path) -> None:
    if not path.is_absolute():
        raise SettingsError("Codex subscription home path must be absolute")
    try:
        home, auth = path.lstat(), (path / "auth.json").lstat()
    except OSError:
        raise SettingsError("Codex subscription authentication is unavailable") from None
    if (
        not stat.S_ISDIR(home.st_mode)
        or stat.S_IMODE(home.st_mode) != 0o700
        or home.st_uid != os.geteuid()
        or not stat.S_ISREG(auth.st_mode)
        or stat.S_IMODE(auth.st_mode) != 0o600
        or auth.st_uid != os.geteuid()
    ):
        raise SettingsError("Codex subscription authentication is not private")


@dataclass(frozen=True)
class Settings:
    input_root: Path
    token: str
    release_profile: SubscriptionProfile | None = None
    release_profile_digest: str = ""
    codex_home: Path | None = None
    auth_generation: int = 0
    model: str = PINNED_MODEL

    @classmethod
    def from_environment(cls) -> Settings:
        profile_path = Path(
            os.environ.get("GLUPTA_RELEASE_PROFILE_FILE", "/run/private/release-profile.json")
        )
        invalid_profile = False
        try:
            profile = TypeAdapter(SubscriptionProfile).validate_json(
                _read_private_file(profile_path, label="release profile", maximum_bytes=32_768)
            )
        except ValueError:
            invalid_profile = True
        if invalid_profile:
            raise SettingsError("release profile is invalid") from None
        if not profile.current_at():
            raise SettingsError("release profile evidence is expired")
        codex_home = Path(os.environ.get("GLUPTA_CODEX_HOME", "/run/codex"))
        _validate_codex_home(codex_home)
        try:
            raw_generation = os.environ["GLUPTA_AUTH_GENERATION"]
            generation = int(raw_generation)
            if (
                not raw_generation.isascii()
                or not raw_generation.isdecimal()
                or str(generation) != raw_generation
            ):
                raise ValueError
        except (KeyError, ValueError):
            raise SettingsError("subscription auth generation is unavailable") from None
        if generation < 1 or generation != profile.auth_generation:
            raise SettingsError("subscription auth generation does not match the release profile")
        token_path = Path(os.environ.get("GLUPTA_INTAKE_TOKEN_FILE", "/run/private/intake-token"))
        token = _read_private_file(
            token_path, label="intake capability", maximum_bytes=4096, minimum=32
        )
        return cls(
            input_root=Path(os.environ.get("GLUPTA_INPUT_ROOT", "/data/inputs")),
            token=token,
            release_profile=profile,
            release_profile_digest=profile.digest(),
            codex_home=codex_home,
            auth_generation=generation,
        )

    def require_external_profile(self) -> tuple[ReleaseProfile, Path, int]:
        if not isinstance(self.release_profile, ReleaseProfile) or isinstance(
                self.release_profile, WalkReleaseProfile) or self.codex_home is None:
            raise SettingsError("external inference release profile is unavailable")
        if self.release_profile.digest() != self.release_profile_digest:
            raise SettingsError("external inference release profile changed")
        if not self.release_profile.current_at():
            raise SettingsError("release profile evidence is expired")
        if self.auth_generation != self.release_profile.auth_generation:
            raise SettingsError("subscription auth generation does not match the release profile")
        _validate_codex_home(self.codex_home)
        return self.release_profile, self.codex_home, self.auth_generation

    def require_walk_profile(self) -> tuple[WalkReleaseProfile, Path, int]:
        if not isinstance(self.release_profile, WalkReleaseProfile) or self.codex_home is None:
            raise SettingsError("Walk release profile is unavailable")
        if self.release_profile.digest() != self.release_profile_digest:
            raise SettingsError("Walk release profile changed")
        if not self.release_profile.current_at():
            raise SettingsError("release profile evidence is expired")
        if self.auth_generation != self.release_profile.auth_generation:
            raise SettingsError("subscription auth generation does not match the release profile")
        _validate_codex_home(self.codex_home)
        return self.release_profile, self.codex_home, self.auth_generation

    @staticmethod
    def dbos_system_database_url() -> str:
        explicit = os.environ.get("DBOS_SYSTEM_DATABASE_URL")
        if explicit:
            parsed = urlsplit(explicit)
            if parsed.scheme != "postgresql" or parsed.hostname not in LOCAL_HOSTS:
                del explicit, parsed
                raise SettingsError("DBOS system database must be local PostgreSQL")
            return explicit
        password_path = Path(
            os.environ.get("GLUPTA_POSTGRES_PASSWORD_FILE", "/run/private/postgres-password")
        )
        user = quote(os.environ.get("GLUPTA_POSTGRES_USER", "glupta"), safe="")
        host = os.environ.get("GLUPTA_POSTGRES_HOST", "postgres")
        if host not in LOCAL_HOSTS:
            raise SettingsError("PostgreSQL host must be local")
        port = int(os.environ.get("GLUPTA_POSTGRES_PORT", "5432"))
        database = quote(os.environ.get("GLUPTA_POSTGRES_DB", "glupta"), safe="")
        password = _read_private_file(password_path, label="PostgreSQL password", maximum_bytes=512)
        return f"postgresql://{user}:{quote(password, safe='')}@{host}:{port}/{database}"

    def authenticates(self, candidate: str) -> bool:
        return hmac.compare_digest(self.token.encode(), candidate.encode())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_environment()
