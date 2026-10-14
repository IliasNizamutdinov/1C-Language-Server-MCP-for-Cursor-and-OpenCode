"""Постоянные сведения о проверенной сборке анализатора и правилах адаптера."""

TESTED_BSL_VERSION = "1.0.7"
BSL_REPOSITORY = "https://github.com/1c-syntax/bsl-language-server"
BSL_DOCUMENTATION = "https://1c-syntax.github.io/bsl-language-server/"
BSL_RELEASE_PAGE = (
    "https://github.com/1c-syntax/bsl-language-server/releases/tag/v1.0.7"
)
BSL_JAR_NAME = "bsl-language-server-1.0.7-exec.jar"
BSL_JAR_URL = (
    "https://github.com/1c-syntax/bsl-language-server/releases/download/"
    "v1.0.7/bsl-language-server-1.0.7-exec.jar"
)
# Контрольная сумма официального актива bsl-language-server-1.0.7-exec.jar.
BSL_JAR_SHA256 = "9f62765edd344d66456da24c906eaf623a03c56e90e5aafee466200100909f64"
BSL_LICENSE = "LGPL-3.0-or-later"
BSL_COPYING_URL = (
    "https://github.com/1c-syntax/bsl-language-server/blob/v1.0.7/COPYING.md"
)

# Коды, которые BSL Language Server 1.0.7 возвращает для синтаксических дефектов.
# ParseError — ошибка разбора. SemicolonPresence — пропущенная точка с запятой:
# уровень Information, но для платформы 1С это синтаксическая ошибка.
SYNTAX_DIAGNOSTIC_CODES = frozenset({"ParseError", "SemicolonPresence"})
# Вызов члена платформы, которого нет в заданном режиме совместимости.
COMPATIBILITY_DIAGNOSTIC_CODES = frozenset({"UnavailableMemberCall"})

SUPPORTED_EXTENSIONS = frozenset({".bsl", ".os"})
BINARY_CONFIGURATION_EXTENSIONS = frozenset({".cf", ".cfe", ".epf", ".erf"})

# Каталоги, которые не обходятся при проверке проекта.
EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".svn",
        ".hg",
        ".idea",
        ".vs",
        ".vscode",
        ".cursor",
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
        "target",
        "build",
        "out",
        "dist",
        ".gradle",
        "bin",
        "obj",
        "tmp",
        "temp",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)

STATUS_TEXT = {
    "passed": "проверка пройдена",
    "failed": "проверка не пройдена",
    "not_performed": "проверка не выполнена",
    "limited": "проверка ограничена",
}

FAIL_ON_VALUES = ("syntax", "error", "warning", "any")

SCOPE_NOTE = (
    "Проверена синтаксическая корректность текста на языке 1С (BSL) или OneScript. "
    "Синтаксическая корректность не гарантирует правильность бизнес-логики, "
    "корректность запросов к базе, наличие объектов конфигурации, права доступа "
    "или успешное выполнение кода в платформе 1С."
)

FRAGMENT_LIMITATION = (
    "Проверен переданный текст, а не модуль в составе конфигурации. "
    "Не учитываются директивы компиляции модуля, другие процедуры, "
    "метаданные конфигурации и файл .bsl-language-server.json проекта. "
    "Такую проверку нельзя считать полноценной проверкой модуля."
)

ISOLATED_FILE_NOTE = (
    "Файл проверен по отдельной копии, без дерева метаданных конфигурации. "
    "Диагностики, которым нужны объекты конфигурации, могут отсутствовать или быть неполными."
)
