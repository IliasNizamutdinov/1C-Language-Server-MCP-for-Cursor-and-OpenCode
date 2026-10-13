"""Вызов BSL Language Server в режиме analyze. Код анализатора здесь не дублируется."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from bsl_mcp.config import Settings
from bsl_mcp.constants import (
    BSL_DOCUMENTATION,
    BSL_REPOSITORY,
    TESTED_BSL_VERSION,
)
from bsl_mcp.process import executable_exists, run_command


class AnalyzerNotReady(Exception):
    """Анализатор нельзя запустить. Это не успешная проверка."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class AnalyzerOutput:
    report: dict[str, object]
    exit_code: int
    duration_seconds: float
    stdout_tail: str
    stderr_tail: str


def _tail(text: str, limit: int = 2000) -> str:
    compact = text.strip()
    if len(compact) <= limit:
        return compact
    return compact[-limit:]


def default_configuration() -> dict[str, object]:
    return {
        "language": "ru",
        "sendErrors": "never",
        "v8platform": {"enabled": False},
        "diagnostics": {"mode": "ON"},
    }


def load_configuration_file(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise AnalyzerNotReady(f"Файл конфигурации анализатора не найден: {path}.")
    if path.stat().st_size > 1_048_576:
        raise AnalyzerNotReady(f"Файл конфигурации слишком большой: {path}.")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AnalyzerNotReady(
            f"Не удалось прочитать конфигурацию {path}: {error}."
        ) from error
    if not isinstance(data, dict):
        raise AnalyzerNotReady(f"Конфигурация {path} должна быть JSON-объектом.")
    return data


def deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = deep_merge(current, value)
        elif key == "excludePaths" and isinstance(current, list) and isinstance(value, list):
            combined: list[object] = []
            for item in [*current, *value]:
                if item not in combined:
                    combined.append(item)
            merged[key] = combined
        else:
            merged[key] = value
    return merged


def build_configuration(settings: Settings, project_root: Path | None) -> dict[str, object]:
    config = default_configuration()
    if settings.user_configuration is not None:
        config = deep_merge(config, load_configuration_file(settings.user_configuration))
    if project_root is not None:
        local = project_root / ".bsl-language-server.json"
        if local.is_file():
            config = deep_merge(config, load_configuration_file(local))
    # Отправка текстов ошибок разработчикам анализатора всегда выключена.
    config["sendErrors"] = "never"
    return config


class BslAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def describe(self) -> dict[str, object]:
        return {
            "name": "BSL Language Server",
            "role": "синтаксический и статический анализ кода 1С и OneScript",
            "tested_version": TESTED_BSL_VERSION,
            "jar_version_hint": self.settings.jar_version_hint(),
            "jar": str(self.settings.jar) if self.settings.jar else None,
            "mode": "analyze",
            "repository": BSL_REPOSITORY,
            "documentation": BSL_DOCUMENTATION,
        }

    def ensure_ready(self) -> None:
        if self.settings.command_prefix:
            program = self.settings.command_prefix[0]
            if not executable_exists(program) and not Path(program).is_file():
                raise AnalyzerNotReady(f"Тестовая команда анализатора не найдена: {program}.")
            return
        if not executable_exists(self.settings.java):
            raise AnalyzerNotReady(
                "Java не найдена. Для BSL Language Server нужна Java 17 или новее, "
                "рекомендуется Java 21. Установите Java и проверьте команду java -version. "
                "При необходимости укажите полный путь в переменной BSL_JAVA."
            )
        jar = self.settings.jar
        if jar is None:
            raise AnalyzerNotReady(
                "Не задан путь к BSL Language Server. Укажите переменную "
                "BSL_LANGUAGE_SERVER_JAR — полный путь к файлу "
                "bsl-language-server-<версия>-exec.jar."
            )
        if not jar.is_file():
            raise AnalyzerNotReady(f"Файл анализатора не найден: {jar}.")

    def command(self, source_dir: Path, output_dir: Path, configuration: Path) -> list[str]:
        analyze_args = [
            "analyze",
            "--silent",
            "--srcDir",
            str(source_dir),
            "--outputDir",
            str(output_dir),
            "--workspaceDir",
            str(source_dir),
            "--configuration",
            str(configuration),
            "--reporter",
            "json",
        ]
        if self.settings.command_prefix:
            return [*self.settings.command_prefix, *analyze_args]
        assert self.settings.jar is not None
        return [
            self.settings.java,
            *self.settings.java_opts,
            "-jar",
            str(self.settings.jar),
            *analyze_args,
        ]

    def analyze(self, source_dir: Path, output_dir: Path, configuration: Path) -> AnalyzerOutput:
        self.ensure_ready()
        argv = self.command(source_dir, output_dir, configuration)
        started = time.monotonic()
        try:
            completed = run_command(argv, self.settings.timeout_seconds, output_dir)
        except FileNotFoundError as error:
            raise AnalyzerNotReady(
                f"Не удалось запустить процесс анализатора: {error}."
            ) from error
        duration = round(time.monotonic() - started, 3)
        stdout_tail = _tail(completed.stdout)
        stderr_tail = _tail(completed.stderr)
        if completed.timed_out:
            raise AnalyzerNotReady(
                "Превышено время ожидания анализатора "
                f"({self.settings.timeout_seconds} с). Процесс и его дочерние процессы остановлены. "
                "Увеличьте BSL_MCP_TIMEOUT или сузьте набор файлов."
            )
        report_path = output_dir / "bsl-json.json"
        if completed.exit_code != 0 or not report_path.is_file():
            details = stderr_tail or stdout_tail or "анализатор не записал bsl-json.json"
            raise AnalyzerNotReady(
                "Анализатор завершился с ошибкой "
                f"(код {completed.exit_code}) и не дал пригодный отчёт. {details}"
            )
        try:
            report = json.loads(report_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise AnalyzerNotReady(f"Отчёт анализатора не удалось прочитать: {error}.") from error
        if not isinstance(report, dict):
            raise AnalyzerNotReady("Отчёт анализатора имеет неожиданный формат.")
        return AnalyzerOutput(report, completed.exit_code, duration, stdout_tail, stderr_tail)
