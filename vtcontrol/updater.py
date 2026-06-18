"""自我更新 — 檢查 GitHub Release，下載最新安裝檔靜默升級。

改寫自 autogo/src/autogo_dash/updater.py。差異：
  - repo 改為 gsinvest017-ai/nemotron-voice-typing
  - 版號讀 vtcontrol.APP_VERSION（凍結後沒有 pyproject 可讀）
  - 安裝檔走 Inno Setup 的 .exe（/VERYSILENT 靜默升級），非 MSI
  - 「已安裝」= 以凍結 exe 形式執行（sys.frozen）；dev 直跑不自我升級

repo 為 private，每個 GitHub 呼叫都需要 token。解析順序：
  NVT_GH_TOKEN / GH_TOKEN / GITHUB_TOKEN 環境變數
  → ~/.config/nemotron-voice-typing/gh-token
  → gh auth token（gh CLI 已登入時）
無 token 時降級為「讀不到 release」，UI 改顯示手動下載連結。
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

from . import APP_VERSION

logger = logging.getLogger(__name__)

DEFAULT_REPO = "gsinvest017-ai/nemotron-voice-typing"
_VER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
CREATE_NO_WINDOW = 0x08000000


def repo() -> str:
    return (os.environ.get("NVT_UPDATE_REPO") or DEFAULT_REPO).strip()


def _parse_ver(s: str) -> Optional[Tuple[int, int, int]]:
    m = _VER_RE.search(s or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def local_version() -> str:
    return APP_VERSION


def is_newer(latest: str, current: str) -> bool:
    lt, cur = _parse_ver(latest), _parse_ver(current)
    if lt is None or cur is None:
        return False
    return lt > cur


def is_installed() -> bool:
    """以凍結 exe（PyInstaller）形式執行才算安裝版，dev 直跑不自我升級。"""
    return bool(getattr(sys, "frozen", False))


# ---- auth ---- #

def gh_token() -> Optional[str]:
    for env in ("NVT_GH_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        v = (os.environ.get(env) or "").strip()
        if v:
            return v
    tok_file = Path.home() / ".config" / "nemotron-voice-typing" / "gh-token"
    try:
        if tok_file.exists():
            t = tok_file.read_text(encoding="utf-8").strip()
            if t:
                return t
    except OSError:
        pass
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True,
                             text=True, timeout=6, creationflags=CREATE_NO_WINDOW)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


# ---- release query ---- #

def _api_get(path: str, token: Optional[str], timeout: float = 8.0) -> Optional[dict]:
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "nemotron-voice-updater")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as exc:  # noqa: BLE001
        logger.info("release API call failed: %s", exc)
        return None


def _pick_asset(assets: list) -> Optional[dict]:
    """優先 .exe（Inno 安裝檔），否則 .msi。"""
    exes = [a for a in assets if str(a.get("name", "")).lower().endswith(".exe")]
    msis = [a for a in assets if str(a.get("name", "")).lower().endswith(".msi")]
    chosen = (exes or msis)
    return chosen[0] if chosen else None


def check_update() -> dict:
    """比對本機版號與最新 release。永不丟例外。"""
    current = local_version()
    token = gh_token()
    result = {
        "current": current, "latest": None, "tag": None,
        "update_available": False, "notes": None,
        "asset_id": None, "asset_name": None,
        "auth_ok": False, "installed": is_installed(),
        "repo": repo(), "error": None,
    }
    data = _api_get(f"/repos/{repo()}/releases/latest", token)
    if data is None:
        result["error"] = (
            "無法讀取 GitHub Release（repo 為 private，需設定 token 或 gh auth login）"
            if not token else "GitHub API 讀取失敗"
        )
        return result
    result["auth_ok"] = True
    tag = data.get("tag_name") or ""
    latest = tag.lstrip("v")
    asset = _pick_asset(data.get("assets") or [])
    result.update({
        "latest": latest, "tag": tag,
        "notes": (data.get("body") or "")[:2000],
        "update_available": is_newer(latest, current),
        "asset_id": asset.get("id") if asset else None,
        "asset_name": asset.get("name") if asset else None,
    })
    return result


# ---- apply ---- #

def _download_asset(tag: str, asset_name: str, token: Optional[str], dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 1) gh CLI（處理 private repo 認證 + S3 redirect 最乾淨）
    try:
        out = subprocess.run(
            ["gh", "release", "download", tag, "--repo", repo(),
             "--pattern", asset_name, "--output", str(dest), "--clobber"],
            capture_output=True, text=True, timeout=600, creationflags=CREATE_NO_WINDOW,
        )
        if out.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    # 2) 手動：asset API + octet-stream，redirect 時丟掉 Authorization（S3 會拒）
    if not token:
        return False
    rel = _api_get(f"/repos/{repo()}/releases/tags/{tag}", token)
    if not rel:
        return False
    asset = next((a for a in (rel.get("assets") or [])
                  if a.get("name") == asset_name), None)
    if not asset:
        return False
    asset_url = f"https://api.github.com/repos/{repo()}/releases/assets/{asset['id']}"

    class _NoAuthRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            new = super().redirect_request(req, fp, code, msg, headers, newurl)
            if new is not None:
                new.headers.pop("Authorization", None)
            return new

    opener = urllib.request.build_opener(_NoAuthRedirect())
    req = urllib.request.Request(asset_url)
    req.add_header("Accept", "application/octet-stream")
    req.add_header("User-Agent", "nemotron-voice-updater")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with opener.open(req, timeout=600) as resp, open(dest, "wb") as fh:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                fh.write(chunk)
        return dest.exists() and dest.stat().st_size > 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("manual asset download failed: %s", exc)
        return False


def _write_updater_script(installer: Path, exe_name: str, exe_path: Path, script: Path) -> None:
    """detached PS1：等待 → 停 app → /VERYSILENT 安裝 → 重啟 app。"""
    runlog = script.with_suffix(".run.log")
    body = f"""
