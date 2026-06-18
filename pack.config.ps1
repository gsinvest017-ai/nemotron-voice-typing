# pack.config.ps1 — nemotron-voice-typing 桌面 App 打包設定（給 gs-app-pack）
# 用法（從本 repo 根目錄）：
#   C:\Users\User\gs-app-pack\pack.ps1 -Clean              # 建 exe + 安裝檔
#   C:\Users\User\gs-app-pack\pack.ps1 -Tag v1.0.0 -Clean  # + GitHub Release

# ── App metadata ─────────────────────────────────────────────────────────────
$AppName      = "Nemotron 語音輸入"
$AppVersion   = "1.0.3"
$AppId        = "7E3A9C42-1B5D-4F6A-9C21-3D8E2F0A6B74"
$AppExe       = "nemotron-voice"            # 輸出 exe 名（不含 .exe）
$AppPublisher = "gsinvest"
$AppUrl       = "https://github.com/gsinvest017-ai/nemotron-voice-typing"

# ── Server startup ───────────────────────────────────────────────────────────
# 本專案自訂 app.py（控制面板 + 自動啟停語音輸入），server 走 stdlib http.server。
$ServerMode   = "function"
$ServerModule = "vtcontrol.server"
$ServerFunc   = "serve"
$ServerApp    = "app"
$ServerCmd    = ""
$ServerHost   = "127.0.0.1"
$ServerPort   = 8791
$ConfigModule = ""
$ConfigFunc   = ""

# ── pywebview 視窗 ───────────────────────────────────────────────────────────
$WinTitle     = "Nemotron 語音輸入"
$WinWidth     = 660
$WinHeight    = 580
$WinBgColor   = "#0f0b06"
# DWM 標題列（Windows 11；COLORREF = 0x00BBGGRR）
$DwmCaption   = 0x00060B0F            # #0f0b06
$DwmBorder    = 0x0037AFD4            # #d4af37 gold
$DwmText      = 0x0095D1E8            # #e8d195 champagne

# ── Icon ─────────────────────────────────────────────────────────────────────
$IconBg       = "#0f0b06"
$IconRing     = "#d4af37"
$IconSize     = 32

# ── PyInstaller ──────────────────────────────────────────────────────────────
# 把控制面板資源 + 安裝腳本/模板一起打包，讓「一鍵安裝語音引擎」按鈕可用。
$PyiAddData   = @(
    "static;static",
    "vtcontrol;vtcontrol",
    "install.ps1;.",
    "config;config",
    "patches;patches",
    "scripts;scripts"
)
# pywebview 的 EdgeChromium backend 動態載入，需 collect-all 才不會漏。
$PyiExtraArgs = @(
    "--collect-all=webview"
)

# ── Installer (Inno Setup) ───────────────────────────────────────────────────
$InstallerRequiresGh = $false         # 自動更新讀 private repo 需 token，但安裝時不強制裝 gh
