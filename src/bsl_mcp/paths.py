"""Проверка путей. Инструменты не получают доступ за пределы разрешённых корней."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from bsl_mcp.constants import (
    BINARY_CONFIGURATION_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
)


class PathRejected(Exception):
    """Путь нельзя передать анализатору."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class ResolvedPath:
    requested: str
    path: Path
    extension: str


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _normalize(raw: str) -> Path:
    if "\x00" in raw:
        raise PathRejected("Путь содержит недопустимый нулевой символ.")
    text = raw.strip()
    if not text:
        raise PathRejected("Путь не указан.")
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return Path(os.path.normpath(str(candidate)))


def _realpath(path: Path) -> Path:
    if path.exists():
        return Path(os.path.realpath(path))
    parent = Path(os.path.realpath(path.parent))
    return parent / path.name


def resolve_inside_roots(raw: str, roots: tuple[Path, ...]) -> Path:
    """Вернуть канонический путь внутри одного из разрешённых корней."""

    normalized = _normalize(raw)
    real = _realpath(normalized)
    allowed = [Path(os.path.realpath(root)) for root in roots]
    if not any(_within(real, root) for root in allowed):
        raise PathRejected(
            "Путь находится за пределами разрешённой рабочей области. "
            "Проверять можно только каталоги из BSL_MCP_ALLOWED_ROOTS."
        )
    return real


def extension_of(path: Path) -> str:
    return path.suffix.lower()


def describe_extension(path: Path) -> str | None:
    """Вернуть текст отказа, если файл нельзя анализировать как исходник."""

    suffix = extension_of(path)
    if suffix in SUPPORTED_EXTENSIONS:
        return None
    if suffix in BINARY_CONFIGURATION_EXTENSIONS:
        return (
            f"Файл {path.name} имеет расширение {suffix}. "
            "Конфигурации и внешние обработки в двоичном виде напрямую не проверяются. "
            "Сначала выгрузите исходники в файлы .bsl и повторите проверку."
        )
    return (
        f"Расширение {suffix or '(без расширения)'} не поддерживается. "
        "Анализатор читает исходники .bsl и .os."
    )


def resolve_source_file(raw: str, roots: tuple[Path, ...]) -> ResolvedPath:
    path = resolve_inside_roots(raw, roots)
    if path.is_dir():
        raise PathRejected(
            "Указан каталог. Для одного модуля используйте файл .bsl или .os, "
            "для набора исходников — проверку проекта."
        )
    problem = describe_extension(path)
    if problem:
        raise PathRejected(problem)
    if not path.exists():
        raise PathRejected(f"Файл не найден: {path}.")
    if not path.is_file():
        raise PathRejected(f"Путь не является файлом: {path}.")
    if path.is_symlink():
        # resolve_inside_roots уже проверил цель ссылки.
        pass
    return ResolvedPath(requested=raw, path=path, extension=extension_of(path))


def resolve_project_dir(raw: str, roots: tuple[Path, ...]) -> Path:
    path = resolve_inside_roots(raw, roots)
    if not path.exists():
        raise PathRejected(f"Каталог не найден: {path}.")
    if not path.is_dir():
        raise PathRejected(
            "Для проверки проекта нужен каталог с исходниками, а не файл."
        )
    return path


def safe_code_file_name(file_name: str) -> str:
    """Имя временного файла: только базовое имя с расширением .bsl или .os."""

    if not isinstance(file_name, str):
        raise PathRejected("Имя файла должно быть строкой.")
    name = file_name.strip()
    if not name:
        raise PathRejected("Укажите file_name с расширением .bsl или .os.")
    if "\x00" in name or "/" in name or "\\" in name or ":" in name:
        raise PathRejected(
            "file_name должно быть именем файла без каталога, например Module.bsl."
        )
    if name in {".", ".."} or name.startswith("."):
        raise PathRejected("Некорректное имя временного файла.")
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise PathRejected(
            "Временный файл должен иметь расширение .bsl или .os. "
            f"Получено имя {file_name!r}."
        )
    if len(name) > 180:
        raise PathRejected("Имя временного файла слишком длинное.")
    return name


def relative_to_root(path: Path, root: Path) -> str:
    relative = path.resolve().relative_to(root.resolve())
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise PathRejected("Относительный путь выходит за пределы каталога.")
    return relative.as_posix()
