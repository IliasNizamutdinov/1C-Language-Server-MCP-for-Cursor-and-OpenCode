# Подключение к OpenCode

Сначала установите Java 21 или новее, Python, виртуальное окружение и BSL Language Server по [windows.md](windows.md). Java 17 этот анализатор не запускает: `java -version` должна показать 21 или выше.

Документация текущей версии: https://dev.opencode.ai/v2/docs/mcp-servers. Документация предыдущих версий: https://opencode.ai/docs/mcp-servers/. Это не формат Cursor `mcpServers`.

## Новая версия: настройка вручную

В текущей версии OpenCode имя сервера пишется внутри `mcp.servers`. Имя сразу под `mcp`, поле `enabled` и числовой `timeout` эта версия не использует.

Образец: [examples/opencode/opencode.v2.json](../examples/opencode/opencode.v2.json). Замените `C:\\Users\\USER` на свой каталог пользователя. В `BSL_MCP_ALLOWED_ROOTS` укажите каталог исходников 1С. Путь к Java в файл не записывайте: OpenCode подставляет переменную среды как `{env:BSL_JAVA}`. Переменная Windows `BSL_JAVA` должна указывать на `java.exe` из JDK 21 или новее.

Файл кладётся в корень проекта (`opencode.json`) либо в общую конфигурацию `%USERPROFILE%\.config\opencode\opencode.json`.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "bsl-syntax": {
        "type": "local",
        "command": [
          "C:\\Users\\USER\\1C-Language-Server-MCP-for-Cursor-and-OpenCode\\.venv\\Scripts\\python.exe",
          "-m",
          "bsl_mcp"
        ],
        "codemode": false,
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
}
```

`codemode` здесь `false`, чтобы инструменты остались в списке агента под именами `check_bsl_file`, `check_bsl_code`, `check_bsl_files` и `check_bsl_project`. Поле `protocol` не задавайте: адаптер отвечает на обычный handshake `initialize`. Чтобы временно не подключать сервер, добавьте `"disabled": true` внутрь объекта `bsl-syntax`.

Если старт Java на этой машине долгий, увеличьте ожидание подключения. Время задаётся объектом в миллисекундах, а не одним числом:

```json
"timeout": {
  "startup": 60000,
  "catalog": 30000
}
```

Длительность самой проверки по-прежнему ограничивает `BSL_MCP_TIMEOUT` в секундах.

Тот же файл можно создать командой, а переменные среды дописать вручную. Из каталога проекта 1С:

```powershell
opencode mcp add bsl-syntax -- "$env:USERPROFILE\1C-Language-Server-MCP-for-Cursor-and-OpenCode\.venv\Scripts\python.exe" -m bsl_mcp
```

Команда записывает сервер в проектный `opencode.json`. После неё откройте файл и вставьте блок `environment` из образца выше. Для всех проектов добавьте флаг `--global`.

## Где лежит конфигурация

- Проект: `opencode.json` в корне проекта.
- Общая конфигурация пользователя: `%USERPROFILE%\.config\opencode\opencode.json`.

Инструкции агента OpenCode читает из `AGENTS.md`. Файл `opencode.json` с полем `instructions` в актуальной документации V2 сам по себе может не подмешивать дополнительные файлы, поэтому рабочий текст кладите в `AGENTS.md`.

## Предыдущие версии

Образец: [examples/opencode/opencode.json](../examples/opencode/opencode.json). В них имя сервера лежит сразу внутри `mcp`, включение задаётся полем `enabled`, а `timeout` — одним числом миллисекунд. Замените `C:\\Users\\USER` на свой каталог пользователя.

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

Проверьте, что `command` — массив строк и путь к `python.exe` существует. В новой версии имя `bsl-syntax` должно быть внутри `mcp.servers`. Если оно лежит сразу под `mcp`, текущая версия сервер не подключает. Запустите ту же команду в PowerShell вручную: процесс должен молчать в stdout и ждать протокол MCP. Ошибки Java и Python печатаются в stderr. Список и состояние: `opencode mcp list` или команда `/mcps` внутри OpenCode.
