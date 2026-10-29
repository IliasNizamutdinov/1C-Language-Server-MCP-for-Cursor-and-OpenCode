# Установка на Windows

Команды ниже рассчитаны на PowerShell. Выполняйте их по порядку и сверяйте ожидаемый результат.

## 1. Git

```powershell
git --version
```

Ожидается строка вида `git version 2.x`. Если команда не найдена, установите Git с https://git-scm.com/download/win и откройте новое окно PowerShell.

## 2. Java 21 или новее

Для файла `bsl-language-server-1.0.7-exec.jar` нужна Java 21 или любая более новая версия: 22, 23, 25 и дальше. Более новая Java запускает этот jar. Java 17 и более старые не подходят: сборка скомпилирована в class-файл версии 65.0, а Java 17 понимает class-файлы только до версии 61.0 и завершается ошибкой `UnsupportedClassVersionError`.

Установите Microsoft Build of OpenJDK. Ссылка открывается в отдельном окне: <a href="https://learn.microsoft.com/java/openjdk/download" target="_blank" rel="noopener noreferrer">https://learn.microsoft.com/java/openjdk/download</a>. На странице выберите JDK 21 или новее для Windows x64 и установите его.

Проверьте, какая Java сейчас первая в системе:

```powershell
java -version
```

Если в первой строке версия 21 или выше, этот шаг уже выполнен. Тогда запомните путь к этой `java.exe` и сохраните его:

```powershell
$env:BSL_JAVA = (Get-Command java).Source
[Environment]::SetEnvironmentVariable("BSL_JAVA", $env:BSL_JAVA, "User")
& $env:BSL_JAVA -version
```

Ожидается строка `openjdk version "21..."` или старше, например `25...`.

Если Java уже установлена, но `java -version` показывает 17 или другую версию ниже 21, менять нужно путь, а не скачанный jar. Команда `java` в этом случае берёт старую версию, потому что её каталог стоит в `PATH` раньше нового. После установки JDK 21 или новее выполните в том же окне:

```powershell
$jdk = Get-ChildItem "C:\Program Files\Microsoft" -Directory -Filter "jdk-*" -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^jdk-(\d+)' -and [int]$Matches[1] -ge 21 } |
  Sort-Object { if ($_.Name -match '^jdk-(\d+)') { [int]$Matches[1] } } -Descending |
  Select-Object -First 1
if (-not $jdk) {
  throw "В C:\Program Files\Microsoft нет JDK 21 или новее. Установите его по ссылке выше и откройте новое окно PowerShell."
}
$env:BSL_JAVA = Join-Path $jdk.FullName "bin\java.exe"
[Environment]::SetEnvironmentVariable("BSL_JAVA", $env:BSL_JAVA, "User")
$bin = Split-Path $env:BSL_JAVA
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "$bin*") {
  [Environment]::SetEnvironmentVariable("Path", "$bin;$userPath", "User")
}
& $env:BSL_JAVA -version
```

Ожидается `openjdk version "21..."` или новее. Закройте PowerShell и откройте новое окно: только тогда `java -version` начнёт показывать ту же версию. Если снова видна старая версия, для всех следующих команд используйте `& $env:BSL_JAVA`, а не `java`.

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
& $env:BSL_JAVA -jar $jar version
```

Ожидаемый SHA256, без учёта регистра:

`9F62765EDD344D66456DA24C906EAF623A03C56E90E5AAFEE466200100909F64`

Последняя команда блока должна напечатать `version: 1.0.7`. Её нельзя запускать отдельно от строки `$jar = ...`: если `$jar` пустая, PowerShell принимает слово `version` за имя файла и пишет `Unable to access jarfile version`.

Проверка самой Java, без jar:

```powershell
& $env:BSL_JAVA -version
```

Ожидается Java 21 или новее. Если версия ниже 21, вернитесь к шагу 2 и смените путь. Jar заново скачивать не нужно.

## 5. Клонирование и виртуальное окружение

Не выполняйте эти команды в `C:\WINDOWS\system32`. У этого каталога нет права на создание папки, поэтому `git clone` отвечает `Permission denied`, а `python -m venv .venv` — `Отказано в доступе`. Если приглашение PowerShell начинается с `PS C:\WINDOWS\system32>`, первая команда ниже переходит в домашнюю папку, например `C:\Users\Имя`.

```powershell
Set-Location $env:USERPROFILE
git clone https://github.com/IliasNizamutdinov/1C-Language-Server-MCP-for-Cursor-and-OpenCode.git
Set-Location "$env:USERPROFILE\1C-Language-Server-MCP-for-Cursor-and-OpenCode"
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
