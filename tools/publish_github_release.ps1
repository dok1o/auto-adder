param(
  [Parameter(Mandatory = $true)]
  [string]$Repository,

  [string]$Tag = "v0.3",
  [string]$Title = "Auto Adder 0.3",
  [string]$InstallerPath = "dist\AutoAdderSetup.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
  Write-Host "GitHub CLI (gh) is not installed."
  Write-Host "Install it from: https://cli.github.com/"
  exit 1
}

if (-not (Test-Path -LiteralPath $InstallerPath)) {
  Write-Host "Installer not found: $InstallerPath"
  exit 1
}

gh release create $Tag $InstallerPath `
  --repo $Repository `
  --title $Title `
  --notes-file docs\RELEASE_NOTES.md

Write-Host ""
Write-Host "Customer direct download link:"
Write-Host "https://github.com/$Repository/releases/latest/download/AutoAdderSetup.exe"
