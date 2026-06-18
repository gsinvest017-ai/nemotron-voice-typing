#Requires -Version 7
<#
.SYNOPSIS
    一鍵安裝 Nemotron + Whisper 地端語音輸入 vibe coding 套件（Windows + NVIDIA GPU）。
.DESCRIPTION
    自動處理整套安裝，並內建我們實際踩過的 4 個坑的解法：
      坑1 Blackwell(RTX 50 系/sm_120) 不支援 repo 釘死的舊 ctranslate2
      坑2 requirements.txt 釘死舊版在 Python 3.12 編譯失敗 -> 中斷整批安裝
      坑3 config 用 cp950 讀 UTF-8 中文炸 UnicodeDecodeError
      坑4 cublas64_12.dll 找不到 -> faster-whisper 靜默 fallback 到 CPU（慢 20 倍）
.EXAMPLE
    pwsh -File install.ps1
.EXAMPLE
    pwsh -File install.ps1 -WhisperModel large-v3-turbo -SkipContinue
#>
[CmdletBinding()]
param(
    [string]$InstallDir   = "$HOME\tools\whisper-writer",
    [string]$WhisperRepo  = "https://github.com/verbumeng/whisper-writer",
    [string]$OllamaModel  = "nemotron-3-nano:30b",
    [string]$WhisperModel = "large-v3",
    [string]$Hotkey       = "ctrl+shift+space",
    [switch]$SkipOllama,        # 不下載 LLM（只裝語音輸入）
    [switch]$SkipModelPull,     # 裝 Ollama 但不 pull 模型
    [switch]$SkipContinue       # 不裝 VS Code Continue 擴充
)

$ErrorActionPreference = 'Stop'
$RepoRoot = $PSScriptRoot

function Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Info($m) { Write-Host "  $m" -ForegroundColor Gray }
function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!] $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "  [X] $m" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
Step "0. 檢查前置工具"
$git = (Get-Command git -ErrorAction SilentlyContinue)
if (-not $git) { Die "找不到 git，請先安裝 https://git-scm.com" }
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { Die "找不到 python，請先安裝 Python 3.10+ https://python.org" }
$pyver = (& python -c "import sys;print('%d.%d'%sys.version_info[:2])")
Ok "python $pyver / git $($git.Version)"

# GPU 偵測：決定走 CUDA 還是 CPU
$hasGpu = $false
$gpuName = $null
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $gpuName = (nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1)
    if ($gpuName) { $hasGpu = $true }
}
if ($hasGpu) {
    $Device = "cuda"; $Compute = "float16"
    Ok "偵測到 GPU: $gpuName -> 走 CUDA float16"
} else {
    $Device = "cpu"; $Compute = "int8"
    Warn "沒偵測到 NVIDIA GPU -> 走 CPU int8（會比較慢）"
}

# ---------------------------------------------------------------------------
if (-not $SkipOllama) {
    Step "1. Ollama + Nemotron LLM"
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Warn "找不到 ollama，請先安裝 https://ollama.com（或加 -SkipOllama 跳過）"
    } else {
        Ok "ollama $((ollama --version) 2>$null)"
        if (-not $SkipModelPull) {
            Info "pull $OllamaModel（24GB 量級，第一次很久）..."
            ollama pull $OllamaModel
            Ok "$OllamaModel ready"
        }
    }
}

# ---------------------------------------------------------------------------
Step "2. 取得 whisper-writer"
if (Test-Path "$InstallDir\.git") {
    Info "已存在，git pull 更新"
    git -C $InstallDir pull --ff-only 2>&1 | Select-Object -Last 1
} else {
    New-Item -ItemType Directory -Force (Split-Path $InstallDir) | Out-Null
    git clone --depth 1 $WhisperRepo $InstallDir
}
Ok $InstallDir

# ---------------------------------------------------------------------------
Step "3. 建立 venv + 安裝依賴（避開坑1、坑2）"
$venvPy = "$InstallDir\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { & python -m venv "$InstallDir\.venv" }
& $venvPy -m pip install --upgrade pip --quiet

# 坑2：不要用 repo 的 requirements.txt（釘死 numpy==1.24.3 等在 3.12 編不過、會中斷整批）。
#       改裝不釘版本的執行期套件。
$runtime = @(
    "python-dotenv","PyQt5","pynput","sounddevice","soundfile","pyperclip",
    "webrtcvad-wheels","PyGetWindow","audioplayer","coloredlogs","openai",
    "mss","pyscreenshot","numpy"
)
Info "安裝執行期套件..."
& $venvPy -m pip install --quiet @runtime
# 坑1：Blackwell(sm_120) 需要新版 ctranslate2 + faster-whisper（repo 釘的 4.2.1 跑不動）。
Info "安裝 ML 引擎（新版以支援新顯卡）..."
& $venvPy -m pip install --quiet --upgrade "ctranslate2>=4.5.0" "faster-whisper>=1.1.0"
if ($hasGpu) {
    Info "安裝 CUDA 函式庫 (cublas/cudnn)..."
    & $venvPy -m pip install --quiet --upgrade nvidia-cublas-cu12 nvidia-cudnn-cu12
}
Ok "依賴安裝完成"

