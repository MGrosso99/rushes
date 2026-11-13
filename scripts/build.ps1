<#
.SYNOPSIS
  Genera dist\TraerMaterial\ (PyInstaller) y el instalador packaging\Output\TraerMaterial-Setup.exe (Inno Setup).
  Requisitos: Python 3.11+ y Inno Setup 6 (ISCC.exe) instalados. Correr fetch_vendor.ps1 antes.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path "vendor\rclone.exe") -or -not (Test-Path "vendor\ffprobe.exe")) {
    throw "Faltan binarios en vendor\. Corré primero: .\scripts\fetch_vendor.ps1"
}

if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip pyinstaller pytest | Out-Null

Write-Host "Tests..."
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests fallaron" }

Write-Host "PyInstaller..."
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed `
    --name TraerMaterial `
    --paths src `
    --add-data "vendor;vendor" `
    packaging\entry.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló" }

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "No encuentro Inno Setup 6 (ISCC.exe). Instalalo desde jrsoftware.org." }

$version = (Select-String -Path "src\traer_material\__init__.py" -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
& $iscc "/DAppVersion=$version" packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falló" }
Write-Host "Instalador: packaging\Output\TraerMaterial-Setup-$version.exe"
