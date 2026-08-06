param(
  [string]$Version = "0.2",
  [string]$OutDir = "dist",
  [switch]$IncludePortablePython,
  [string]$PortablePythonSource = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python",
  [string]$OverlaySitePackages = ".venv\Lib\site-packages"
)

$ErrorActionPreference = "Stop"

function Copy-DirectoryTree {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Source,

    [Parameter(Mandatory = $true)]
    [string]$Destination
  )

  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  & robocopy $Source $Destination /E /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed with exit code $LASTEXITCODE while copying $Source"
  }
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ReleaseName = "AutoAdder-$Version"
$ReleaseRoot = Join-Path $Root $OutDir
$Stage = Join-Path $ReleaseRoot $ReleaseName
$Zip = Join-Path $ReleaseRoot "$ReleaseName.zip"

New-Item -ItemType Directory -Force -Path $ReleaseRoot | Out-Null

if (Test-Path $Stage) {
  Remove-Item -LiteralPath $Stage -Recurse -Force
}
if (Test-Path $Zip) {
  Remove-Item -LiteralPath $Zip -Force
}

New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Copy-Item -LiteralPath (Join-Path $Root "cpp\build\AutoAdder.exe") -Destination (Join-Path $Stage "AutoAdder.exe")
Copy-Item -LiteralPath (Join-Path $Root "engine") -Destination (Join-Path $Stage "engine") -Recurse
Copy-Item -LiteralPath (Join-Path $Root "check_pack") -Destination (Join-Path $Stage "check_pack") -Recurse
if (Test-Path (Join-Path $Root "assets")) {
  Copy-Item -LiteralPath (Join-Path $Root "assets") -Destination (Join-Path $Stage "assets") -Recurse
}

if ($IncludePortablePython) {
  $PortablePythonSourcePath = Resolve-Path $PortablePythonSource
  $PortablePythonDestination = Join-Path $Stage "python"

  Write-Host "Copying portable Python from: $PortablePythonSourcePath"
  Copy-DirectoryTree -Source $PortablePythonSourcePath.Path -Destination $PortablePythonDestination

  $OverlayPath = Join-Path $Root $OverlaySitePackages
  if (Test-Path $OverlayPath) {
    Write-Host "Overlaying project site-packages from: $OverlayPath"
    Copy-DirectoryTree -Source $OverlayPath -Destination (Join-Path $PortablePythonDestination "Lib\site-packages")
  }

  Get-ChildItem -LiteralPath $PortablePythonDestination -Recurse -Directory -Filter "__pycache__" |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }

  Get-ChildItem -LiteralPath $PortablePythonDestination -Recurse -File |
    Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
}

Copy-Item -LiteralPath (Join-Path $Root "requirements.txt") -Destination $Stage
Copy-Item -LiteralPath (Join-Path $Root "install_deps.bat") -Destination $Stage
Copy-Item -LiteralPath (Join-Path $Root "START_AUTO_ADDER.bat") -Destination $Stage
Copy-Item -LiteralPath (Join-Path $Root "docs\CLIENT_README.txt") -Destination $Stage
Copy-Item -LiteralPath (Join-Path $Root "docs\PRIVACY_SECURITY.md") -Destination $Stage
Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination $Stage

Get-ChildItem -LiteralPath $Stage -Recurse -Directory -Filter "__pycache__" |
  ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }

Get-ChildItem -LiteralPath $Stage -Recurse -File |
  Where-Object {
    $_.Name -like "*.pyc" -or
    $_.Name -like "*_backup.*" -or
    $_.Name -like "*_filled.*" -or
    $_.Name -in @("fill_result.json", "extract_result.json", "fields.json")
  } |
  ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }

& tar.exe -a -cf $Zip -C $ReleaseRoot $ReleaseName
if ($LASTEXITCODE -ne 0) {
  throw "tar failed with exit code $LASTEXITCODE while creating $Zip"
}

Write-Host "Release folder: $Stage"
Write-Host "Release zip:    $Zip"
