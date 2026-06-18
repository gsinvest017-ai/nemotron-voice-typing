# nemotron-voice-typing

> 地端「Vibe Coding」語音輸入一鍵安裝套件：**Whisper（語音轉文字）+ Nemotron（本機 LLM）+ VS Code Continue**。
> 全程不上雲、低延遲，按住熱鍵說話、放開即把程式碼需求打進編輯器。
> 專為 **Windows 11 + NVIDIA GPU** 設計（在 RTX 5090 / 32GB 實測）。

這個 repo 的價值不只在腳本，而在它**內建了實際安裝時踩過的 4 個坑的解法**——照 survey 直裝會卡在這些地方。

---

## 架構

| 層 | 工具 | 說明 |
|---|---|---|
| 語音轉文字 (STT) | [whisper-writer](https://github.com/verbumeng/whisper-writer)（faster-whisper + CUDA） | 系統匣常駐，按住熱鍵說話→放開→辨識文字打進當前游標 |
| 本機 LLM | [Ollama](https://ollama.com) + `nemotron-3-nano:30b` | 30B-A3B MoE，24GB，塞得進 32GB 顯卡還留空間給 Whisper |
| 編輯器整合 | VS Code [Continue](https://www.continue.dev/) | chat/edit 用 Nemotron、Tab 補全用 qwen3-coder |

---

## 桌面應用程式（安裝檔 + 自動更新）⭐

除了腳本，本 repo 也提供一個 **桌面控制器 App**（`nemotron-voice-setup.exe`）：

- **點兩下安裝檔 → 桌面捷徑/開始選單** 多一個「Nemotron 語音輸入」圖示（免系統管理員、per-user 安裝）
- **點圖示開啟 → 自動在背景啟動語音輸入**；面板有運作狀態、Start/Stop 切換、模型/熱鍵資訊
- **關閉視窗 → 背景語音輸入即停止**
- **自動更新**：面板「檢查更新」會比對 GitHub Release，有新版一鍵下載靜默升級並自動重啟
- 首次若偵測不到語音引擎，面板提供「一鍵安裝語音引擎」按鈕（背景跑 `install.ps1`）

> 桌面 App 是**輕量控制器**（~50MB），不含 CUDA/模型；它控制由 `install.ps1` 裝在
> `~/tools/whisper-writer` 的重環境。安裝檔在 [Releases](https://github.com/gsinvest017-ai/nemotron-voice-typing/releases) 下載。
> repo 為 private，自動更新需 `gh auth login` 或設定 `NVT_GH_TOKEN`。

### 自己打包桌面 App
底層用通用打包器 [gs-app-pack](https://github.com/gsinvest017-ai)（PyInstaller + Inno Setup），
但**請用本 repo 的 `build-app.ps1`**（不要直接 `pack.ps1`）——它會先以 `make_voice_icon.py`
產生麥克風 icon 再打包，避免被 gs-app-pack 的通用金環 `make_icon.py` 蓋掉而跟其他 GS app 撞圖：
```powershell
pip install pyinstaller pywebview pillow   # 一次性
pwsh -File build-app.ps1                    # 建 exe + 安裝檔
pwsh -File build-app.ps1 -Tag v1.0.2       # + 發 GitHub Release（先 git push main）
```
發版前記得同步 `vtcontrol/__init__.py` 的 `APP_VERSION` 與 `pack.config.ps1` 的 `$AppVersion`。
控制器原始碼在 `app.py` + `vtcontrol/`（`manager` 管子程序、`server` stdlib 控制 API、`updater` 自我更新）、
UI 在 `static/control.html`、icon 產生器 `make_voice_icon.py`、打包設定 `pack.config.ps1`。

---

## 一鍵安裝（純腳本，不需桌面 App）

```powershell
git clone https://github.com/gsinvest017-ai/nemotron-voice-typing
cd nemotron-voice-typing
pwsh -File install.ps1
```

腳本會自動：偵測 GPU → pull LLM → clone whisper-writer → 建 venv 裝依賴（避開坑1、2）→ 部署 DLL 修正（坑4）→ patch UTF-8（坑3）→ 寫設定 → 裝 Continue → **實跑一次 encode 驗證 GPU 真的生效**。

### 常用參數

```powershell
pwsh -File install.ps1 -WhisperModel large-v3-turbo   # 換更快的 turbo 模型
pwsh -File install.ps1 -SkipOllama                     # 只裝語音輸入，不裝 LLM
pwsh -File install.ps1 -SkipContinue                   # 不裝 VS Code 擴充
pwsh -File install.ps1 -Hotkey "ctrl+alt+space"        # 自訂熱鍵
```

### 前置需求
- Windows 11、PowerShell 7+（`pwsh`）
- Python 3.10+、git
- NVIDIA GPU + 驅動（沒有的話腳本會自動退成 CPU int8，但會慢很多）
- Ollama（要裝 LLM 時）、VS Code 的 `code` CLI（要裝 Continue 時）

---

## 安裝完怎麼用

```powershell
& "$HOME\tools\whisper-writer\start-voice.ps1"   # 啟動，常駐系統匣
```
- 任何視窗按住 **Ctrl+Shift+Space** 說話 → 放開 → 辨識文字自動打進游標處
- VS Code vibe coding：`Ctrl+I` 開 Continue → 按住熱鍵說「幫我寫一個 Python 快排，加註解」→ 放開 → Enter
- 停止：`stop-voice.ps1`　測麥克風：`test-mic.ps1`

---

## 踩過的 4 個坑與解法 ⭐

照泛用教學直裝一定會中這幾個，這也是本 repo 存在的理由。

### 坑 1：Blackwell(RTX 50 系 / sm_120) 跑不動 repo 釘死的舊 ctranslate2
whisper-writer 的 `requirements.txt` 釘 `ctranslate2==4.2.1`，那版不支援新顯卡架構。
**解法**：改裝 `ctranslate2>=4.5`（實測 4.8.0）+ `faster-whisper>=1.1`（1.2.1）。

### 坑 2：requirements.txt 釘死舊版在 Python 3.12 編譯失敗
`numpy==1.24.3` 等舊 pin 在 3.12 沒有 wheel、要現場編 C 擴充而失敗，**導致 `pip install -r requirements.txt` 整批中斷**，PyQt5 / dotenv / pynput 全沒裝進去。表面只看到後面一個 `ModuleNotFoundError`。
**解法**：不要用 `requirements.txt`，改裝不釘版本的執行期套件清單（見 `install.ps1`）。

### 坑 3：config 用 cp950 讀 UTF-8 中文 → `UnicodeDecodeError`
`src/utils.py` 的 `open()` 沒指定編碼，Windows 預設用 cp950(Big5) 去解設定檔裡的中文 `initial_prompt`，啟動就炸 `'cp950' codec can't decode byte ...`。
**解法**：patch `load_user_config` / `save_config` 的 `open()` 加 `encoding="utf-8"`（存檔再加 `allow_unicode=True`）。`install.ps1` 會自動套這個 patch。

### 坑 4（最隱蔽，會害你以為「GPU 很慢」）：缺 cublas DLL → 靜默 fallback 到 CPU
ctranslate2 在 Windows **不會**自動搜尋 pip 裝的 `site-packages\nvidia\*\bin`，找不到 `cublas64_12.dll` 時 `transcription.py` 會**靜默 fallback 到 CPU**——不報錯，只是 large-v3 一句話從 **~0.3s 暴增到 ~6s**。
**陷阱中的陷阱**：`WhisperModel(...)` 只「載入」模型**不會**觸發缺 DLL，要 `.transcribe()` 跑到 encode 才會。所以**驗證 GPU 一定要實際轉錄一次**，不能只看載入成功。
**解法**：在 venv 的 `site-packages\sitecustomize.py` 用 `os.add_dll_directory()` 把 cublas/cudnn 的 bin 加進 DLL 搜尋路徑（見 `patches/sitecustomize.py`）。

| 坑 | 症狀 | 解法 |
|---|---|---|
| 1 Blackwell | 新顯卡載模型/encode 出錯 | 升級 ctranslate2≥4.5 + faster-whisper≥1.1 |
| 2 舊 pin 編譯失敗 | `ModuleNotFoundError: dotenv` 等 | 不用 requirements.txt，裝不釘版本清單 |
| 3 cp950 編碼 | 啟動 `UnicodeDecodeError` | utils.py 的 open() 加 `encoding="utf-8"` |
| 4 缺 cublas DLL | 能用但每句 ~6s（偷偷用 CPU） | sitecustomize.py 加 `os.add_dll_directory` |
| 5 Ctrl+C 關不掉 | PyQt 事件迴圈吃掉 SIGINT | main.py 裝 SIGINT handler + no-op QTimer |

> 坑5 補充：whisper-writer 是 PyQt GUI，`app.exec_()` 會阻塞 Python 的 SIGINT 處理，
> 終端機 Ctrl+C 因此無效；存設定後的 `restart_app` 又用 `QProcess.startDetached` 把程序
> 脫離 console group，更收不到訊號。`install.ps1` 會自動 patch main.py 裝 SIGINT handler
> 並跑一個 no-op QTimer 定時把控制權交還直譯器。**最省事的停止方式**：用 `stop-voice.ps1`，
> 或直接用桌面 App（關窗即停）。

---

## 效能（RTX 5090，large-v3）

| 情境 | 裝置 | 一句延遲 |
|---|---|---|
| 純運算 benchmark（5 秒音檔，warmup 後） | **CUDA（修好坑4）** | **~236 ms** |
| 實際語音輸入端到端（含錄音/VAD/打字） | **CUDA** | **~1 秒，很順** |
| 坑4 未修（靜默用 CPU） | CPU | ~6 秒 |

第一句會多 1～2 秒（CUDA kernel warmup），第二句起就是上面的滿速體驗。

---

## 其他眉角
- **熱鍵要「按住不放」**講話，講完才放（`hold_to_record` 模式），不是按一下。
- 換麥克風後要**重啟** whisper-writer，否則抓的是舊的預設裝置（可能噴 `PortAudioError: Error querying device -1`）。
- Windows「設定 → 隱私權 → 麥克風」要允許桌面應用程式存取；輸入音量別設 0/靜音。
- 終端機視窗別關（關了 app 就停）；想背景常駐可做開機排程。

## 授權
MIT。whisper-writer / Ollama / Continue 各依其原授權。
