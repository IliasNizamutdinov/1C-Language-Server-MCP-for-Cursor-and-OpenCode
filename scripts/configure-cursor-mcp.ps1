# Writes %USERPROFILE%\.cursor\mcp.json for the bsl-syntax server.
# Uses only python.exe and java.exe that exist on disk.
# Messages are ASCII so Windows PowerShell 5.1 can parse the file.

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
  Write-Host "python.exe from .venv was not found."
  Write-Host "Cursor reports: The system cannot find the path specified."
  Write-Host "Finish step 5 of docs/windows.md from your home folder, not from C:\WINDOWS\system32."
  exit 1
}

$jar = Join-Path $env:USERPROFILE ".bsl-mcp\bsl-language-server-1.0.7-exec.jar"
if (-not (Test-Path -LiteralPath $jar)) {
  Write-Host "Jar not found: $jar"
  exit 1
}

$javaExe = Find-Java21OrNewer
if (-not $javaExe) {
  Write-Host "JDK 21 or newer was not found. Do not save the path of the current java command while it is version 17."
  exit 1
}
[Environment]::SetEnvironmentVariable("BSL_JAVA", $javaExe, "User")
$env:BSL_JAVA = $javaExe

$server = [ordered]@{
  type    = "stdio"
  command = $python
  args    = @("-m", "bsl_mcp")
  env     = [ordered]@{
    BSL_LANGUAGE_SERVER_JAR = $jar
    BSL_JAVA                = '${env:BSL_JAVA}'
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
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($mcpPath, $json, $utf8)

Write-Host "Wrote: $mcpPath"
Write-Host "python: $python"
Write-Host "java:   $javaExe"
Write-Host "mcp.json keeps the name of the variable: `${env:BSL_JAVA}"
Write-Host "jar:    $jar"
Write-Host "Close Cursor completely, then open it again."
