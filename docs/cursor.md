# Подключение к Cursor

Сначала выполните установку из [windows.md](windows.md). Нужна Java 21, не Java 17: `java -version` должна показать версию 21. Также нужны Python, виртуальное окружение и jar BSL Language Server 1.0.7.

## Где лежит конфигурация

- Проект: `.cursor/mcp.json` в корне открытой папки.
- Все проекты: `%USERPROFILE%\.cursor\mcp.json`.

Формат ниже соответствует документации Cursor: https://cursor.com/docs/mcp. Для локального сервера используются `type`, `command`, `args` и `env`. Переменные `${workspaceFolder}`, `${userHome}` и `${env:ИМЯ}` подставляет Cursor.

## Готовый фрагмент

Скопируйте [examples/cursor/mcp.json](../examples/cursor/mcp.json) и поправьте путь к `python.exe`, если виртуальное окружение лежит не в `%USERPROFILE%\.bsl-mcp\venv`.

```json
{
  "mcpServers": {
    "bsl-syntax": {
      "type": "stdio",
      "command": "${userHome}\\.bsl-mcp\\venv\\Scripts\\python.exe",
      "args": ["-m", "bsl_mcp"],
      "env": {
        "BSL_LANGUAGE_SERVER_JAR": "${userHome}\\.bsl-mcp\\bsl-language-server-1.0.7-exec.jar",
        "BSL_MCP_ALLOWED_ROOTS": "${workspaceFolder}",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

`BSL_MCP_ALLOWED_ROOTS` разрешает проверять только открытый проект. Сервер не обходит произвольные диски.

Если окружение создано внутри клона этого репозитория, `command` может указывать на `${workspaceFolder}\\.venv\\Scripts\\python.exe`, но тогда в `BSL_MCP_ALLOWED_ROOTS` нужно перечислить и каталог исходников 1С, и каталог инструмента, разделив их точкой с запятой.

## Перезапуск

Сохраните `mcp.json`. Откройте палитру команд и выполните перезагрузку окна либо полностью закройте Cursor и откройте снова. В Customize найдите сервер `bsl-syntax` и включите его, если он выключен.

## Как убедиться, что сервер подключён

1. Откройте настройки Cursor и раздел MCP, либо Customize.
2. У `bsl-syntax` должен быть статус подключения без ошибки запуска.
3. В списке инструментов должны быть `check_bsl_file`, `check_bsl_code`, `check_bsl_files`, `check_bsl_project`.

Если инструментов нет, откройте панель Output и выберите MCP Logs. Затем запустите ту же команду в PowerShell: путь к `python.exe`, аргумент `-m`, модуль `bsl_mcp`. Сообщения сервера идут в stderr и не должны попадать в stdout.

## Ручная проверка модуля

В чате агента:

`Проверь синтаксис файла src/CommonModules/Пример/Ext/Module.bsl, ничего в нём не меняя. Используй check_bsl_file.`

Агент передаёт путь инструменту. Инструмент копирует файл во временный каталог, запускает `java -jar ... analyze` и возвращает диагностику. Исходный файл не перезаписывается.

## Проверка кода, который написал агент

Попросите написать процедуру и сразу проверить её. Для ещё не сохранённого текста агент вызывает `check_bsl_code`. Статус `limited` при отсутствии синтаксических ошибок означает, что фрагмент проверен без конфигурации. Статус `passed` для такого вызова не используется намеренно.

## Правила проекта

Скопируйте [.cursor/rules/bsl-syntax-check.mdc](../.cursor/rules/bsl-syntax-check.mdc) в свой проект 1С по тому же пути `.cursor/rules/bsl-syntax-check.mdc`.

Правило просит агента проверять модуль после изменений. Оно не является хуком редактора и не гарантирует запуск. Отдельный автоматический хук Cursor в этом репозитории не включён: надёжный механизм, который удалось бы проверить здесь, не использовался.

## Если сервер не виден

Смотрите [troubleshooting.md](troubleshooting.md). Чаще всего неверен путь к `python.exe`, не задан jar или JSON содержит лишнюю запятую.
