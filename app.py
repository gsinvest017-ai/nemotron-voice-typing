"""Nemotron 語音輸入 — 桌面控制器入口（pywebview）。

行為（符合需求）：
  - 點擊圖示開啟 → 控制面板視窗 + 自動在「背景」啟動語音輸入
  - 關閉視窗 → 停止背景語音輸入
基底改寫自 gs-app-pack/templates/app_launcher.py。
"""
from __future__ import annotations

import argparse
import atexit
import logging
import math
import socket
import struct
import sys
import threading
import time
from pathlib import Path

if getattr(sys, "frozen", False):
    _BASE = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    sys.path.insert(0, str(_BASE))
else:
    _BASE = Path(__file__).resolve().parent

from vtcontrol import manager  # noqa: E402
from vtcontrol.server import serve  # noqa: E402

# pythonw/--windowed 下 stdout/stderr 為 None，先導向 devnull 避免 logging 崩潰
import os  # noqa: E402
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

log = logging.getLogger("nemotron-voice")

_WIN_TITLE = "Nemotron 語音輸入"
_WIN_WIDTH = 660
_WIN_HEIGHT = 580
_WIN_BG = "#0f0b06"
_DWM_CAPTION = 0x00060B0F   # #0f0b06
_DWM_BORDER = 0x0037AFD4    # #d4af37 gold
_DWM_TEXT = 0x0095D1E8      # #e8d195 champagne
_ICON_BG = "#0f0b06"
_ICON_RING = "#d4af37"
_ICON_SIZE = 32
_SERVER_HOST = "127.0.0.1"
_SERVER_PORT = 8791


# ── icon ───────────────────────────────────────────────────────────────────
def _hex_to_bgra(hex_color: str) -> bytes:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return bytes([b, g, r, 255])


def _make_icon_ico(size=32, bg="#0f0b06", ring="#d4af37") -> bytes:
    BG, GOLD = _hex_to_bgra(bg), _hex_to_bgra(ring)
    cx = cy = (size - 1) / 2.0
    r_outer, r_inner = size * 0.42, size * 0.22

    def lerp4(a, b, t):
        t = max(0.0, min(1.0, t))
        return bytes(int(a[i] + (b[i] - a[i]) * t) for i in range(4))

    rows = []
    for y in range(size - 1, -1, -1):
        row = bytearray()
        for x in range(size):
            d = math.hypot(x - cx, y - cy)
            if d <= r_inner - 0.5: row += BG
            elif d <= r_inner + 0.5: row += lerp4(BG, GOLD, d - (r_inner - 0.5))
            elif d <= r_outer - 0.5: row += GOLD
            elif d <= r_outer + 0.5: row += lerp4(GOLD, BG, d - (r_outer - 0.5))
            else: row += BG
        rows.append(bytes(row))
    pixel = b"".join(rows)
    and_mask = bytes(((size + 31) // 32 * 4) * size)
    bih = struct.pack("<IIIHHIIIIII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    image = bih + pixel + and_mask
    return (struct.pack("<HHH", 0, 1, 1)
            + struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(image), 22)
            + image)


def _ensure_icon():
    p = _BASE / "static" / "gs-icon.ico"
    if not p.exists():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(_make_icon_ico(_ICON_SIZE, _ICON_BG, _ICON_RING))
        except Exception as exc:
            log.warning("icon gen failed: %s", exc)
            return None
    return p


def _apply_win32_style(icon_path):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = 0
        deadline = time.monotonic() + 5.0
        while not hwnd and time.monotonic() < deadline:
            hwnd = ctypes.windll.user32.FindWindowW(None, _WIN_TITLE)
            if not hwnd:
                time.sleep(0.1)
        if not hwnd:
            return

        def _dwm(attr, colorref):
            v = ctypes.c_int(colorref)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

        _dwm(35, _DWM_CAPTION); _dwm(34, _DWM_BORDER); _dwm(36, _DWM_TEXT)
        if icon_path and icon_path.exists():
            for sz, kind in ((32, 1), (16, 0)):
                hicon = ctypes.windll.user32.LoadImageW(None, str(icon_path), 1, sz, sz, 0x10)
                if hicon:
                    ctypes.windll.user32.SendMessageW(hwnd, 0x80, kind, hicon)
    except Exception as exc:
        log.warning("win32 style failed: %s", exc)


# ── server helpers ───────────────────────────────────────────────────────────
def _port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _find_free_port(pref):
    if _port_is_free(pref):
        return pref
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(port, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


# ── entry ────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=_SERVER_PORT)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
                        datefmt="%H:%M:%S")

    port = _find_free_port(args.port)
    threading.Thread(target=serve, args=(_SERVER_HOST, port), daemon=True,
                     name="control-server").start()
    if not _wait_for_server(port):
        log.error("control server did not start")
        return 1

    # 開窗即背景啟動語音輸入；關窗時停止。
    def _shutdown():
        try:
            manager.stop()
        except Exception:
            pass
    atexit.register(_shutdown)
    if manager.venv_ok():
        try:
            manager.start()
        except Exception as exc:
            log.warning("auto-start failed: %s", exc)

    icon = _ensure_icon()
    url = f"http://{_SERVER_HOST}:{port}/"
    log.info("control panel at %s", url)
    try:
        import webview
    except ImportError:
        log.error("pywebview not installed")
        return 1

    webview.create_window(_WIN_TITLE, url, width=_WIN_WIDTH, height=_WIN_HEIGHT,
                          resizable=True, min_size=(560, 480), background_color=_WIN_BG)
    webview.start(func=lambda: _apply_win32_style(icon), debug=False)
    _shutdown()  # 視窗關閉後確保停止背景語音輸入
    return 0


if __name__ == "__main__":
    sys.exit(main())
