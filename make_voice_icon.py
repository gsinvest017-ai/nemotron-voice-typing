"""產生 nemotron-voice 專用 icon：麥克風 + 聲波（GS 金色主題）。

與 gs-app-pack 通用金環 icon 區隔，避免跟 gs-gh-summary 等撞圖。
用法：
  python make_voice_icon.py --out static/gs-icon.ico
  python make_voice_icon.py --out static/gs-icon.ico --preview preview.png
"""
from __future__ import annotations

import argparse
import math
from PIL import Image, ImageDraw

BG = (15, 11, 6)        # #0f0b06 warm black
GOLD = (212, 175, 55)   # #d4af37
CHAMP = (232, 209, 149) # #e8d195
COPPER = (176, 116, 64) # 銅，做漸層下緣


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _vgrad(size, top, bot):
    g = Image.new("RGB", (1, size))
    for y in range(size):
        g.putpixel((0, y), _lerp(top, bot, y / max(1, size - 1)))
    return g.resize((size, size))


def render(S: int) -> Image.Image:
    SS = 4
    W = S * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = W / 2

    # 背景圓角方塊 + 金色細邊框
    rad = int(W * 0.22)
    d.rounded_rectangle([0, 0, W - 1, W - 1], radius=rad, fill=BG + (255,))
    bw_border = max(1, int(W * 0.025))
    inset = int(W * 0.045)
    d.rounded_rectangle([inset, inset, W - 1 - inset, W - 1 - inset],
                        radius=int(rad * 0.8), outline=GOLD + (180,), width=bw_border)

    # 聲波：以麥克風中心為圓心，左右各兩道弧
    wcx, wcy = cx, W * 0.40
    for i, r in enumerate((0.32, 0.41)):
        rr = W * r
        box = [wcx - rr, wcy - rr, wcx + rr, wcy + rr]
        lw = max(1, int(W * (0.030 - i * 0.006)))
        col = _lerp(GOLD, CHAMP, i / 1.0) + (255,)
        d.arc(box, start=-42, end=42, fill=col, width=lw)        # 右
        d.arc(box, start=138, end=222, fill=col, width=lw)       # 左

    # 麥克風膠囊本體（直立漸層：上 champagne → 下 copper）
    bw, bh = W * 0.30, W * 0.40
    bx0, by0 = cx - bw / 2, W * 0.19
    bx1, by1 = cx + bw / 2, by0 + bh
    body_box = [bx0, by0, bx1, by1]
    body_mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(body_mask).rounded_rectangle(body_box, radius=int(bw / 2), fill=255)
    grad = _vgrad(W, CHAMP, COPPER).convert("RGBA")
    img.paste(grad, (0, 0), body_mask)
    d = ImageDraw.Draw(img)
    # 膠囊邊緣描金
    d.rounded_rectangle(body_box, radius=int(bw / 2), outline=GOLD + (255,),
                        width=max(1, int(W * 0.018)))
    # 三條格柵線（背景色刻痕）
    for gy in (0.30, 0.37, 0.44):
        y = W * gy
        d.line([bx0 + W * 0.05, y, bx1 - W * 0.05, y], fill=BG + (220,),
               width=max(1, int(W * 0.018)))

    # 支架 U 形托架（弧）
    hr = W * 0.21
    holder = [cx - hr, wcy - hr * 0.55, cx + hr, wcy + hr * 1.15]
    d.arc(holder, start=20, end=160, fill=GOLD + (255,), width=max(1, int(W * 0.035)))
    # 立柱
    d.line([cx, wcy + hr * 1.05, cx, W * 0.85], fill=GOLD + (255,), width=max(1, int(W * 0.04)))
    # 底座
    base_w = W * 0.13
    d.rounded_rectangle([cx - base_w, W * 0.83, cx + base_w, W * 0.875],
                        radius=int(W * 0.02), fill=GOLD + (255,))

    return img.resize((S, S), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="static/gs-icon.ico")
    ap.add_argument("--preview", default="")
    args = ap.parse_args()

    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = [render(s) for s in sizes]
    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    imgs[-1].save(args.out, format="ICO",
                  sizes=[(s, s) for s in sizes], append_images=imgs[:-1])
    print(f"wrote {args.out} ({', '.join(str(s) for s in sizes)})")
    if args.preview:
        render(256).save(args.preview)
        print(f"wrote preview {args.preview}")


if __name__ == "__main__":
    main()
