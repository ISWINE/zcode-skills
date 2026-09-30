# -*- coding: utf-8 -*-
"""沙雕风卡片生成器：高饱和渐变底+熊猫头表情包角色+综艺花字（1920x1080 直出）"""
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
CARD_DIR = ROOT / "materials" / "cards"
W, H = 1920, 1080
HEI = "C:/Windows/Fonts/simhei.ttf"
HEI_B = "C:/Windows/Fonts/simhei.ttf"  # 黑体本身够粗，配描边
YH_B = "C:/Windows/Fonts/msyhbd.ttc"

NAME_TAG = {
    "白骨精": "#E84393", "悟空": "#0984E3", "八戒": "#D35400",
    "唐僧": "#6C5CE7", "小妖": "#00B894", "旁白": "#2D3436",
}


def hexrgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def gradient_bg(c1, c2):
    a, b = hexrgb(c1), hexrgb(c2)
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)],
               fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    # 半调网点
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    for y in range(-40, H, 56):
        off = 28 if (y // 56) % 2 else 0
        for x in range(-40 + off, W, 56):
            dm.ellipse([x, y, x + 14, y + 14], fill=26)
    img.paste(Image.new("RGB", (W, H), (255, 255, 255)), (0, 0), m)
    return img


def thick_line(d, pts, fill, width):
    d.line(pts, fill=fill, width=width)
    for p in (pts[0], pts[-1]):
        d.ellipse([p[0] - width // 2, p[1] - width // 2,
                   p[0] + width // 2, p[1] + width // 2], fill=fill)


def draw_panda(img, cx, cy, s, expr, seed=0):
    """熊猫头表情包：s=脸直径"""
    rnd = random.Random(seed)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    black, white = (25, 25, 25, 255), (255, 255, 255, 255)
    r = s // 2
    # 耳朵
    er = int(r * 0.42)
    for ex in (cx - int(r * 0.72), cx + int(r * 0.72)):
        d.ellipse([ex - er, cy - int(r * 0.86) - er, ex + er, cy - int(r * 0.86) + er],
                  fill=black)
    # 脸
    d.ellipse([cx - r, cy - int(r * 0.9), cx + r, cy + int(r * 0.95)], fill=white,
              outline=black, width=10)
    ey, ew = cy - int(r * 0.18), int(r * 0.46)   # 眼位/眼斑宽
    exl, exr = cx - int(r * 0.52), cx + int(r * 0.52)
    # 眼斑（黑圆）
    for ex in (exl, exr):
        d.ellipse([ex - ew, ey - int(ew * 0.82), ex + ew, ey + int(ew * 0.82)], fill=black)
    ink = (255, 255, 255, 255)

    def eye_dot(ex, dy=0, rr=None):
        rr = rr or int(ew * 0.34)
        d.ellipse([ex - rr, ey + dy - rr, ex + rr, ey + dy + rr], fill=ink)

    def eye_slash(ex, tilt):
        thick_line(d, [(ex - ew * 0.5, ey + tilt * ew * 0.4),
                       (ex + ew * 0.5, ey - tilt * ew * 0.4)], ink, int(s * 0.05))

    my = cy + int(r * 0.42)
    if expr == "normal":
        for ex in (exl, exr):
            eye_dot(ex)
        d.arc([cx - int(r * 0.3), my - int(r * 0.16), cx + int(r * 0.3), my + int(r * 0.2)],
              20, 160, fill=ink, width=int(s * 0.05))
    elif expr == "evil":  # 奸笑：眯眼+嘴角上挑+阴影
        for ex, t in ((exl, -1), (exr, 1)):
            eye_slash(ex, t)
        d.arc([cx - int(r * 0.36), my - int(r * 0.3), cx + int(r * 0.36), my + int(r * 0.24)],
              10, 120, fill=ink, width=int(s * 0.055))
        m2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(m2).polygon([(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy),
                                    (cx - r, cy)], fill=(120, 120, 130, 60))
        lay = Image.alpha_composite(lay, m2)
        d = ImageDraw.Draw(lay)
    elif expr == "angry":  # 怒：圆瞪眼+青筋+张嘴吼
        for ex in (exl, exr):
            rr = int(ew * 0.42)
            d.ellipse([ex - rr, ey - rr, ex + rr, ey + rr], fill=ink)
        d.ellipse([cx - int(r * 0.34), my - int(r * 0.2), cx + int(r * 0.34), my + int(r * 0.34)],
                  fill=(40, 20, 20, 255), outline=ink, width=int(s * 0.04))
        vx, vy = cx + int(r * 0.82), cy - int(r * 0.95)
        for a in (0, 90, 45, 135):
            rad = math.radians(a - 45)
            dx, dy = math.cos(rad) * s * 0.09, math.sin(rad) * s * 0.09
            thick_line(d, [(vx, vy), (vx + dx, vy + dy)], (231, 76, 60, 255), int(s * 0.035))
    elif expr == "shock":  # 瞳孔地震：小眼点+大张嘴+汗滴
        for ex in (exl, exr):
            eye_dot(ex, rr=int(ew * 0.2))
        d.ellipse([cx - int(r * 0.26), my - int(r * 0.1), cx + int(r * 0.26), my + int(r * 0.4)],
                  fill=(40, 20, 20, 255), outline=ink, width=int(s * 0.04))
        sx, sy = cx + int(r * 0.88), cy - int(r * 0.5)
        d.polygon([(sx, sy), (sx + s * 0.09, sy + s * 0.16), (sx - s * 0.02, sy + s * 0.15)],
                  fill=(116, 185, 255, 255), outline=(41, 128, 210, 255))
    elif expr == "cry":  # 泪流：X 眼+泪河
        for ex, t in ((exl, 1), (exr, -1)):
            thick_line(d, [(ex - ew * 0.4, ey - ew * 0.3), (ex + ew * 0.4, ey + ew * 0.3)],
                       ink, int(s * 0.05))
            thick_line(d, [(ex + ew * 0.4, ey - ew * 0.3), (ex - ew * 0.4, ey + ew * 0.3)],
                       ink, int(s * 0.05))
        d.arc([cx - int(r * 0.3), my - int(r * 0.3), cx + int(r * 0.3), my + int(r * 0.1)],
              20, 160, fill=ink, width=int(s * 0.05))
        for ex in (exl, exr):
            d.rounded_rectangle([ex - s * 0.03, ey + ew * 0.5, ex + s * 0.03, ey + s * 0.34],
                                radius=int(s * 0.03), fill=(116, 185, 255, 235))
    elif expr == "happy":  # 笑哭：眯眼倒 V+泪花
        for ex in (exl, exr):
            d.arc([ex - ew * 0.5, ey - ew * 0.4, ex + ew * 0.5, ey + ew * 0.4],
                  200, 340, fill=ink, width=int(s * 0.05))
            d.ellipse([ex + ew * 0.3, ey - ew * 0.5, ex + ew * 0.6, ey - ew * 0.1],
                      fill=(116, 185, 255, 235))
        d.arc([cx - int(r * 0.38), my - int(r * 0.34), cx + int(r * 0.38), my + int(r * 0.3)],
              15, 165, fill=ink, width=int(s * 0.055))
        thick_line(d, [(cx - int(r * 0.3), my + int(r * 0.1)),
                       (cx - int(r * 0.12), my + int(r * 0.22))], ink, int(s * 0.04))
    elif expr == "worship":  # 星星眼：五角星+小嘴
        for ex in (exl, exr):
            star = [(ex + s * 0.10 * math.cos(math.radians(a - 90)),
                     ey + s * 0.10 * math.sin(math.radians(a - 90)))
                    if a % 72 == 0 else
                    (ex + s * 0.045 * math.cos(math.radians(a - 90)),
                     ey + s * 0.045 * math.sin(math.radians(a - 90)))
                    for a in range(0, 360, 36)]
            d.polygon(star, fill=(253, 224, 71, 255), outline=ink)
        d.ellipse([cx - int(r * 0.1), my, cx + int(r * 0.1), my + int(r * 0.18)], fill=ink)
    elif expr == "dead":  # 眼 X + 波浪嘴 + 灰调
        for ex in (exl, exr):
            for t in ((1, -1), (-1, 1)):
                thick_line(d, [(ex - t[0] * ew * 0.4, ey - t[1] * ew * 0.3),
                               (ex + t[0] * ew * 0.4, ey + t[1] * ew * 0.3)],
                           ink, int(s * 0.05))
        pts = [(cx - int(r * 0.3) + i * r * 0.1, my + (r * 0.08 if i % 2 else -r * 0.08))
               for i in range(7)]
        thick_line(d, pts, ink, int(s * 0.045))
        grey = Image.new("RGBA", (W, H), (110, 110, 120, 70))
        lay = Image.alpha_composite(lay, grey)
    img.paste(lay, (0, 0), lay)
    return d


def name_tag(img, who, cx, cy):
    d = ImageDraw.Draw(img, "RGBA")
    f = ImageFont.truetype(YH_B, 44)
    tw = d.textlength(who, font=f)
    d.rounded_rectangle([cx - tw / 2 - 26, cy - 36, cx + tw / 2 + 26, cy + 40],
                        radius=22, fill=hexrgb(NAME_TAG.get(who, "#2D3436")))
    d.text((cx, cy + 2), who, font=f, fill=(255, 255, 255), anchor="mm")


def big_top(img, text, y=150, rot=-2):
    """综艺花字：黑体+白底描边+黑外描边，微旋转"""
    f = ImageFont.truetype(HEI, 150)
    pad = 60
    tmp = Image.new("RGBA", (W, 320 + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((W // 2, 160 + pad), text, font=f, fill=(255, 235, 59, 255),
           anchor="mm", stroke_width=14, stroke_fill=(20, 20, 20, 255))
    tmp = tmp.rotate(rot, resample=Image.BICUBIC, center=(W // 2, 160 + pad))
    img.alpha_composite(tmp, (0, y - pad))


def badge_ribbon(img, text, x, y, rot=8, fill="#FF3B30", fs=76):
    f = ImageFont.truetype(HEI, fs)
    tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    tw = d.textlength(text, font=f)
    cx, cy = W // 2, y
    d.polygon([(cx - tw / 2 - 70, cy - 62), (cx + tw / 2 + 70, cy - 62),
               (cx + tw / 2 + 10, cy), (cx + tw / 2 + 70, cy + 62),
               (cx - tw / 2 - 70, cy + 62), (cx - tw / 2 - 10, cy)],
              fill=hexrgb(fill))
    d.text((cx, cy), text, font=f, fill=(255, 255, 255), anchor="mm",
           stroke_width=8, stroke_fill=(255, 255, 255, 90))
    tmp = tmp.rotate(rot, resample=Image.BICUBIC, center=(cx, cy))
    img.alpha_composite(tmp, (0, 0))


def corner_label(img, text):
    d = ImageDraw.Draw(img, "RGBA")
    f = ImageFont.truetype(YH_B, 40)
    d.text((44, 36), text, font=f, fill=(255, 255, 255, 230),
           stroke_width=5, stroke_fill=(20, 20, 20, 200))


def main():
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / "materials" / "scenes.json").read_text(encoding="utf-8"))
    for s in cfg["scenes"]:
        img = gradient_bg(*s["bg"]).convert("RGBA")
        chars = s.get("chars", [])
        n = len(chars)
        xs = [W // 4] if n == 1 else ([W // 4, 3 * W // 4] if n == 2 else
                                      [W // 6, W // 2, 5 * W // 6])
        size = 620 if n <= 2 else 520
        for i, ch in enumerate(chars):
            cx = xs[i]
            cy = H // 2 + 90 if n <= 2 else H // 2 + 110
            draw_panda(img, cx, cy, size, ch["expr"], seed=s["seed"] + i)
            name_tag(img, ch["who"], cx, cy + size // 2 + 90)
        big_top(img, s.get("top", ""), y=60)
        if s.get("badge"):
            badge_ribbon(img, s["badge"], 0, H - 170)
        corner_label(img, s["corner_label"])
        img = img.convert("RGB")
        img.save(CARD_DIR / f"{s['id']}.png")
        print("card ok:", s["id"])


if __name__ == "__main__":
    main()
