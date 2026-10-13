from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from bsl_mcp.constants import BSL_JAR_SHA256, TESTED_BSL_VERSION

pytestmark = pytest.mark.integration

JAR = Path(os.environ.get("BSL_LANGUAGE_SERVER_JAR", "/tmp/bsl-ls/bsl-language-server-exec.jar"))


def require_analyzer() -> None:
    if not JAR.is_file():
        pytest.fail(
            "Интеграционный тест не запущен: нет BSL Language Server. "
            f"Ожидался файл {JAR}."
        )


def real_settings(root: Path, **overrides: object):
    from bsl_mcp.config import Settings

    return Settings(
        java=str(overrides.get("java", "java")),
        jar=Path(str(overrides.get("jar", JAR))),
        timeout_seconds=float(overrides.get("timeout_seconds", 180)),
        allowed_roots=(root,),
        max_files=int(overrides.get("max_files", 50)),
        java_opts=("-Dfile.encoding=UTF-8", "-Xmx512m"),
        user_configuration=overrides.get("user_configuration"),  # type: ignore[arg-type]
    )


def service(root: Path, **overrides: object):
    from bsl_mcp.service import CheckService

    return CheckService(real_settings(root, **overrides))


@pytest.fixture(autouse=True)
def analyzer_available() -> None:
    require_analyzer()


def test_jar_matches_published_checksum() -> None:
    import hashlib

    digest = hashlib.sha256(JAR.read_bytes()).hexdigest()
    assert digest == BSL_JAR_SHA256


def test_real_valid_module_passes(tmp_path: Path) -> None:
    module = tmp_path / "Valid.bsl"
    module.write_text(
        "Процедура РассчитатьСумму(СтрокаТаблицы) Экспорт\n"
        "\tСтрокаТаблицы.Сумма = СтрокаТаблицы.Количество * СтрокаТаблицы.Цена;\n"
        "КонецПроцедуры\n",
        encoding="utf-8",
    )
    before = module.read_bytes()
    result = service(tmp_path).check_file(str(module))
    assert result["status"] == "passed", result["summary"]
    assert result["syntax_status"] == "passed"
    assert result["syntax_error_count"] == 0
    assert result["source_unchanged"] is True
    assert module.read_bytes() == before
    assert result["analyzer"]["tested_version"] == TESTED_BSL_VERSION
    assert result["temporary_files_removed"] is True


def test_real_parse_error_has_location(tmp_path: Path) -> None:
    module = tmp_path / "Broken.bsl"
    module.write_text(
        "Процедура Пример()\n\tА = (1 + );\nКонецПроцедуры\n",
        encoding="utf-8",
    )
    result = service(tmp_path).check_file(str(module))
    assert result["status"] == "failed"
    errors = result["files"][0]["syntax_errors"]
    assert errors
    assert errors[0]["code"] == "ParseError"
    assert errors[0]["line"] == 2
    assert errors[0]["column"] >= 1
    assert "Ошибка разбора" in errors[0]["message"]
    assert result["status"] != "passed"


def test_real_missing_semicolon_fails(tmp_path: Path) -> None:
    module = tmp_path / "Semi.bsl"
    module.write_text(
        'Процедура Пример()\n\tСообщить("Привет")\nКонецПроцедуры\n',
        encoding="utf-8",
    )
    result = service(tmp_path).check_file(str(module))
    assert result["status"] == "failed"
    codes = [item["code"] for item in result["files"][0]["syntax_errors"]]
    assert "SemicolonPresence" in codes


def test_real_empty_file_passes(tmp_path: Path) -> None:
    module = tmp_path / "Empty.bsl"
    module.write_text("", encoding="utf-8")
    result = service(tmp_path).check_file(str(module))
    assert result["status"] == "passed"
    assert result["syntax_error_count"] == 0


