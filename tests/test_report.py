from bsl_mcp.analyzer import explain_java_too_old
from bsl_mcp.report import file_status, parse_report, public_diagnostic


def test_java_17_class_version_is_explained() -> None:
    message = (
        "Exception in thread \"main\" java.lang.UnsupportedClassVersionError: "
        "com/github/_1c_syntax/bsl/languageserver/MainApplication has been compiled "
        "by a more recent version of the Java Runtime (class file version 65.0), "
        "this version of the Java Runtime only recognizes class file versions up to 61.0"
    )
    explanation = explain_java_too_old("", message)
    assert explanation is not None
    assert "Java 21" in explanation
    assert "Java 17" in explanation
    assert explain_java_too_old("version: 1.0.7", "") is None


def test_positions_are_one_based() -> None:
    report = {
        "fileinfos": [
            {
                "path": "file:///workspace/Module.bsl",
                "mdoRef": "file:///tmp/Module.bsl",
                "diagnostics": [
                    {
                        "code": "ParseError",
                        "severity": "Error",
                        "message": "Ошибка разбора исходного кода",
                        "source": "bsl-language-server",
                        "range": {
                            "start": {"line": 1, "character": 4},
                            "end": {"line": 1, "character": 6},
                        },
                    }
                ],
            }
        ]
    }
    parsed = parse_report(report)
    diagnostic = parsed[0][2][0]
    assert diagnostic["line"] == 2
    assert diagnostic["column"] == 5
    assert diagnostic["syntax"] is True
    assert file_status(parsed[0][2], "syntax") == "failed"
    public = public_diagnostic(diagnostic)
    assert "syntax" not in public
    assert public["category"] == "синтаксическая ошибка"


def test_static_analysis_does_not_fail_syntax_policy() -> None:
    diagnostics = [
        {
            "code": "FunctionShouldHaveReturn",
            "severity": "Error",
            "message": "Функция не содержит Возврат",
            "syntax": False,
        }
    ]
    assert file_status(diagnostics, "syntax") == "passed"
    assert file_status(diagnostics, "error") == "failed"
