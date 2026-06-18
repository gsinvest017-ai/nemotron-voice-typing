"""控制面板的 stdlib HTTP server（不用 FastAPI/uvicorn，凍結後體積小）。

路由：
  GET  /                  -> 控制面板 HTML
  GET  /api/status        -> {running, venv_ok, model, hotkey, version, ...}
  POST /api/start         -> 背景啟動語音輸入
  POST /api/stop          -> 停止語音輸入
  GET  /api/update/check  -> updater.check_update()
  POST /api/update/apply  -> updater.apply_update()
  POST /api/setup         -> 背景跑 install.ps1 安裝語音引擎
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import APP_VERSION, manager, updater

CREATE_NO_WINDOW = 0x08000000


def _base_dir() -> Path:
    """資源根目錄：凍結時是 _MEIPASS，否則是 repo 根。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def _status() -> dict:
    info = manager.config_info()
    return {
        "version": APP_VERSION,
        "running": manager.is_running(),
        "venv_ok": manager.venv_ok(),
        "install_dir": str(manager.whisper_dir()),
        "model": info.get("model"),
        "hotkey": info.get("hotkey"),
    }


def _run_setup() -> dict:
    """背景執行 install.ps1（安裝語音引擎）。立即回傳。"""
    script = _base_dir() / "install.ps1"
    if not script.exists():
        return {"status": "error", "error": f"找不到 install.ps1：{script}"}
    log = manager.log_path().with_name("setup.log")
    try:
        with open(log, "a", encoding="utf-8") as fh:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(script), "-SkipOllama"],
                cwd=str(script.parent),
                stdout=fh, stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
            )
    except OSError as exc:
        return {"status": "error", "error": str(exc)}
    return {"status": "started", "log": str(log)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 靜音
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: dict, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            html = (_base_dir() / "static" / "control.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
        elif self.path == "/api/status":
            self._json(_status())
        elif self.path == "/api/update/check":
            self._json(updater.check_update())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/api/start":
            ok = manager.start()
            self._json({"ok": ok, **_status()})
        elif self.path == "/api/stop":
            manager.stop()
            self._json({"ok": True, **_status()})
        elif self.path == "/api/update/apply":
            self._json(updater.apply_update())
        elif self.path == "/api/setup":
            self._json(_run_setup())
        else:
            self._json({"error": "not found"}, 404)


def serve(host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.serve_forever()