def test_real_code_text_and_fragment_limit(tmp_path: Path) -> None:
    broken = service(tmp_path).check_code("А = (1 + );\n", "Fragment.bsl")
    assert broken["status"] == "failed"
    assert broken["syntax_error_count"] >= 1
    clean = service(tmp_path).check_code(
        "Процедура Пример()\n\tА = 1;\nКонецПроцедуры\n",
        "Module.bsl",
    )
    assert clean["status"] == "limited"
    assert clean["syntax_status"] == "passed"
    assert clean["temporary_files_removed"] is True


def test_real_project_skips_git(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Good.bsl").write_text(
        "Процедура Пример()\n\tА = 1;\nКонецПроцедуры\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "Bad.bsl").write_text(
        "Процедура Пример()\n\tА = (1 + );\nКонецПроцедуры\n",
        encoding="utf-8",
    )
    hidden = tmp_path / ".git" / "Hidden.bsl"
    hidden.parent.mkdir()
    hidden.write_text("Процедура Пример()\n\tА = (1 + );\nКонецПроцедуры\n", encoding="utf-8")
    (tmp_path / "note.txt").write_text("не модуль", encoding="utf-8")
    before = {
        path: path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    result = service(tmp_path).check_project(str(tmp_path))
    names = [Path(str(item["file"])).name for item in result["files"]]
    assert "Hidden.bsl" not in names
    assert result["status"] == "failed"
    assert result["excluded_directory_count"] >= 1
    for path, content in before.items():
        assert path.read_bytes() == content


def test_real_static_error_does_not_mask_syntax_success(tmp_path: Path) -> None:
    module = tmp_path / "NoReturn.bsl"
    module.write_text("Функция Пример()\n\tА = 1;\nКонецФункции\n", encoding="utf-8")
    result = service(tmp_path).check_file(str(module))
    assert result["syntax_status"] == "passed"
    assert result["status"] == "passed"
    codes = [item["code"] for item in result["files"][0]["diagnostics"]]
    assert "FunctionShouldHaveReturn" in codes
    strict = service(tmp_path).check_file(str(module), fail_on="error")
    assert strict["status"] == "failed"
    assert strict["syntax_status"] == "passed"


def test_real_stray_endprocedure_is_not_reported(tmp_path: Path) -> None:
    # Зафиксированное ограничение BSL Language Server 1.0.7:
    # одиночный «КонецПроцедуры» не получает ParseError.
    module = tmp_path / "OnlyEnd.bsl"
    module.write_text("КонецПроцедуры\n", encoding="utf-8")
    result = service(tmp_path).check_file(str(module))
    assert result["status"] == "passed"
    assert result["syntax_error_count"] == 0


def test_stdio_lists_tools_and_checks_code_twice() -> None:
    import anyio
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    env = os.environ.copy()
    env["BSL_LANGUAGE_SERVER_JAR"] = str(JAR)
    env["BSL_MCP_ALLOWED_ROOTS"] = "/tmp"
    env["BSL_JAVA_OPTS"] = "-Dfile.encoding=UTF-8 -Xmx512m"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    async def scenario() -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "bsl_mcp"],
            env=env,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = sorted(tool.name for tool in tools.tools)
                assert names == [
                    "check_bsl_code",
                    "check_bsl_file",
                    "check_bsl_files",
                    "check_bsl_project",
                ]
                first = await session.call_tool(
                    "check_bsl_code",
                    {"code": "Процедура Пример()\n\tА = 1;\nКонецПроцедуры\n", "file_name": "Module.bsl"},
                )
                second = await session.call_tool(
                    "check_bsl_code",
                    {"code": "Процедура Пример()\n\tА = (1 + );\nКонецПроцедуры\n", "file_name": "Broken.bsl"},
                )
        return first, second

    first, second = anyio.run(scenario)
    first_payload = json.loads(first.content[0].text)
    second_payload = json.loads(second.content[0].text)
    assert first_payload["status"] == "limited"
    assert first_payload["syntax_status"] == "passed"
    assert second_payload["status"] == "failed"
    assert second_payload["files"][0]["syntax_errors"][0]["line"] == 2
