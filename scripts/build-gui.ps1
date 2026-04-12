Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$projectRoot = Split-Path -Parent $PSScriptRoot
$releaseVersion = "0.120.1"
$distDir = Join-Path $projectRoot "dist"
$buildDir = Join-Path $projectRoot "build"
$releaseDir = Join-Path $projectRoot "release"
$bundleDir = Join-Path $releaseDir "Codex-CLI-CN-v$releaseVersion-GUI-win64"
$zipPath = Join-Path $releaseDir "Codex-CLI-CN-v$releaseVersion-GUI-win64.zip"
$specPath = Join-Path $projectRoot "gui\Codex-CLI-CN-GUI.spec"

if (Test-Path $distDir) { Remove-Item $distDir -Recurse -Force }
if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force }
if (Test-Path $bundleDir) { Remove-Item $bundleDir -Recurse -Force }
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Push-Location $projectRoot
try {
    pyinstaller $specPath --noconfirm --clean
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller 构建失败，退出码：$LASTEXITCODE"
    }

    New-Item -ItemType Directory -Force -Path $bundleDir | Out-Null

    Copy-Item (Join-Path $distDir "Codex-CLI-CN-GUI.exe") $bundleDir -Force
    Copy-Item (Join-Path $projectRoot "README.md") $bundleDir -Force
    Copy-Item (Join-Path $projectRoot "NOTICE.md") $bundleDir -Force
    Copy-Item (Join-Path $projectRoot "CHANGELOG.md") $bundleDir -Force
    Copy-Item (Join-Path $projectRoot "LICENSE") $bundleDir -Force

    Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $zipPath -Force
    Write-Host "Release package:"
    Write-Host $zipPath
}
finally {
    Pop-Location
}
