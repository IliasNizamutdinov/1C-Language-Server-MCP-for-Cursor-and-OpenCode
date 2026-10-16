"""MCP-сервер STDIO для Cursor и OpenCode."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from bsl_mcp import __version__
from bsl_mcp.config import Settings, SettingsError
from bsl_mcp.service import CheckService

FailOn = Literal["syntax", "error", "warning", "any"]

INSTRUCTIONS = (
    "Локальная проверка синтаксиса модулей 1С (BSL) и OneScript через BSL Language Server. "
    "Инструменты не изменяют файлы и не отправляют код во внешние сервисы. "
    "После создания или правки модуля вызови проверку, исправь найденные синтаксические ошибки "
    "и повтори проверку. Статус passed означает, что анализатор не нашёл синтаксических ошибок; "
    "это не подтверждение бизнес-логики. check_bsl_code проверяет переданный текст отдельно "
    "от конфигурации, поэтому при отсутствии синтаксических ошибок его статус будет limited. "
    "Режим совместимости бери из Configuration.xml или параметра compatibility_mode "
    "(8.3.24, 8.5, Version8_3_24). Вызов члена платформы, которого нет в этом режиме, "
    "делает проверку не пройденной. Синтаксис «Параметр: Тип» анализатор 1.0.7 "
    "считает ошибкой разбора на любой версии и не проверяет соответствие значений типу."
)

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_server(settings: Settings) -> FastMCP:
    service = CheckService(settings)
    server = FastMCP(
        "bsl-syntax",
        instructions=INSTRUCTIONS,
        log_level="WARNING",
    )

    @server.tool(
        name="check_bsl_file",
        description=(
            "Проверить синтаксис одного существующего файла .bsl или .os через BSL Language Server. "
            "Файл только читается. Передай абсолютный путь. "
            "Используй после чтения модуля и после его изменения. "
            "Не используй для текста, который ещё не записан на диск: для него есть check_bsl_code. "
            "compatibility_mode — режим совместимости конфигурации, например 8.3.24, 8.5 или Version8_3_24. "
            "Если не передан, сервер ищет CompatibilityMode в Configuration.xml проекта."
        ),
        annotations=_READ_ONLY,
        structured_output=False,
    )
    async def check_bsl_file(
        path: str,
        fail_on: FailOn | None = None,
        compatibility_mode: str | None = None,
    ) -> str:
        payload = await asyncio.to_thread(service.check_file, path, fail_on, compatibility_mode)
        return _dump(payload)

    @server.tool(
        name="check_bsl_code",
        description=(
            "Проверить переданный текст модуля 1С или OneScript, не записывая его в проект. "
            "code — полный текст, file_name — имя вида Module.bsl или script.os без каталога. "
            "Проверка фрагмента ограничена: нет контекста конфигурации и остальных модулей. "
            "Если синтаксических ошибок нет, статус будет limited, а не passed. "
            "compatibility_mode задаёт версию платформы для этой проверки, потому что у текста нет Configuration.xml."
        ),
        annotations=_READ_ONLY,
        structured_output=False,
    )
    async def check_bsl_code(
        code: str,
        file_name: str,
        fail_on: FailOn | None = None,
        compatibility_mode: str | None = None,
    ) -> str:
        payload = await asyncio.to_thread(
            service.check_code,
            code,
            file_name,
            fail_on,
            compatibility_mode,
        )
        return _dump(payload)

    @server.tool(
        name="check_bsl_files",
        description=(
            "Проверить несколько указанных файлов .bsl или .os. "
            "Ошибка одного файла не останавливает проверку остальных. "
            "Отсутствующие и неподдерживаемые пути возвращаются отдельно. "
            "Исходники не изменяются."
        ),
        annotations=_READ_ONLY,
        structured_output=False,
    )
    async def check_bsl_files(
        paths: list[str],
        fail_on: FailOn | None = None,
        compatibility_mode: str | None = None,
    ) -> str:
        payload = await asyncio.to_thread(service.check_files, paths, fail_on, compatibility_mode)
        return _dump(payload)

    @server.tool(
        name="check_bsl_project",
        description=(
            "Проверить исходники .bsl и .os в указанном каталоге проекта. "
            "Каталог должен входить в BSL_MCP_ALLOWED_ROOTS. "
            "Служебные каталоги (.git, node_modules, сборки, виртуальные окружения) пропускаются. "
            "Двоичные .cf, .cfe, .epf и .erf не анализируются: нужна выгрузка исходников. "
            "Каталоги за пределами разрешённой области не обходятся. "
            "Режим совместимости читается из Configuration.xml или CompatibilityMode в каталоге. "
            "Параметр compatibility_mode его перекрывает."
        ),
        annotations=_READ_ONLY,
        structured_output=False,
    )
    async def check_bsl_project(
        path: str,
        fail_on: FailOn | None = None,
        compatibility_mode: str | None = None,
    ) -> str:
        payload = await asyncio.to_thread(service.check_project, path, fail_on, compatibility_mode)
        return _dump(payload)

    return server


def _configure_logging() -> None:
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


def run_server(settings: Settings | None = None) -> None:
    _configure_logging()
    selected = settings or Settings.from_env()
    build_server(selected).run(transport="stdio")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bsl-mcp",
        description="MCP-сервер синтаксической проверки кода 1С",
    )
    parser.add_argument("--check", metavar="FILE", help="Проверить один файл и напечатать JSON")
    parser.add_argument(
        "--check-project",
        metavar="DIR",
        help="Проверить каталог исходников и напечатать JSON",
    )
    parser.add_argument("--code-file", metavar="NAME", help="Имя файла для --code, например Module.bsl")
    parser.add_argument(
        "--compatibility-mode",
        metavar="VERSION",
        help="Режим совместимости, например 8.3.24, 8.5 или Version8_3_24",
    )
    parser.add_argument("--version", action="store_true", help="Показать версию адаптера")
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    _configure_logging()
    try:
        settings = Settings.from_env()
    except SettingsError as error:
        print(str(error), file=sys.stderr)
        return 2
    service = CheckService(settings)
    if args.check:
        payload = service.check_file(args.check, compatibility_mode=args.compatibility_mode)
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return _exit_code(payload)
    if args.check_project:
        payload = service.check_project(
            args.check_project,
            compatibility_mode=args.compatibility_mode,
        )
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return _exit_code(payload)
    if args.code_file:
        code = sys.stdin.read()
        payload = service.check_code(
            code,
            args.code_file,
            compatibility_mode=args.compatibility_mode,
        )
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return _exit_code(payload)
    try:
        run_server(settings)
    except SettingsError as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


def _exit_code(payload: dict[str, Any]) -> int:
    status = payload.get("status")
    if status == "passed":
        return 0
    if status == "limited":
        return 0
    if status == "failed":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
