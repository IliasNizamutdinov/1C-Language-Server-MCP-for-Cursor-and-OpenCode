# Установка на Windows

Команды ниже рассчитаны на PowerShell. Выполняйте их по порядку и сверяйте ожидаемый результат.

## 1. Git

```powershell
git --version
```

Ожидается строка вида `git version 2.x`. Если команда не найдена, установите Git с https://git-scm.com/download/win и откройте новое окно PowerShell.

## 2. Java 21

Для файла `bsl-language-server-1.0.7-exec.jar` нужна Java 21 или новее. Эта сборка скомпилирована в class-файл версии 65.0. Java 17 понимает class-файлы только до версии 61.0 и завершается ошибкой `UnsupportedClassVersionError`. В документации BSL Language Server Java 17 указана как минимум для более ранних сборок, но проверенный jar 1.0.7 на Java 17 не запускается.

```powershell
java -version
```

Ожидается строка `openjdk version "21..."` или более новая. Версия `17` для этого jar не подходит.

Если Java 21 ещё нет, установите её с https://adoptium.net/temurin/releases/?version=21 или Microsoft Build of OpenJDK 21: https://learn.microsoft.com/java/openjdk/download. Через winget сначала посмотрите доступный пакет JDK 21 и установите его:

```powershell
winget search OpenJDK
```

После установки закройте PowerShell и откройте новое окно. Снова выполните `java -version`.

Если команда по-прежнему показывает 17, в `PATH` первой стоит старая Java. Найдите `java.exe` из JDK 21:

```powershell
where.exe java
Get-ChildItem "C:\Program Files\Microsoft","C:\Program Files\Eclipse Adoptium" -Recurse -Filter java.exe -ErrorAction SilentlyContinue
```

Дальше указывайте найденный файл явно. Путь ниже — образец, подставьте каталог, который показала предыдущая команда:

```powershell
$env:BSL_JAVA = "<полный путь к java.exe из JDK 21>"
& $env:BSL_JAVA -version
```

## 3. Python

Нужен Python 3.11 или новее. Проверен Python 3.12.

```powershell
python --version
```

Если команда не найдена, попробуйте `py -3 --version`. Установщик: https://www.python.org/downloads/windows/. При установке включите `Add python.exe to PATH`.

## 4. BSL Language Server

Адаптер не содержит jar-файл анализатора. Скачайте официальную сборку 1.0.7.

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.bsl-mcp" | Out-Null
$jar = "$env:USERPROFILE\.bsl-mcp\bsl-language-server-1.0.7-exec.jar"
Invoke-WebRequest -Uri "https://github.com/1c-syntax/bsl-language-server/releases/download/v1.0.7/bsl-language-server-1.0.7-exec.jar" -OutFile $jar
(Get-FileHash -Algorithm SHA256 $jar).Hash
```

Ожидаемый SHA256, без учёта регистра:

`9F62765EDD344D66456DA24C906EAF623A03C56E90E5AAFEE466200100909F64`

Проверка запуска:

```powershell
java -jar $jar version
```

Ожидается `version: 1.0.7`. Если вместо этого появляется `UnsupportedClassVersionError`, jar скачан правильно, но его запускает Java 17. Вернитесь к шагу 2 и добейтесь, чтобы `java -version` показывала 21. Если для JDK 21 задана переменная `BSL_JAVA`, проверяйте так:

```powershell
& $env:BSL_JAVA -jar $jar version
```

## 5. Клонирование и виртуальное окружение

```powershell
git clone https://github.com/IliasNizamutdinov/1C-Language-Server-MCP-for-Cursor-and-OpenCode.git
Set-Location .\1C-Language-Server-MCP-for-Cursor-and-OpenCode
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Если `python` не находится, замените его на `py -3`. После активации приглашение содержит `(.venv)`.

Если выполнение скриптов запрещено:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 6. Переменные среды

Для текущего окна:

```powershell
$env:BSL_LANGUAGE_SERVER_JAR = "$env:USERPROFILE\.bsl-mcp\bsl-language-server-1.0.7-exec.jar"
$env:BSL_MCP_ALLOWED_ROOTS = (Get-Location).Path
```

Чтобы сохранить путь к анализатору для новых окон текущего пользователя:

```powershell
[System.Environment]::SetEnvironmentVariable("BSL_LANGUAGE_SERVER_JAR", "$env:USERPROFILE\.bsl-mcp\bsl-language-server-1.0.7-exec.jar", "User")
```

После этого откройте новое окно PowerShell. `BSL_MCP_ALLOWED_ROOTS` для Cursor обычно задаётся в `mcp.json` как `${workspaceFolder}` и в постоянные переменные пользователя его лучше не записывать.

## 7. Первая проверка

Из корня клонированного репозитория, с активированным `.venv`:

```powershell
python -m bsl_mcp --check .\examples\bsl\valid-module.bsl
```

Ожидается JSON со `"status": "passed"` и `"syntax_error_count": 0`. Код выхода 0.

```powershell
python -m bsl_mcp --check .\examples\bsl\syntax-error.bsl
echo $LASTEXITCODE
```

Ожидается `"status": "failed"`, в `syntax_errors` код `ParseError`, строка 2. Код выхода 1.

Пустой файл `examples\bsl\empty.bsl` анализатор 1.0.7 считает синтаксически допустимым: статус `passed`.

Файл с пропущенной точкой с запятой `examples\bsl\missing-semicolon.bsl` получает статус `failed` и код `SemicolonPresence`.
