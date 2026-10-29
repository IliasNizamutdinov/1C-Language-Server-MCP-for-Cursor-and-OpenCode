"""Разбор отчёта BSL Language Server и решение о статусе проверки."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from bsl_mcp.constants import (
    COMPATIBILITY_DIAGNOSTIC_CODES,
    STATUS_TEXT,
    SYNTAX_DIAGNOSTIC_CODES,
)


def file_uri_to_path(value: str) -> Path | None:
    if not value:
        return None
    if not value.lower().startswith("file:"):
        return Path(value)
    parsed = urlparse(value)
    path = unquote(parsed.path)
    if len(path) >= 3 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    if not path:
        return None
    return Path(path)


def _display_position(value: object) -> int | None:
    if not isinstance(value, int) or value < 0:
        return None
    return value + 1


def _category(code: str, severity: str, syntax: bool) -> str:
    if code in COMPATIBILITY_DIAGNOSTIC_CODES:
        return "несовместимость с режимом совместимости"
    if syntax:
        return "синтаксическая ошибка"
    return {
        "Error": "ошибка статического анализа",
        "Warning": "предупреждение",
        "Information": "информация",
        "Hint": "подсказка",
    }.get(severity, "диагностика")


def _diagnostic(raw: object, file_name: str) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    code = str(raw.get("code") or "")
    severity = str(raw.get("severity") or "")
    message = str(raw.get("message") or "")
    source = str(raw.get("source") or "bsl-language-server")
    range_info = raw.get("range") if isinstance(raw.get("range"), dict) else {}
    start = range_info.get("start") if isinstance(range_info.get("start"), dict) else {}
    end = range_info.get("end") if isinstance(range_info.get("end"), dict) else {}
    syntax = code in SYNTAX_DIAGNOSTIC_CODES or code in COMPATIBILITY_DIAGNOSTIC_CODES
    description = raw.get("codeDescription")
    documentation = None
    if isinstance(description, dict) and isinstance(description.get("href"), str):
        documentation = description["href"]
    return {
        "file": file_name,
        "line": _display_position(start.get("line")),
        "column": _display_position(start.get("character")),
        "end_line": _display_position(end.get("line")),
        "end_column": _display_position(end.get("character")),
        "category": _category(code, severity, syntax),
        "severity": severity,
        "code": code,
        "message": message,
        "source": source,
        "documentation": documentation,
        "syntax": syntax,
    }


def parse_report(report: object) -> list[tuple[Path | None, str, list[dict[str, object]]]]:
    """Вернуть список (путь из mdoRef, относительный путь отчёта, диагностики)."""

    if not isinstance(report, dict):
        raise ValueError("Отчёт анализатора не является объектом JSON.")
    infos = report.get("fileinfos")
    if not isinstance(infos, list):
        raise ValueError("В отчёте анализатора нет массива fileinfos.")
    parsed: list[tuple[Path | None, str, list[dict[str, object]]]] = []
    for info in infos:
        if not isinstance(info, dict):
            continue
        raw_path = str(info.get("path") or "")
        relative = raw_path
        marker = "file:///workspace/"
        if raw_path.startswith(marker):
            relative = raw_path[len(marker) :]
        mdo = file_uri_to_path(str(info.get("mdoRef") or ""))
        diagnostics_raw = info.get("diagnostics") or []
        diagnostics: list[dict[str, object]] = []
        if isinstance(diagnostics_raw, list):
            for item in diagnostics_raw:
                diagnostic = _diagnostic(item, relative or (mdo.name if mdo else ""))
                if diagnostic is not None:
                    diagnostics.append(diagnostic)
        parsed.append((mdo, relative, diagnostics))
    return parsed


def is_blocking(diagnostic: dict[str, object], fail_on: str) -> bool:
    if diagnostic.get("syntax") is True and fail_on in {"syntax", "error", "warning", "any"}:
        return True
    severity = str(diagnostic.get("severity") or "")
    if fail_on == "syntax":
        return False
    if fail_on == "error":
        return severity == "Error"
    if fail_on == "warning":
        return severity in {"Error", "Warning"}
    if fail_on == "any":
        return True
    return False


def split_diagnostics(
    diagnostics: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    syntax = [item for item in diagnostics if item.get("syntax") is True]
    other = [item for item in diagnostics if item.get("syntax") is not True]
    return syntax, other


def public_diagnostic(diagnostic: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in diagnostic.items() if key != "syntax"}


def file_status(diagnostics: list[dict[str, object]], fail_on: str) -> str:
    if any(is_blocking(item, fail_on) for item in diagnostics):
        return "failed"
    return "passed"


def status_text(status: str) -> str:
    return STATUS_TEXT.get(status, status)


def summarize(
    status: str,
    syntax_error_count: int,
    analysis_error_count: int,
    warning_count: int,
    files_checked: int,
) -> str:
    if status == "not_performed":
        return "Проверка не выполнена. Анализатор не подтвердил результат."
    parts = [
        f"Проверено файлов: {files_checked}.",
        f"Синтаксических ошибок и несовместимостей с режимом: {syntax_error_count}.",
    ]
    if analysis_error_count or warning_count:
        parts.append(
            "Статический анализ: "
            f"ошибок {analysis_error_count}, предупреждений {warning_count}."
        )
    parts.append(f"Статус: {status_text(status)}.")
    if status == "passed":
        parts.append("Синтаксических ошибок, препятствующих проверке, не обнаружено.")
    elif status == "limited":
        parts.append(
            "Синтаксических ошибок в проверенном объёме не обнаружено, "
            "но проверка ограничена и не заменяет проверку модуля в конфигурации."
        )
    elif status == "failed":
        parts.append("Есть диагностики, из-за которых проверка не пройдена.")
    return " ".join(parts)