# ---------------------------------------------------------------------------
if ($hasGpu) {
    Step "4. 修坑4：讓 ctranslate2 找得到 CUDA DLL（否則靜默掉 CPU）"
    $sitePkg = (& $venvPy -c "import site;print(site.getsitepackages()[-1])").Trim()
    Copy-Item "$RepoRoot\patches\sitecustomize.py" "$sitePkg\sitecustomize.py" -Force
    Ok "已部署 sitecustomize.py -> $sitePkg"
}

# ---------------------------------------------------------------------------
Step "5. 修坑3：config 讀寫改 UTF-8（中文設定不再 cp950 炸掉）"
$utils = "$InstallDir\src\utils.py"
$c = Get-Content $utils -Raw -Encoding utf8
$c = $c -replace 'open\(config_path, "r"\) as file', 'open(config_path, "r", encoding="utf-8") as file'
$c = $c -replace 'open\(config_path, "w"\) as file', 'open(config_path, "w", encoding="utf-8") as file'
$c = $c -replace 'yaml\.dump\(cls\._instance\.config, file, default_flow_style=False\)', 'yaml.dump(cls._instance.config, file, default_flow_style=False, allow_unicode=True)'
Set-Content $utils $c -Encoding utf8 -NoNewline
Ok "utils.py 已 patch UTF-8"

# ---------------------------------------------------------------------------
Step "6. 寫入 whisper-writer 設定 (src/config.yaml)"
$cfg = @"
# 由 nemotron-voice-typing/install.ps1 產生
model_options:
  use_api: false
  common:
    language: null
    initial_prompt: "以下是程式設計相關的口語指令，可能中英夾雜。"
  local:
    model: $WhisperModel
    device: $Device
    compute_type: $Compute
    vad_filter: true
recording_options:
  activation_key: $Hotkey
  recording_mode: hold_to_record
post_processing:
  add_trailing_space: true
misc:
  print_to_terminal: true
  noise_on_completion: true
"@
# 用 UTF-8 寫（搭配坑3的 patch）
[System.IO.File]::WriteAllText("$InstallDir\src\config.yaml", $cfg, (New-Object System.Text.UTF8Encoding $false))
Ok "model=$WhisperModel device=$Device hotkey=$Hotkey mode=hold_to_record"

# 部署輔助腳本
Copy-Item "$RepoRoot\scripts\*.ps1" "$InstallDir\" -Force
Ok "已部署 start-voice / stop-voice / test-mic"

# ---------------------------------------------------------------------------
if (-not $SkipContinue) {
    Step "7. VS Code Continue 擴充 + 設定"
    if (Get-Command code -ErrorAction SilentlyContinue) {
        code --install-extension Continue.continue --force 2>&1 | Select-Object -Last 1
        New-Item -ItemType Directory -Force "$HOME\.continue" | Out-Null
        $cont = (Get-Content "$RepoRoot\config\continue-config.yaml" -Raw) -replace 'nemotron-3-nano:30b', $OllamaModel
        [System.IO.File]::WriteAllText("$HOME\.continue\config.yaml", $cont, (New-Object System.Text.UTF8Encoding $false))
        Ok "Continue 已設定（chat=$OllamaModel）"
    } else {
        Warn "找不到 VS Code 的 code CLI，跳過（可加 -SkipContinue 消除此訊息）"
    }
}

# ---------------------------------------------------------------------------
Step "8. 驗證 GPU 真的有吃到（直接跑一次 encode）"
$verify = @"
import time, numpy as np
from faster_whisper import WhisperModel
m = WhisperModel('$WhisperModel', device='$Device', compute_type='$Compute')
audio = (np.random.randn(3*16000)*0.05).astype(np.float32)
list(m.transcribe(audio, beam_size=1, language='zh')[0])  # warmup（同時觸發 cublas，能抓到坑4）
t=time.perf_counter()
list(m.transcribe(audio, beam_size=1, language='zh')[0])
print('TRANSCRIBE_MS=%d DEVICE=$Device' % ((time.perf_counter()-t)*1000))
"@
$out = & $venvPy -c $verify 2>&1
$ms = ($out | Select-String 'TRANSCRIBE_MS=(\d+)').Matches.Groups[1].Value
if ($ms) {
    if ($Device -eq 'cuda' -and [int]$ms -gt 2000) {
        Warn "轉錄 $ms ms 偏慢，GPU 可能沒生效（檢查 sitecustomize.py / cublas）"
    } else {
        Ok "轉錄一句 ~$ms ms on $Device（GPU 正常）"
    }
} else {
    Warn "驗證未取得計時，輸出如下："; $out | Select-Object -Last 8 | ForEach-Object { Info $_ }
}

# ---------------------------------------------------------------------------
Step "完成 🎉"
Write-Host @"
  啟動語音輸入：  & "$InstallDir\start-voice.ps1"
  停止：          & "$InstallDir\stop-voice.ps1"
  測麥克風：      & "$InstallDir\test-mic.ps1"

  用法：在任何視窗按住「$Hotkey」說話，放開即把辨識文字打進游標處。
  VS Code vibe coding：Ctrl+I 開 Continue 對話框 -> 按住熱鍵說需求 -> 放開 -> Enter。
"@ -ForegroundColor White
