param(
  [string]$Version = "0.5"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$VsDevCmd = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
$Dist = Join-Path $Root "dist"

if (-not (Test-Path $VsDevCmd)) {
  throw "Visual Studio Build Tools were not found: $VsDevCmd"
}

New-Item -ItemType Directory -Force -Path $Dist | Out-Null

& $env:ComSpec /d /s /c "call `"$VsDevCmd`" -arch=x64 -host_arch=x64 && cd /d `"$Root\cpp`" && call build_msvc.bat"
if ($LASTEXITCODE -ne 0) {
  throw "AutoAdder.exe build failed."
}

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_release.ps1") -Version $Version -IncludePortablePython
if ($LASTEXITCODE -ne 0) {
  throw "Portable release build failed."
}

$ReleaseZip = Join-Path $Dist "AutoAdder-$Version.zip"
$CustomerZip = Join-Path $Dist "Auto-adder.zip"
Copy-Item -LiteralPath $ReleaseZip -Destination $CustomerZip -Force

& $env:ComSpec /d /s /c "call `"$VsDevCmd`" -arch=x64 -host_arch=x64 && cd /d `"$Root\setup`" && call build_setup_msvc.bat"
if ($LASTEXITCODE -ne 0) {
  throw "AutoAdderSetup.exe build failed."
}

Copy-Item -LiteralPath (Join-Path $Root "setup\build\AutoAdderSetup.exe") -Destination (Join-Path $Dist "AutoAdderSetup.exe") -Force

$Stage = Join-Path $Dist "AutoAdder-$Version"
foreach ($generatedDir in @($Stage, (Join-Path $Root "setup\build"), (Join-Path $Root "cpp\build"))) {
  if (Test-Path -LiteralPath $generatedDir) {
    Remove-Item -LiteralPath $generatedDir -Recurse -Force
  }
}

Write-Host "Customer installer: $Dist\AutoAdderSetup.exe"
Write-Host "Portable zip:       $CustomerZip"
Get-FileHash -LiteralPath (Join-Path $Dist "AutoAdderSetup.exe") -Algorithm SHA256
