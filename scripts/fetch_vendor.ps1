<#
.SYNOPSIS
  Descarga rclone.exe y ffprobe.exe (y opcionalmente ffmpeg.exe) a vendor/,
  verificando SHA256 contra el checksum oficial y contra los hashes fijados en vendor/checksums.txt.

.DESCRIPTION
  Primera vez (o para actualizar versiones):  .\scripts\fetch_vendor.ps1 -UpdatePins
     -> verifica contra el checksum oficial y GUARDA los hashes en vendor/checksums.txt (commitealo).
  Siguientes builds:                          .\scripts\fetch_vendor.ps1
     -> falla si el hash no coincide con el fijado (protege contra binarios alterados).

.PARAMETER WithFfmpeg
  Incluye ffmpeg.exe para la "verificación completa" (deep_check). Suma ~100 MB al instalador.
#>
param(
    [switch]$UpdatePins,
    [switch]$WithFfmpeg
)
$ErrorActionPreference = "Stop"
$Root    = Split-Path -Parent $PSScriptRoot
$Vendor  = Join-Path $Root "vendor"
$Pins    = Join-Path $Vendor "checksums.txt"
$Tmp     = Join-Path ([IO.Path]::GetTempPath()) ("rushes-vendor-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $Vendor, $Tmp | Out-Null

# Algunos servidores mandan los .txt/.sha256 como binario: PowerShell devuelve byte[] y
# los -split/-match no encuentran nada. Esto siempre devuelve texto.
function Get-Text([string]$Url) {
    $c = (Invoke-WebRequest -UseBasicParsing $Url).Content
    if ($c -is [byte[]]) { return [Text.Encoding]::UTF8.GetString($c) }
    return [string]$c
}

function Get-Pins {
    $h = @{}
    if (Test-Path $Pins) {
        Get-Content $Pins | Where-Object { $_ -match '^\s*([0-9a-fA-F]{64})\s+(\S+)' } |
            ForEach-Object { $h[$Matches[2]] = $Matches[1].ToLower() }
    }
    return $h
}
$pinned = Get-Pins
$newPins = @{}

function Assert-Hash([string]$File, [string]$Official, [string]$Key) {
    $actual = (Get-FileHash -Algorithm SHA256 $File).Hash.ToLower()
    if ($actual -ne $Official.ToLower()) { throw "SHA256 de $Key NO coincide con el oficial. Abortando." }
    if (-not $UpdatePins) {
        if (-not $pinned.ContainsKey($Key)) { throw "No hay hash fijado para $Key. Corré con -UpdatePins." }
        if ($pinned[$Key] -ne $actual) { throw "SHA256 de $Key no coincide con vendor/checksums.txt. Abortando." }
    }
    $script:newPins[$Key] = $actual
    Write-Host "  OK $Key $actual"
}

# ---------------- rclone ----------------
$ver = ((Get-Text "https://downloads.rclone.org/version.txt") -replace '^rclone\s+','').Trim()
if (-not $UpdatePins -and $pinned.Keys -match '^rclone-') {
    $ver = (($pinned.Keys | Where-Object { $_ -like 'rclone-*' } | Select-Object -First 1) -replace '^rclone-(v[\d\.]+)-.*','$1')
}
$rzip = "rclone-$ver-windows-amd64.zip"
Write-Host "rclone $ver"
Invoke-WebRequest -UseBasicParsing "https://downloads.rclone.org/$ver/$rzip" -OutFile "$Tmp\$rzip"
$sums = Get-Text "https://downloads.rclone.org/$ver/SHA256SUMS"
$line = ($sums -split "\r?\n") | Where-Object { $_ -match [regex]::Escape($rzip) } | Select-Object -First 1
if (-not $line) { throw "No encontré $rzip en SHA256SUMS" }
Assert-Hash "$Tmp\$rzip" (($line -split '\s+')[0]) $rzip
Expand-Archive "$Tmp\$rzip" -DestinationPath $Tmp -Force
Copy-Item (Get-ChildItem $Tmp -Recurse -Filter rclone.exe | Select-Object -First 1).FullName $Vendor -Force

# ---------------- ffmpeg / ffprobe (build oficial recomendada por ffmpeg.org para Windows) ----------------
$fzip = "ffmpeg-release-essentials.zip"
Write-Host "ffmpeg essentials (gyan.dev)"
Invoke-WebRequest -UseBasicParsing "https://www.gyan.dev/ffmpeg/builds/$fzip" -OutFile "$Tmp\$fzip"
$fsha = (Get-Text "https://www.gyan.dev/ffmpeg/builds/$fzip.sha256").Trim()
# El zip "release" cambia con cada versión: el pin se actualiza con -UpdatePins.
Assert-Hash "$Tmp\$fzip" (($fsha -split '\s+')[0]) $fzip
Expand-Archive "$Tmp\$fzip" -DestinationPath $Tmp -Force
Copy-Item (Get-ChildItem $Tmp -Recurse -Filter ffprobe.exe | Select-Object -First 1).FullName $Vendor -Force
if ($WithFfmpeg) {
    Copy-Item (Get-ChildItem $Tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1).FullName $Vendor -Force
} elseif (Test-Path "$Vendor\ffmpeg.exe") {
    Remove-Item "$Vendor\ffmpeg.exe"
}

if ($UpdatePins) {
    $newPins.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Value)  $($_.Name)" } |
        Set-Content -Encoding ascii $Pins
    Write-Host "Hashes guardados en vendor/checksums.txt -> commitealo."
}
Remove-Item -Recurse -Force $Tmp
Write-Host "Listo: $(Get-ChildItem $Vendor -Filter *.exe | ForEach-Object Name)"
