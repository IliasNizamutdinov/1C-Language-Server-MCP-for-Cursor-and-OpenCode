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

Сначала посмотрите, что вызывает команда `java`:

```powershell
java -version
```

Если здесь `17`, не сохраняйте этот путь. Строка `(Get-Command java).Source` указывает на ту же Java 17, поэтому после `$env:BSL_JAVA = (Get-Command java).Source` команда `& $env:BSL_JAVA -version` снова печатает 17. Версия так не меняется.

JDK 21 или новее нужно установить по ссылке выше, если его ещё нет. После установки закройте PowerShell, откройте новое окно и выполните весь блок ниже. Он ищет каталог `C:\Program Files\Microsoft\jdk-21...` (или новее) и записывает путь к его `java.exe`. Старую Java 17 он не выбирает.

```powershell
$jdk = Get-ChildItem "C:\Program Files\Microsoft" -Directory -Filter "jdk-*" -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^jdk-(\d+)' -and [int]$Matches[1] -ge 21 } |
  Sort-Object { if ($_.Name -match '^jdk-(\d+)') { [int]$Matches[1] } } -Descending |
  Select-Object -First 1
if (-not $jdk) {
  throw "JDK 21 или новее в C:\Program Files\Microsoft не найден. Установите его по ссылке выше и откройте новое окно PowerShell. Не записывайте в BSL_JAVA путь от команды java, пока java -version показывает 17."
}
$env:BSL_JAVA = Join-Path $jdk.FullName "bin\java.exe"
[Environment]::SetEnvironmentVariable("BSL_JAVA", $env:BSL_JAVA, "User")
$bin = Split-Path $env:BSL_JAVA
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "$bin*") {
  [Environment]::SetEnvironmentVariable("Path", "$bin;$userPath", "User")
}
Write-Host "Сохранён путь: $env:BSL_JAVA"
& $env:BSL_JAVA -version
```

Ожидается `openjdk version "21..."` или новее, например `25...`, и строка `Сохранён путь:` с каталогом `jdk-21` или старше. Если снова видна версия 17, блок выбрал не тот файл: смотрите путь в строке `Сохранён путь`.

Закройте PowerShell и откройте новое окно. Команда `java -version` начнёт показывать 21 или новее только после этого. Если в новом окне по-прежнему 17, для проверки анализатора используйте `& $env:BSL_JAVA`, а не `java`.

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

Окружение `.venv` действует только в том окне PowerShell, где его включили. После закрытия окна оно выключается. В новом окне включите его снова и перейдите в каталог репозитория. Приглашение должно начаться с `(.venv)`.

```powershell
Set-Location "$env:USERPROFILE\1C-Language-Server-MCP-for-Cursor-and-OpenCode"
.\.venv\Scripts\Activate.ps1
```

Если PowerShell пишет, что выполнение сценариев отключено, один раз для этого окна выполните:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Set-Location "$env:USERPROFILE\1C-Language-Server-MCP-for-Cursor-and-OpenCode"
.\.venv\Scripts\Activate.ps1
```

В этом же новом окне снова задайте каталог, который разрешено проверять. Путь к jar уже сохранён на шаге 6 и подхватится сам, если окно открыто после той команды.

```powershell
$env:BSL_MCP_ALLOWED_ROOTS = (Get-Location).Path
```

Дальше, уже с `(.venv)` в приглашении:

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
