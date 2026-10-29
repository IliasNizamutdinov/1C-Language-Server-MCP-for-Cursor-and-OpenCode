"""Настройки адаптера. Источник — переменные среды, не аргументы инструментов."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from bsl_mcp.constants import EXCLUDED_DIR_NAMES, FAIL_ON_VALUES


class SettingsError(ValueError):
    """Некорректная конфигурация сервера."""


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise SettingsError(f"{name} должно быть целым числом, получено {raw!r}.") from error
    if value <= 0:
        raise SettingsError(f"{name} должно быть больше нуля.")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise SettingsError(f"{name} должно быть числом, получено {raw!r}.") from error
    if value <= 0:
        raise SettingsError(f"{name} должно быть больше нуля.")
    return value


def _java_options() -> tuple[str, ...]:
    raw = os.environ.get("BSL_JAVA_OPTS")
    if raw is None:
        return ("-Dfile.encoding=UTF-8", "-Xmx768m")
    # Разбор строки на аргументы, без запуска оболочки.
    return tuple(shlex.split(raw, posix=(os.name != "nt")))


def _allowed_roots() -> tuple[Path, ...]:
    raw = os.environ.get("BSL_MCP_ALLOWED_ROOTS")
    if raw is None or raw.strip() == "":
        return (Path.cwd().resolve(),)
    roots: list[Path] = []
    for part in raw.split(os.pathsep):
        item = part.strip()
        if not item:
            continue
        path = Path(item).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        roots.append(path.resolve())
    if not roots:
        raise SettingsError("BSL_MCP_ALLOWED_ROOTS не содержит ни одного пути.")
    return tuple(roots)


def _fail_on() -> str:
    value = os.environ.get("BSL_MCP_FAIL_ON", "syntax").strip().lower()
    if value not in FAIL_ON_VALUES:
        allowed = ", ".join(FAIL_ON_VALUES)
        raise SettingsError(f"BSL_MCP_FAIL_ON должно быть одним из: {allowed}.")
    return value


def _optional_path(name: str) -> Path | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


@dataclass(frozen=True)
class Settings:
    """Параметры запуска. command_prefix используется только тестами."""

    java: str = "java"
    java_opts: tuple[str, ...] = ("-Dfile.encoding=UTF-8", "-Xmx768m")
    jar: Path | None = None
    timeout_seconds: float = 180.0
    allowed_roots: tuple[Path, ...] = ()
    max_code_bytes: int = 1_048_576
    max_file_bytes: int = 2_097_152
    max_files: int = 2000
    max_concurrent: int = 2
    fail_on: str = "syntax"
    compatibility_mode: str | None = None
    user_configuration: Path | None = None
    extra_exclude_dirs: tuple[str, ...] = ()
    command_prefix: tuple[str, ...] | None = None

    @property
    def exclude_dir_names(self) -> frozenset[str]:
        extra = {name.lower() for name in self.extra_exclude_dirs if name.strip()}
        return EXCLUDED_DIR_NAMES | extra

    def jar_version_hint(self) -> str | None:
        if self.jar is None:
            return None
        name = self.jar.name
        marker = "bsl-language-server-"
        if not name.startswith(marker):
            return None
        rest = name[len(marker) :]
        version = rest.split("-exec")[0].removesuffix(".jar")
        return version or None

    @classmethod
    def from_env(cls) -> Settings:
        extra_raw = os.environ.get("BSL_MCP_EXCLUDE_DIRS", "")
        extra = tuple(part.strip() for part in extra_raw.split(",") if part.strip())
        jar = _optional_path("BSL_LANGUAGE_SERVER_JAR")
        return cls(
            java=os.environ.get("BSL_JAVA", "java").strip() or "java",
            java_opts=_java_options(),
            jar=jar,
            timeout_seconds=_positive_float("BSL_MCP_TIMEOUT", 180.0),
            allowed_roots=_allowed_roots(),
            max_code_bytes=_positive_int("BSL_MCP_MAX_CODE_BYTES", 1_048_576),
            max_file_bytes=_positive_int("BSL_MCP_MAX_FILE_BYTES", 2_097_152),
            max_files=_positive_int("BSL_MCP_MAX_FILES", 2000),
            max_concurrent=_positive_int("BSL_MCP_MAX_CONCURRENT", 2),
            fail_on=_fail_on(),
            compatibility_mode=(os.environ.get("BSL_MCP_COMPATIBILITY_MODE") or "").strip() or None,
            user_configuration=_optional_path("BSL_LANGUAGE_SERVER_CONFIG"),
            extra_exclude_dirs=extra,
        )
