from pathlib import Path

import pytest

from bsl_mcp.compatibility import (
    CompatibilityError,
    find_project_compatibility,
    from_request,
    normalize_target_version,
    type_check_info,
)
from bsl_mcp.report import file_status, parse_report
from tests.conftest import service_with_fake, write_module


def test_version_names() -> None:
    assert normalize_target_version("8.3.24") == "8.3.24"
    assert normalize_target_version("8.5") == "8.5"
    assert normalize_target_version("Version8_3_10") == "8.3.10"
    assert normalize_target_version("Version8_5_1") == "8.5.1"
    assert normalize_target_version("DontUse") is None
    with pytest.raises(CompatibilityError):
        normalize_target_version("платформа")


def test_configuration_xml_is_preferred_over_nothing(tmp_path: Path) -> None:
    config = tmp_path / "Configuration.xml"
    config.write_text(
        "<Configuration><CompatibilityMode>Version8_3_10</CompatibilityMode></Configuration>",
        encoding="utf-8",
    )
    found = find_project_compatibility(tmp_path / "Module.bsl", (tmp_path,))
    assert found is not None
    assert found.applied is True
    assert found.target_version == "8.3.10"
    assert found.source_path == str(config)


def test_explicit_mode_overrides_configuration_file(tmp_path: Path) -> None:
    (tmp_path / "Configuration.xml").write_text(
        "<CompatibilityMode>Version8_3_10</CompatibilityMode>",
        encoding="utf-8",
    )
    write_module(tmp_path / "Module.bsl", "А = 1;\n")
    result = service_with_fake(tmp_path).check_file(
        str(tmp_path / "Module.bsl"),
        compatibility_mode="8.5",
    )
    assert result["status"] == "passed"
    assert result["compatibility"]["target_version"] == "8.5"
    assert result["compatibility"]["source"] == "параметр инструмента"
    assert result["type_check"]["method_variable_types"] is False


def test_invalid_mode_is_not_a_successful_check(tmp_path: Path) -> None:
    write_module(tmp_path / "Module.bsl", "А = 1;\n")
    result = service_with_fake(tmp_path).check_file(
        str(tmp_path / "Module.bsl"),
        compatibility_mode="платформа",
    )
    assert result["status"] == "not_performed"
    assert result["files_checked"] == 0


def test_type_annotation_is_reported_but_not_checked(tmp_path: Path) -> None:
    result = service_with_fake(tmp_path).check_code(
        'Процедура Пример(&Тип("Число") Количество)\nКонецПроцедуры\n',
        "Module.bsl",
        compatibility_mode="8.5",
    )
    assert result["type_check"]["annotations_found"] is True
    assert result["type_check"]["performed"] is False


def test_unavailable_member_fails_syntax_policy() -> None:
    report = {
        "fileinfos": [
            {
                "path": "file:///workspace/Module.bsl",
                "mdoRef": "file:///tmp/Module.bsl",
                "diagnostics": [
                    {
                        "code": "UnavailableMemberCall",
                        "severity": "Error",
                        "message": "Метод доступен только начиная с версии платформы 8.3.18",
                        "source": "bsl-language-server",
                        "range": {
                            "start": {"line": 1, "character": 7},
                            "end": {"line": 1, "character": 18},
                        },
                    }
                ],
            }
        ]
    }
    diagnostic = parse_report(report)[0][2][0]
    assert diagnostic["category"] == "несовместимость с режимом совместимости"
    assert diagnostic["line"] == 2
    assert file_status(parse_report(report)[0][2], "syntax") == "failed"
    mode = from_request("Version8_3_10", "тест")
    assert mode.applied is True
    assert type_check_info(["А = 1;"])["annotations_found"] is False
