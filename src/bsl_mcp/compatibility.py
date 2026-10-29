"""Режим совместимости конфигурации 1С для проверки синтаксиса.

Строка версии передаётся в BSL Language Server как v8platform.targetVersion.
Сам разбор по-прежнему делает анализатор.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")
_ENUM_RE = re.compile(r"^Version(\d+)_(\d+)(?:_(\d+))?$", re.IGNORECASE)
_TAG_RE = re.compile(
    r"<(?:[\w.]+:)?CompatibilityMode>\s*([^<]+?)\s*</(?:[\w.]+:)?CompatibilityMode>",
    re.IGNORECASE,
)
_DONT_USE = {"dontuse", "неиспользовать", "latest", "none"}
_CONFIG_NAMES = (
    "Configuration.xml",
    "ConfigurationExtension.xml",
    "Configuration/Configuration.mdo",
    "src/Configuration/Configuration.mdo",
    "src/cf/Configuration.xml",
    "cf/Configuration.xml",
    "src/Configuration.xml",
)
_MAX_CONFIG_BYTES = 8_000_000


class CompatibilityError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class CompatibilityMode:
    """Какой режим передан анализатору."""

    applied: bool
    target_version: str | None
    requested: str | None
    source: str
    source_path: str | None
    note: str

    def as_dict(self) -> dict[str, object]:
        return {
            "applied": self.applied,
            "target_version": self.target_version,
            "requested": self.requested,
            "source": self.source,
            "source_path": self.source_path,
            "note": self.note,
        }


def not_set() -> CompatibilityMode:
    return CompatibilityMode(
        applied=False,
        target_version=None,
        requested=None,
        source="не задан",
        source_path=None,
        note=(
            "Режим совместимости не задан. BSL Language Server проверяет члены платформы "
            "как для самой свежей известной ему версии: отличие синтаксиса 8.3 и 8.5 "
            "в этом запуске не учитывается. Укажите compatibility_mode, переменную "
            "BSL_MCP_COMPATIBILITY_MODE или положите CompatibilityMode в Configuration.xml."
        ),
    )


def normalize_target_version(raw: str) -> str | None:
    """Вернуть targetVersion для анализатора либо None для DontUse.

    None означает «самая свежая платформа», как режим DontUse в конфигурации.
    """

    text = raw.strip()
    if not text:
        raise CompatibilityError("Режим совместимости пустой.")
    if text.lower() in _DONT_USE:
        return None
    version_match = _VERSION_RE.match(text)
    if version_match:
        return _join_version(version_match.group(1), version_match.group(2), version_match.group(3))
    enum_match = _ENUM_RE.match(text)
    if enum_match:
        return _join_version(enum_match.group(1), enum_match.group(2), enum_match.group(3))
    raise CompatibilityError(
        "Непонятный режим совместимости "
        f"{raw!r}. Ожидается версия вроде 8.3.24, 8.5 или значение "
        "Version8_3_24 из Configuration.xml. DontUse означает самую свежую платформу."
    )


def from_request(raw: str, source: str, source_path: str | None = None) -> CompatibilityMode:
    target = normalize_target_version(raw)
    if target is None:
        return CompatibilityMode(
            applied=False,
            target_version=None,
            requested=raw.strip(),
            source=source,
            source_path=source_path,
            note=(
                "Режим совместимости DontUse: анализатор считает целевой самую свежую платформу. "
                "Конструкции, которые есть только в старых режимах, отдельно не отсекаются."
            ),
        )
    return CompatibilityMode(
        applied=True,
        target_version=target,
        requested=raw.strip(),
        source=source,
        source_path=source_path,
        note=(
            f"Проверка членов платформы выполняется для версии {target}. "
            "Вызов метода, которого нет в этом режиме, анализатор возвращает как "
            "UnavailableMemberCall, и проверка считается не пройденной."
        ),
    )


def read_compatibility_file(path: Path) -> str | None:
    if not path.is_file() or path.is_symlink():
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size > _MAX_CONFIG_BYTES:
        return None
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    match = _TAG_RE.search(text)
    if not match:
        return None
    return match.group(1).strip()


def find_project_compatibility(start: Path, allowed_roots: tuple[Path, ...]) -> CompatibilityMode | None:
    """Найти CompatibilityMode, поднимаясь от файла или каталога к разрешённому корню."""

    current = start if start.is_dir() else start.parent
    allowed = [Path(os.path.realpath(root)) for root in allowed_roots]
    while True:
        real_current = Path(os.path.realpath(current))
        if not any(_is_relative_to(real_current, root) for root in allowed):
            return None
        for relative in _CONFIG_NAMES:
            candidate = current / relative
            value = read_compatibility_file(candidate)
            if value:
                return from_request(value, "файл конфигурации", str(candidate))
        bsl_config = current / ".bsl-language-server.json"
        target = target_version_from_bsl_config(bsl_config)
        if target:
            return from_request(target, "конфигурация анализатора", str(bsl_config))
        if any(real_current == root for root in allowed) or current.parent == current:
            return None
        current = current.parent


def target_version_from_bsl_config(path: Path) -> str | None:
    if not path.is_file() or path.stat().st_size > 1_048_576:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    platform = data.get("v8platform")
    if not isinstance(platform, dict):
        return None
    version = platform.get("targetVersion")
    if not isinstance(version, str) or not version.strip():
        return None
    return version.strip()


def _join_version(major: str, minor: str, patch: str | None) -> str:
    if patch is None:
        return f"{int(major)}.{int(minor)}"
    return f"{int(major)}.{int(minor)}.{int(patch)}"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


_TYPE_ANNOTATION_RE = re.compile(r"&(?:Тип|Type)\b", re.IGNORECASE)

TYPE_CHECK_NOTE = (
    "Типы параметров и переменных внутри процедур и функций BSL Language Server 1.0.7 "
    "не сверяет с присваиваниями и вызовами. Запись вида «Параметр: Число» и «Перем Имя: Число» "
    "этот анализатор считает ошибкой разбора на любой версии платформы, и для 8.3, и для 8.5. "
    "Аннотация &Тип(...) разбирается как аннотация, но не становится проверкой типа. "
    "Учитывается другое: при заданном режиме совместимости анализатор отклоняет вызов члена платформы, "
    "которого нет в этой версии."
)


def type_check_info(texts: list[str]) -> dict[str, object]:
    found = any(_TYPE_ANNOTATION_RE.search(text) for text in texts)
    return {
        "performed": False,
        "method_variable_types": False,
        "annotations_found": found,
        "note": TYPE_CHECK_NOTE,
    }