$log = "{runlog}"
function L($m) {{ "$(Get-Date -Format o)  $m" | Out-File -FilePath $log -Append -Encoding utf8 }}
"=== nemotron-voice self-update ===" | Out-File -FilePath $log -Encoding utf8
try {{
  Start-Sleep -Seconds 2
  L "stopping {exe_name}"
  Get-Process -Name "{exe_name}" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 1
  L "running installer"
  $p = Start-Process -FilePath "{installer}" -Wait -PassThru -ArgumentList @('/VERYSILENT','/NORESTART','/SUPPRESSMSGBOXES')
  L "installer exit $($p.ExitCode)"
  Start-Sleep -Seconds 1
  L "relaunching"
  Start-Process -FilePath "{exe_path}"
  L "done"
}} catch {{
  L "ERROR $_"
}}
"""
    # 用 utf-8-sig（帶 BOM）寫入！detached updater 用 Windows PowerShell 5.1 執行，
    # 無 BOM 的 .ps1 會被當 cp950 解讀，含中文的安裝路徑（如「Nemotron 語音輸入」）
    # 會變亂碼導致 relaunch「系統找不到指定的檔案」。BOM 讓 PS 5.1 / 7 都正確讀 UTF-8。
    script.write_text(body, encoding="utf-8-sig")


def apply_update(asset_name: Optional[str] = None) -> dict:
    """下載最新安裝檔並交給 detached updater 升級。立即回傳 {status: updating}。"""
    if not is_installed():
        return {"status": "refused",
                "error": "非安裝版（dev 直跑）——請用 git pull 更新"}
    info = check_update()
    if not info.get("auth_ok"):
        return {"status": "error", "error": info.get("error") or "無法存取 release"}
    if not info.get("update_available"):
        return {"status": "up-to-date", "current": info["current"]}
    name = asset_name or info.get("asset_name")
    if not name:
        return {"status": "error", "error": "release 沒有可用的安裝檔資產"}

    tmp = Path(tempfile.gettempdir())
    installer = tmp / f"nemotron-voice-update-{info['latest']}.exe"
    if not _download_asset(info["tag"], name, gh_token(), installer):
        return {"status": "error", "error": "下載安裝檔失敗（檢查 token / 網路）"}

    exe_path = Path(sys.executable)
    exe_name = exe_path.stem
    script = tmp / "nemotron-voice-self-update.ps1"
    _write_updater_script(installer, exe_name, exe_path, script)

    CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        devnull = open(os.devnull, "r+b")  # noqa: SIM115 — 交給子程序
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
            stdin=devnull, stdout=devnull, stderr=devnull, close_fds=True,
        )
    except OSError as exc:
        return {"status": "error", "error": f"啟動更新程序失敗：{exc}"}
    return {"status": "updating", "from": info["current"], "to": info["latest"]}
