# Подключение к OpenCode

Сначала установите Java 21 или новее, Python, виртуальное окружение и BSL Language Server по [windows.md](windows.md). Java 17 этот анализатор не запускает: `java -version` должна показать 21 или выше.

Документация OpenCode: https://opencode.ai/docs/mcp-servers/. Локальный сервер задаётся в объекте `mcp` полем `type: "local"` и массивом `command`. Это не формат Cursor `mcpServers`.

## Где лежит конфигурация

- Проект: `opencode.json` в корне проекта.
- Общая конфигурация пользователя: `%USERPROFILE%\.config\opencode\opencode.json`.

Инструкции агента OpenCode читает из `AGENTS.md`. Файл `opencode.json` с полем `instructions` в актуальной документации V2 сам по себе может не подмешивать дополнительные файлы, поэтому рабочий текст кладите в `AGENTS.md`.

## Готовый фрагмент

Образец: [examples/opencode/opencode.json](../examples/opencode/opencode.json). Замените `C:\\Users\\USER` на свой каталог пользователя. В `BSL_MCP_ALLOWED_ROOTS` укажите каталог исходников 1С. Путь к Java в файл не записывайте: OpenCode подставляет переменную среды в виде `{env:BSL_JAVA}`. Это не запись Cursor `${env:BSL_JAVA}`. Сама переменная Windows `BSL_JAVA` должна указывать на `java.exe` из JDK 21 или новее.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "bsl-syntax": {
      "type": "local",
      "command": [
        "C:\\Users\\USER\\1C-Language-Server-MCP-for-Cursor-and-OpenCode\\.venv\\Scripts\\python.exe",
        "-m",
        "bsl_mcp"
      ],
      "enabled": true,
      "timeout": 15000,
      "environment": {
        "BSL_LANGUAGE_SERVER_JAR": "C:\\Users\\USER\\.bsl-mcp\\bsl-language-server-1.0.7-exec.jar",
        "BSL_JAVA": "{env:BSL_JAVA}",
        "BSL_MCP_ALLOWED_ROOTS": "C:\\Users\\USER\\src\\my-1c-project",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

`timeout` здесь — ожидание запуска и списка инструментов в миллисекундах. Проверка кода занимает дольше и ограничивается `BSL_MCP_TIMEOUT` (секунды, по умолчанию 180).

Поле `cwd` можно добавить, если сервер должен стартовать в каталоге проекта. Для путей в инструментах надёжнее передавать абсолютные пути.

## Проверка подключения

Перезапустите OpenCode в каталоге проекта. В подсказке к агенту напишите: `Покажи инструменты MCP bsl-syntax`. Должны быть доступны `check_bsl_file`, `check_bsl_code`, `check_bsl_files` и `check_bsl_project`.

Список серверов в терминале, если установлен интерфейс командной строки OpenCode:

```powershell
opencode mcp list
```

## Проверка файла и нового кода

`Проверь синтаксис Module.bsl через check_bsl_file и ничего в файле не меняй.`

`Напиши процедуру расчёта суммы, проверь текст через check_bsl_code до записи в файл, исправь синтаксические ошибки и повтори проверку.`

Для второго запроса нормальный успешный статус — `limited`, если анализатор не нашёл синтаксических ошибок. Это ограниченная проверка текста, не модуля внутри конфигурации.

## Инструкции проекта

Скопируйте [AGENTS.md](../AGENTS.md) в корень проекта 1С либо допишите его содержимое в уже существующий `AGENTS.md`.

Инструкция заставляет агента вызывать проверку после правок, но не гарантирует этого. Автоматический хук OpenCode, который сам запускал бы анализатор после каждого сохранения, в этом репозитории не настраивался.

## Если инструменты не появились

Проверьте, что `command` — массив строк, путь к `python.exe` существует, а `opencode.json` проходит разбор JSON. Запустите ту же команду в PowerShell вручную: процесс должен молчать в stdout и ждать протокол MCP. Ошибки Java и Python печатаются в stderr.
