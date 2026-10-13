from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from bsl_mcp.analyzer import build_configuration
from bsl_mcp.config import Settings
from bsl_mcp.service import CheckService
from tests.conftest import service_with_fake, write_module


def test_missing_file_is_not_success(tmp_path: Path) -> None:
    result = service_with_fake(tmp_path).check_file(str(tmp_path / "missing.bsl"))
    assert result["status"] == "not_performed"
    assert result["syntax_status"] == "not_performed"
    assert result["files_checked"] == 0


def test_directory_is_not_a_single_file(tmp_path: Path) -> None:
    result = service_with_fake(tmp_path).check_file(str(tmp_path))
    assert result["status"] == "not_performed"
    assert "каталог" in result["summary"].lower()


def test_unsupported_extension(tmp_path: Path) -> None:
    target = tmp_path / "module.txt"
    target.write_text("А = 1;\n", encoding="utf-8")
    result = service_with_fake(tmp_path).check_file(str(target))
    assert result["status"] == "not_performed"
    assert "не поддерживается" in result["summary"]


def test_binary_configuration_is_not_claimed_as_checked(tmp_path: Path) -> None:
    target = tmp_path / "config.cf"
    target.write_bytes(b"not-a-source")
    result = service_with_fake(tmp_path).check_file(str(target))
    assert result["status"] == "not_performed"
    assert ".cf" in result["summary"]


def test_parent_path_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-from-service.bsl"
    outside.write_text("СИНТАКСИС\n", encoding="utf-8")
    try:
        result = service_with_fake(tmp_path).check_file(str(tmp_path / ".." / outside.name))
        assert result["status"] == "not_performed"
        assert result["syntax_error_count"] == 0
    finally:
        outside.unlink(missing_ok=True)


def test_fake_syntax_marker_fails_and_clean_code_is_limited_for_text(tmp_path: Path) -> None:
    broken = service_with_fake(tmp_path).check_code("СИНТАКСИС\n", "Module.bsl")
    assert broken["status"] == "failed"
    assert broken["syntax_error_count"] == 1
    assert broken["files"][0]["syntax_errors"][0]["line"] == 1
    clean = service_with_fake(tmp_path).check_code("А = 1;\n", "Module.bsl")
    assert clean["status"] == "limited"
    assert clean["syntax_status"] == "passed"
    assert clean["temporary_files_removed"] is True
    assert any("фрагмент" in item.lower() or "переданный текст" in item.lower() for item in clean["limitations"])


def test_existing_file_and_source_unchanged(tmp_path: Path) -> None:
    module = tmp_path / "Module.bsl"
    write_module(module, "А = 1;\n")
    before = module.read_bytes()
    result = service_with_fake(tmp_path).check_file(str(module))
    assert result["status"] == "passed"
    assert result["source_unchanged"] is True
    assert module.read_bytes() == before
    assert result["temporary_files_removed"] is True


def test_several_files_continue_after_one_error(tmp_path: Path) -> None:
    good = tmp_path / "Good.bsl"
    bad = tmp_path / "Bad.bsl"
    missing = tmp_path / "Missing.bsl"
    write_module(good, "А = 1;\n")
    write_module(bad, "СИНТАКСИС\n")
    result = service_with_fake(tmp_path).check_files(
        [str(good), str(bad), str(missing), str(tmp_path / "note.txt")]
    )
    assert result["status"] == "failed"
    by_name = {Path(str(item["file"])).name: item for item in result["files"]}
    assert by_name["Good.bsl"]["status"] == "passed"
    assert by_name["Bad.bsl"]["status"] == "failed"
    assert by_name["Missing.bsl"]["status"] == "not_performed"
    assert by_name["note.txt"]["status"] == "not_performed"


def test_project_skips_git_and_reports_broken_file(tmp_path: Path) -> None:
    write_module(tmp_path / "src" / "Good.bsl", "А = 1;\n")
    write_module(tmp_path / "src" / "Bad.bsl", "СИНТАКСИС\n")
    write_module(tmp_path / ".git" / "Hidden.bsl", "СИНТАКСИС\n")
    write_module(tmp_path / "readme.txt", "text")
    result = service_with_fake(tmp_path).check_project(str(tmp_path))
    names = [Path(str(item["file"])).name for item in result["files"]]
    assert "Hidden.bsl" not in names
    assert "Bad.bsl" in names
    assert result["excluded_directory_count"] >= 1
    assert result["status"] == "failed"


