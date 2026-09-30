# -*- coding: utf-8 -*-
"""生成《三打白骨精》水墨风格故事卡（3840x2160 PNG）"""
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
CARD_DIR = ROOT / "materials" / "cards"
W, H = 3840, 2160
KAI = "C:/Windows/Fonts/simkai.ttf"
YH_B = "C:/Windows/Fonts/msyhbd.ttc"


def paper(rgb, seed):
    rnd = random.Random(seed)
    img = Image.new("RGB", (W, H), tuple(rgb))
    noise = Image.effect_noise((W, H), 22).convert("RGB")
    img = Image.blend(img, noise, 0.055)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(150):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        ln = rnd.uniform(60, 360)
        slope = rnd.uniform(-0.15, 0.15)
        shade = rnd.choice([(255, 252, 240), (206, 198, 180)])
        d.line([(x, y), (x + ln, y + ln * slope)], fill=shade + (rnd.randint(8, 20),),
               width=rnd.choice([1, 2]))
    return img


def ridge(img, base_y, amp, color, alpha, seed, blur=4):
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, 2 * math.pi) for _ in range(4)]
    pts = []
    for x in range(0, W + 1, 12):
        t = x / W * 2 * math.pi
        y = base_y - amp * (0.55 * math.sin(t + ph[0]) + 0.28 * math.sin(2.3 * t + ph[1])
                            + 0.12 * math.sin(4.1 * t + ph[2]) + 0.05 * math.sin(6.7 * t + ph[3]))
        pts.append((x, y))
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon(pts + [(W, H), (0, H)], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(blur))
    img.paste(Image.new("RGB", (W, H), tuple(color)), (0, 0), m.point(lambda v: v * alpha // 255))


def mist(img, y0=1300, alpha=60):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse((-400, y0, W + 400, y0 + 480), fill=alpha)
    m = m.filter(ImageFilter.GaussianBlur(95))
    img.paste(Image.new("RGB", (W, H), (245, 242, 232)), (0, 0), m)


def disc(img, x, y, r, color):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse([x - r * 1.9, y - r * 1.9, x + r * 1.9, y + r * 1.9], fill=64)
    m = m.filter(ImageFilter.GaussianBlur(60))
    img.paste(Image.new("RGB", (W, H), tuple(color)), (0, 0), m)
    m2 = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m2).ellipse([x - r, y - r, x + r, y + r], fill=215)
    m2 = m2.filter(ImageFilter.GaussianBlur(3))
    img.paste(Image.new("RGB", (W, H), tuple(color)), (0, 0), m2)


def rain(img, seed, n=170):
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(n):
        x = rnd.uniform(0, W)
        y = rnd.uniform(-100, H - 500)
        ln = rnd.uniform(80, 180)
        dx = -ln * 0.26
        bright = rnd.choice([False, False, True])
        col = ((240, 246, 252, rnd.randint(50, 78)) if bright
               else (228, 236, 246, rnd.randint(26, 46)))
        d.line([(x, y), (x + dx, y + ln)], fill=col, width=rnd.choice([1, 2, 2, 3]))


def splash(img, cx, cy, scale, seed):
    rnd = random.Random(seed)
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    for _ in range(9):
        r = rnd.uniform(26, 120) * scale
        ox = rnd.uniform(-180, 180) * scale
        oy = rnd.uniform(-90, 90) * scale
        dm.ellipse([cx + ox - r, cy + oy - r, cx + ox + r, cy + oy + r], fill=rnd.randint(70, 110))
    for _ in range(6):
        x = cx + rnd.uniform(-160, 160) * scale
        y0 = cy + rnd.uniform(0, 60) * scale
        ln = rnd.uniform(60, 260) * scale
        dm.line([(x, y0), (x, y0 + ln)], fill=rnd.randint(60, 95), width=max(2, int(5 * scale)))
    m = m.filter(ImageFilter.GaussianBlur(9))
    img.paste(Image.new("RGB", (W, H), (128, 34, 30)), (0, 0), m)


def vignette(img, strength=92):
    mask = Image.radial_gradient("L").resize((W, H))
    mask = mask.point(lambda v: v * strength // 255)
    dark = Image.new("RGB", (W, H), (30, 26, 22))
    return Image.composite(dark, img, mask)


def vtext(img, cx, y0, text, size, fill, stroke=0, jitter=6, seed=0, alpha=255):
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img, "RGBA")
    f = ImageFont.truetype(KAI, size)
    y = y0
    for ch in text:
        if ch != " ":
            d.text((cx + rnd.uniform(-jitter, jitter), y), ch, font=f,
                   fill=tuple(fill) + (alpha,), anchor="ma",
                   stroke_width=stroke, stroke_fill=tuple(fill) + (alpha,))
        y += int(size * 1.05)
    return y


def seal(img, cx, cy, ch, size=250):
    pad = int(size * 0.22)
    box = size + pad * 2
    layer = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([4, 4, box - 4, box - 4], radius=int(size * 0.12),
                        fill=(158, 44, 36, 235))
    f = ImageFont.truetype(KAI, size)
    d.text((box // 2, box // 2), ch, font=f, fill=(245, 240, 228, 255), anchor="mm")
    layer = layer.rotate(-2.5, resample=Image.BICUBIC)
    img.paste(layer, (int(cx - box / 2), int(cy - box / 2)), layer)


def corner_label(img, text):
    d = ImageDraw.Draw(img, "RGBA")
    f = ImageFont.truetype(YH_B, 62)
    d.text((130, 100), text, font=f, fill=(60, 54, 46, 145))


def base_layers(s, img):
    if s.get("disc"):
        dc = s["disc"]
        disc(img, dc["x"], dc["y"], dc["r"], dc["color"])
    ridge(img, 1560, 230, s["m_far"], 95, s["seed"] * 3 + 1, blur=5)
    ridge(img, 1810, 260, s["m_near"], 135, s["seed"] * 3 + 2, blur=4)
    ridge(img, 2020, 200, s["m_near"], 170, s["seed"] * 3 + 3, blur=3)
    mist(img)
    if s.get("rain"):
        rain(img, s["seed"])
        img = Image.blend(img, Image.new("RGB", (W, H), (148, 160, 174)), 0.10)
    if s.get("splash"):
        sp = s["splash"]
        splash(img, sp["x"], sp["y"], sp["scale"], s["seed"])
    return vignette(img)


def make_scene(s):
    img = paper(s["paper"], s["seed"])
    img = base_layers(s, img)
    corner_label(img, s["corner_label"])
    vtext(img, W - 680, 300, s["title"], 310, s["ink"], stroke=5, seed=s["seed"])
    cap = s["caption"]
    n = len(cap.replace(" ", ""))
    size = 140 if n <= 8 else 118
    lighter = [min(255, c + 20) for c in s["ink"]]
    vtext(img, W - 1130, 460 if n <= 8 else 430, cap, size, lighter,
          seed=s["seed"] + 1, alpha=225)
    seal(img, W - 680, 1780, s["seal_char"])
    return img


def make_title(s):
    img = paper(s["paper"], s["seed"])
    img = base_layers(s, img)
    # 圆相（enso）淡墨圆环衬在主标题后
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).arc([W // 2 - 560, 1030 - 560, W // 2 + 560, 1030 + 560],
                          start=210, end=110, fill=52, width=30)
    m = m.filter(ImageFilter.GaussianBlur(6))
    img.paste(Image.new("RGB", (W, H), (58, 52, 44)), (0, 0), m)
    d = ImageDraw.Draw(img, "RGBA")
    d.text((W // 2, 400), "西游记 · 第二十七回", font=ImageFont.truetype(YH_B, 116),
           fill=(60, 54, 46, 165), anchor="mm")
    d.text((W // 2, 1050), "三打白骨精", font=ImageFont.truetype(KAI, 560),
           fill=tuple(s["ink"]) + (255,), anchor="mm", stroke_width=9,
           stroke_fill=tuple(s["ink"]) + (255,))
    d.text((W // 2, 1560), "尸魔三戏唐三藏", font=ImageFont.truetype(KAI, 165),
           fill=(64, 58, 50, 235), anchor="mm")
    d.text((W // 2, 1780), "圣僧恨逐美猴王", font=ImageFont.truetype(KAI, 165),
           fill=(64, 58, 50, 235), anchor="mm")
    seal(img, W // 2 + 980, 1670, s["seal_char"], size=230)
    return img


def make_end(s):
    img = paper(s["paper"], s["seed"])
    img = base_layers(s, img)
    corner_label(img, s["corner_label"])
    d = ImageDraw.Draw(img, "RGBA")
    d.text((W // 2, 700), "欲知后事如何", font=ImageFont.truetype(KAI, 320),
           fill=tuple(s["ink"]) + (255,), anchor="mm", stroke_width=6,
           stroke_fill=tuple(s["ink"]) + (255,))
    d.text((W // 2, 1130), "且听下回分解", font=ImageFont.truetype(KAI, 320),
           fill=tuple(s["ink"]) + (255,), anchor="mm", stroke_width=6,
           stroke_fill=tuple(s["ink"]) + (255,))
    seal(img, W // 2, 1580, s["seal_char"], size=260)
    return img


def main():
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / "materials" / "scenes.json").read_text(encoding="utf-8"))
    for s in cfg["scenes"]:
        if s["kind"] == "title":
            img = make_title(s)
        elif s["kind"] == "end":
            img = make_end(s)
        else:
            img = make_scene(s)
        img.save(CARD_DIR / f"{s['id']}.png")
        img.resize((1280, 720), Image.LANCZOS).save(CARD_DIR / f"{s['id']}_preview.jpg", quality=88)
        print("card ok:", s["id"])


if __name__ == "__main__":
    main()
