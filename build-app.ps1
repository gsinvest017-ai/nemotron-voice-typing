#Requires -Version 7
<#
.SYNOPSIS
    打包 nemotron-voice 桌面 App（用自家麥克風 icon，不被 gs-app-pack 金環覆蓋）。
.DESCRIPTION
    流程：產生 voice icon -> 直接 pyinstaller（embed 我們的 icon）-> gs-app-pack 產 Inno
    安裝檔 ->（給 -Tag 時）發 GitHub Release。
    不走 gs-app-pack 的 build.ps1，因為它會用 make_icon.py 把 static\gs-icon.ico 蓋成通用金環。
.EXAMPLE
    pwsh -File build-app.ps1                 # 建 exe + 安裝檔
    pwsh -File build-app.ps1 -Tag v1.0.1     # + 發 Release（記得先 push main）
#>
[CmdletBinding()]
param([string]$Tag = "")

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root
$PACK = "C:\Users\User\gs-app-pack\pack.ps1"

Write-Host "=== [1/4] 產生 voice icon ===" -ForegroundColor Cyan
python make_voice_icon.py --out static\gs-icon.ico
if ($LASTEXITCODE -ne 0) { throw "make_voice_icon.py failed" }

Write-Host "=== [2/4] PyInstaller（內嵌麥克風 icon）===" -ForegroundColor Cyan
Get-Process nemotron-voice -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue
pyinstaller app.py --onedir --windowed --name nemotron-voice --icon static\gs-icon.ico --noconfirm `
    --add-data "static;static" --add-data "vtcontrol;vtcontrol" --add-data "install.ps1;." `
    --add-data "config;config" --add-data "patches;patches" --add-data "scripts;scripts" `
    --collect-all=webview
if ($LASTEXITCODE -ne 0) { throw "pyinstaller failed" }

Write-Host "=== [3/4] Inno Setup 安裝檔 ===" -ForegroundColor Cyan
& $PACK -Only installer

if ($Tag) {
    Write-Host "=== [4/4] GitHub Release $Tag ===" -ForegroundColor Cyan
    & $PACK -Only release -Tag $Tag
} else {
    Write-Host "=== [4/4] Release 略過（加 -Tag vX.Y.Z 才發布）===" -ForegroundColor DarkGray
}
Write-Host "Done." -ForegroundColor Green
