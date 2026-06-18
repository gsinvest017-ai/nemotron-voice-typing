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

## 一鍵安裝

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

---

## 效能（RTX 5090，5 秒音檔，warmup 後）

| 模型 | 裝置 | 一句轉錄 |
|---|---|---|
| large-v3 | **CUDA（修好坑4）** | **~236 ms** |
| large-v3 | CPU（坑4 fallback） | ~6000 ms |

第一句會多 1～2 秒（CUDA kernel warmup），第二句起才是滿速。

---

## 其他眉角
- **熱鍵要「按住不放」**講話，講完才放（`hold_to_record` 模式），不是按一下。
- 換麥克風後要**重啟** whisper-writer，否則抓的是舊的預設裝置（可能噴 `PortAudioError: Error querying device -1`）。
- Windows「設定 → 隱私權 → 麥克風」要允許桌面應用程式存取；輸入音量別設 0/靜音。
- 終端機視窗別關（關了 app 就停）；想背景常駐可做開機排程。

## 授權
MIT。whisper-writer / Ollama / Continue 各依其原授權。