def test_project_without_sources(tmp_path: Path) -> None:
    result = service_with_fake(tmp_path).check_project(str(tmp_path))
    assert result["status"] == "not_performed"
    assert result["files_checked"] == 0


def test_missing_jar_is_not_success(tmp_path: Path) -> None:
    module = tmp_path / "Module.bsl"
    write_module(module, "А = 1;\n")
    settings = Settings(
        java="java",
        jar=tmp_path / "missing.jar",
        allowed_roots=(tmp_path,),
        timeout_seconds=5,
    )
    result = CheckService(settings).check_file(str(module))
    assert result["status"] == "not_performed"
    assert "не найден" in result["summary"]


def test_missing_analyzer_is_not_success(tmp_path: Path) -> None:
    module = tmp_path / "Module.bsl"
    write_module(module, "А = 1;\n")
    settings = Settings(
        java="definitely-missing-java",
        jar=tmp_path / "missing.jar",
        allowed_roots=(tmp_path,),
        timeout_seconds=5,
    )
    result = CheckService(settings).check_file(str(module))
    assert result["status"] == "not_performed"
    assert "Java" in result["summary"] or "анализатор" in result["summary"].lower()


def test_process_crash_is_not_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ANALYZER_MODE", "crash")
    module = tmp_path / "Module.bsl"
    write_module(module, "А = 1;\n")
    result = service_with_fake(tmp_path).check_file(str(module))
    assert result["status"] == "not_performed"
    assert result["syntax_status"] == "not_performed"


def test_bad_report_is_not_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ANALYZER_MODE", "bad-json")
    module = tmp_path / "Module.bsl"
    write_module(module, "А = 1;\n")
    result = service_with_fake(tmp_path).check_file(str(module))
    assert result["status"] == "not_performed"


def test_timeout_kills_child_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pid_file = tmp_path / "child.pid"
    monkeypatch.setenv("FAKE_ANALYZER_MODE", "sleep")
    monkeypatch.setenv("FAKE_CHILD_PID_FILE", str(pid_file))
    module = tmp_path / "Module.bsl"
    write_module(module, "А = 1;\n")
    result = service_with_fake(tmp_path, timeout_seconds=1).check_file(str(module))
    assert result["status"] == "not_performed"
    assert "время ожидания" in result["summary"]
    assert pid_file.is_file()
    child_pid = int(pid_file.read_text(encoding="utf-8"))
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)
    assert result["temporary_files_removed"] is True


def test_sequential_requests(tmp_path: Path) -> None:
    service = service_with_fake(tmp_path)
    first = service.check_code("А = 1;\n", "A.bsl")
    second = service.check_code("СИНТАКСИС\n", "B.bsl")
    assert first["status"] == "limited"
    assert second["status"] == "failed"


def test_parallel_requests(tmp_path: Path) -> None:
    service = service_with_fake(tmp_path, max_concurrent=2)
    results: list[dict[str, object]] = []

    def run(text: str, name: str) -> None:
        results.append(service.check_code(text, name))

    threads = [
        threading.Thread(target=run, args=("А = 1;\n", "A.os")),
        threading.Thread(target=run, args=("СИНТАКСИС\n", "B.os")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    statuses = sorted(str(item["status"]) for item in results)
    assert statuses == ["failed", "limited"]


def test_code_size_limit(tmp_path: Path) -> None:
    result = service_with_fake(tmp_path, max_code_bytes=4).check_code("А = 1;\n", "Module.bsl")
    assert result["status"] == "not_performed"


def test_send_errors_is_forced_off(tmp_path: Path) -> None:
    config = tmp_path / "custom.json"
    config.write_text('{"sendErrors": "send", "language": "en"}', encoding="utf-8")
    settings = Settings(user_configuration=config, allowed_roots=(tmp_path,))
    merged = build_configuration(settings, None)
    assert merged["sendErrors"] == "never"
    assert merged["language"] == "en"


def test_temp_files_do_not_remain(tmp_path: Path) -> None:
    import tempfile

    before = set(Path(tempfile.gettempdir()).glob("bsl-mcp-*"))
    service_with_fake(tmp_path).check_code("А = 1;\n", "Module.bsl")
    after = set(Path(tempfile.gettempdir()).glob("bsl-mcp-*"))
    assert after == before
