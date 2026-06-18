# WhisperWriter 語音輸入啟動器（常駐系統匣）
# 在任何視窗按住熱鍵（預設 Ctrl+Shift+Space）說話，放開即把辨識文字打進游標處。
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root
& "$root\.venv\Scripts\python.exe" "$root\run.py"
