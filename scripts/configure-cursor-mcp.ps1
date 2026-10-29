# Записывает %USERPROFILE%\.cursor\mcp.json для сервера bsl-syntax.
# Берёт только те python.exe и java.exe, которые реально есть на диске.

$ErrorActionPreference = "Stop"

function Find-RepoPython {
  $folders = @(
    $env:USERPROFILE,
    (Join-Path $env:USERPROFILE "source"),
    (Join-Path $env:USERPROFILE "Documents"),
    (Join-Path $env:USERPROFILE "Desktop")
  )
  foreach ($folder in $folders) {
    if (-not (Test-Path -LiteralPath $folder)) { continue }
    $direct = Join-Path $folder "1C-Language-Server-MCP-for-Cursor-and-OpenCode\.venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $direct) {
      return (Resolve-Path -LiteralPath $direct).Path
    }
    $children = Get-ChildItem -LiteralPath $folder -Directory -ErrorAction SilentlyContinue
    foreach ($child in $children) {
      $nested = Join-Path $child.FullName "1C-Language-Server-MCP-for-Cursor-and-OpenCode\.venv\Scripts\python.exe"
      if (Test-Path -LiteralPath $nested) {
        return (Resolve-Path -LiteralPath $nested).Path
      }
    }
  }
  return $null
}

function Find-Java21OrNewer {
  $roots = @(
    "C:\Program Files\Microsoft",
    "C:\Program Files\Java",
    "C:\Program Files\Eclipse Adoptium"
  )
  $found = @()
  foreach ($root in $roots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $dirs = Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue
    foreach ($dir in $dirs) {
      if ($dir.Name -notmatch '^jdk-(\d+)') { continue }
      $major = [int]$Matches[1]
      if ($major -lt 21) { continue }
      $exe = Join-Path $dir.FullName "bin\java.exe"
      if (Test-Path -LiteralPath $exe) {
        $found += [pscustomobject]@{ Major = $major; Exe = (Resolve-Path -LiteralPath $exe).Path }
      }
    }
  }
  $best = $found | Sort-Object Major -Descending | Select-Object -First 1
  if ($best) { return $best.Exe }
  return $null
}

$python = Find-RepoPython
if (-not $python) {
  Write-Host "Файл .venv\Scripts\python.exe не найден."
  Write-Host "Cursor поэтому пишет: Системе не удается найти указанный путь."
  Write-Host "Сначала из домашней папки, не из C:\WINDOWS\system32, выполните шаг 5 инструкции docs/windows.md."
  exit 1
}

$jar = Join-Path $env:USERPROFILE ".bsl-mcp\bsl-language-server-1.0.7-exec.jar"
if (-not (Test-Path -LiteralPath $jar)) {
  Write-Host "Не найден jar: $jar"
  exit 1
}

$javaExe = Find-Java21OrNewer
if (-not $javaExe) {
  Write-Host "JDK 21 или новее не найден. Текущая команда java указывает на старую версию, её путь сохранять нельзя."
  exit 1
}

$server = [ordered]@{
  type    = "stdio"
  command = $python
  args    = @("-m", "bsl_mcp")
  env     = [ordered]@{
    BSL_LANGUAGE_SERVER_JAR = $jar
    BSL_JAVA                = $javaExe
    BSL_MCP_ALLOWED_ROOTS   = '${workspaceFolder}'
    BSL_MCP_TIMEOUT         = "180"
    BSL_MCP_FAIL_ON         = "syntax"
    PYTHONIOENCODING        = "utf-8"
    PYTHONUTF8              = "1"
  }
}

$mcpDir = Join-Path $env:USERPROFILE ".cursor"
$mcpPath = Join-Path $mcpDir "mcp.json"
if (-not (Test-Path -LiteralPath $mcpDir)) {
  New-Item -ItemType Directory -Path $mcpDir | Out-Null
}

$servers = [ordered]@{}
if (Test-Path -LiteralPath $mcpPath) {
  $existing = Get-Content -LiteralPath $mcpPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($existing.mcpServers) {
    foreach ($property in $existing.mcpServers.PSObject.Properties) {
      if ($property.Name -ne "bsl-syntax") {
        $servers[$property.Name] = $property.Value
      }
    }
  }
}
$servers["bsl-syntax"] = $server
$document = [ordered]@{ mcpServers = $servers }
$json = $document | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText($mcpPath, $json, [System.Text.UTF8Encoding]::new($false))

Write-Host "Записан файл: $mcpPath"
Write-Host "python: $python"
Write-Host "java:   $javaExe"
Write-Host "jar:    $jar"
Write-Host "Полностью закройте Cursor и откройте снова."
