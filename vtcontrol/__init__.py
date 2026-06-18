"""nemotron-voice-typing 桌面控制器套件。

控制器本身是輕量的 pywebview 控制面板，負責：
  - 開窗自動在背景啟動語音輸入（whisper-writer），關窗即停止
  - Start/Stop 切換、狀態顯示
  - 透過 GitHub Release 自動更新自己

重的 ML 環境（CUDA / faster-whisper / 模型）不打進安裝檔，
由 install.ps1 安裝到 ~/tools/whisper-writer，控制器只負責「控制」它。
"""

# 自動更新比對版號用；release 前需與 pack.config.ps1 的 $AppVersion 同步。
APP_VERSION = "1.0.1"
