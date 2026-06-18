"""管理 whisper-writer 語音輸入子程序（啟動 / 停止 / 狀態）。

設計：whisper-writer 安裝在獨立 venv（~/tools/whisper-writer，由 install.ps1 建），
本控制器以子程序方式啟動它的 run.py，並用程序掃描判斷是否運作中 / 停止它
（whisper-writer 的 run.py 會再 spawn 一個 main.py 子程序，所以用「掃描 cmdline
含安裝目錄名的 python.exe」最可靠，而不是只追單一 PID）。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000


def whisper_dir() -> Path:
    """whisper-writer 安裝目錄，可用環境變數 NVT_WHISPER_DIR 覆蓋。"""
    env = os.environ.get("NVT_WHISPER_DIR")
    return Path(env) if env else (Path.home() / "tools" / "whisper-writer")


def venv_python() -> Path:
    return whisper_dir() / ".venv" / "Scripts" / "python.exe"


def venv_ok() -> bool:
    """語音引擎是否已安裝（venv + run.py 都在）。"""
    return venv_python().exists() and (whisper_dir() / "run.py").exists()


def _match_pattern() -> str:
    # 以安裝目錄的最後一段當比對關鍵字（預設 'whisper-writer'）
    return whisper_dir().name


def log_path() -> Path:
    p = Path.home() / ".nemotron-voice"
    p.mkdir(parents=True, exist_ok=True)
    return p / "whisper-writer.log"


def _ps(cmd: str, timeout: float = 10.0) -> str:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def is_running() -> bool:
    pat = _match_pattern()
    cmd = (
        "(@(Get-CimInstance Win32_Process | Where-Object { "
        f"$_.Name -eq 'python.exe' -and $_.CommandLine -match '{pat}' "
        "})).Count"
    )
    try:
        return int(_ps(cmd) or "0") > 0
    except ValueError:
        return False


def start() -> bool:
    """背景啟動語音輸入（已在跑則直接回 True）。"""
    if is_running():
        return True
    if not venv_ok():
        return False
    d = whisper_dir()
    log = open(log_path(), "a", encoding="utf-8", buffering=1)
    subprocess.Popen(
        [str(venv_python()), str(d / "run.py")],
        cwd=str(d),
        stdout=log, stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    return True


def stop() -> None:
    """強制停止所有 whisper-writer python 程序。"""
    pat = _match_pattern()
    cmd = (
        "Get-CimInstance Win32_Process | Where-Object { "
        f"$_.Name -eq 'python.exe' -and $_.CommandLine -match '{pat}' "
        "} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    _ps(cmd)


def config_info() -> dict:
    """從 whisper-writer 的 src/config.yaml 撈出目前 model / 熱鍵（輕量解析，免 pyyaml）。"""
    cfg = whisper_dir() / "src" / "config.yaml"
    model = None
    hotkey = None
    try:
        for line in cfg.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("model:") and model is None and "whisper-1" not in s:
                model = s.split(":", 1)[1].strip()
            elif s.startswith("activation_key:"):
                hotkey = s.split(":", 1)[1].strip()
    except OSError:
        pass
    return {"model": model, "hotkey": hotkey}
