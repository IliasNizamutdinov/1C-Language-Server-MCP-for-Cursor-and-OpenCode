# Разработка

## Состав репозитория

- `src/bsl_mcp/` — MCP-инструменты, запуск анализатора, разбор отчёта, проверка путей.
- `tests/` — модульные тесты с подменой процесса и интеграционные тесты с реальным jar.
- `examples/` — модули 1С и образцы конфигурации Cursor и OpenCode.
- `docs/` — отдельные инструкции.
- `.cursor/rules/` — правило для агента Cursor.
- `AGENTS.md` — инструкция для OpenCode.
- `scripts/download_bsl_language_server.py` — загрузка официального jar и проверка SHA256.

Виртуальное окружение, jar и журналы в git не входят.

## Окружение разработчика

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:BSL_LANGUAGE_SERVER_JAR = "$env:USERPROFILE\.bsl-mcp\bsl-language-server-1.0.7-exec.jar"
python scripts\download_bsl_language_server.py $env:BSL_LANGUAGE_SERVER_JAR
```

На Linux и macOS активация другая: `source .venv/bin/activate`.

## Тесты

Модульные тесты не требуют Java:

```powershell
python -m pytest tests/test_paths.py tests/test_report.py tests/test_service.py
```

Интеграционные тесты запускают BSL Language Server. Без jar они завершаются ошибкой, а не тихим пропуском.

```powershell
$env:BSL_LANGUAGE_SERVER_JAR = "$env:USERPROFILE\.bsl-mcp\bsl-language-server-1.0.7-exec.jar"
python -m pytest
```

## Обновление анализатора

1. Откройте https://github.com/1c-syntax/bsl-language-server/releases.
2. Скачайте новый `bsl-language-server-<версия>-exec.jar`.
3. Укажите его в `BSL_LANGUAGE_SERVER_JAR`.
4. Выполните `java -jar <файл> version`.
5. Прогоните интеграционные тесты. Если изменились коды диагностики или формат `bsl-json.json`, обновите разбор в `src/bsl_mcp/report.py` и документацию.
6. Обновите версию, адрес, SHA256 и лицензионное уведомление, если лицензия изменилась.

## Обновление MCP SDK

Измените границу `mcp` в `pyproject.toml`, установите пакет и снова выполните тесты STDIO из `tests/test_integration.py`. Проверьте лицензию нового выпуска в метаданных пакета и поправьте `THIRD-PARTY-NOTICES.md`.

## Лицензии

Перед выпуском сверяйте `THIRD-PARTY-NOTICES.md` с `COPYING.md` выбранного тега BSL Language Server и с метаданными Python-зависимостей. Не копируйте jar в git.

## Изменения

Не добавляйте собственный парсер на регулярных выражениях. Не отправляйте исходники наружу: `sendErrors` остаётся `never`. Не логируйте текст модулей. Аргументы Java передаются списком, без `shell=True`.
