# -*- coding: utf-8 -*-
"""极简混音器：直接 concat 场景 mp3 + 中间插静音 + sfx 后混（无复杂滤镜链）
python simple_mix.py → out/radio_tingshu.mp3
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FF = str(ROOT / "tools" / "bin" / "ffmpeg.exe")
FP = str(ROOT / "tools" / "bin" / "ffprobe.exe")
TTS = ROOT / "materials" / "tts_clone"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

SCENES = ["P1", "P2", "P3", "P4", "P5"]
GAP = 0.6  # 秒

def probe(p):
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip())

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit(f"FAILED: {cmd[:3]}")

# ---- 第 1 步：场景音频 + 静音 → 一条完整人声轨 ----
voice_in = []
parts = []
t = 0.0
for sid in SCENES:
    mp3 = TTS / f"{sid}.mp3"
    d = probe(mp3)
    voice_in += ["-i", str(mp3)]
    parts.append((sid, t, d))
    t += d + GAP
total = t - GAP + 1.0

# concat 场景（直接顺序排，中间用 apad/silence）
fc_v = []
for i in range(len(SCENES)):
    fc_v.append(f"[{i}:a]aresample=44100,aformat=sample_fmts=s16:channel_layouts=stereo[v{i}]")
vc = "".join(f"[v{i}]" for i in range(len(SCENES)))
fc_v.append(f"{vc}concat=n={len(SCENES)}:v=0:a=1,apad=pad_dur={GAP}[voice_out]")
# 注：concat 自动连续，句间 gap 已在场景内部由 tts_clone 处理

voice_wav = OUT / "_voice.wav"
run([FF, "-y", *voice_in, "-filter_complex", ";".join(fc_v),
     "-map", "[voice_out]", "-c:a", "pcm_s16le", str(voice_wav)])

# ---- 第 2 步：sfx 后混（简单 adelay + amix） ----
sfx_events = []
for sid, st, dur in parts:
    tj = TTS / f"{sid}.timing.json"
    if tj.exists():
        data = json.loads(tj.read_text(encoding="utf-8"))
        for ev in data.get("sfx", []):
            sfx_events.append((st + ev["t"], ev["type"]))

SFX = {
    "boom": (str(OUT / "sfx_boom.wav"), 0.9),
    "crack": (str(OUT / "sfx_crack.wav"), 0.9),
    "wobble": (str(OUT / "sfx_wobble.wav"), 0.6),
    "spark": (str(OUT / "sfx_spark.wav"), 0.5),
    "fire": (str(OUT / "sfx_fire.wav"), 0.4),
    "siren": (str(OUT / "sfx_siren.wav"), 0.7),
    "fan": (str(OUT / "sfx_fan.wav"), 0.3),  # 用原始 10s 版，atrim 5s
    "boing": (str(OUT / "sfx_boing.wav"), 0.8),
}
MAXLEN = {"fan": 5.0, "fire": 8.0, "siren": 3.5}

inputs = ["-i", str(voice_wav)]
chains = []
labels = ["[0:a]"]
for j, (at, typ) in enumerate(sorted(sfx_events)):
    path, vol = SFX.get(typ, (str(OUT / "sfx_boom.wav"), 0.5))
    inputs += ["-i", path]
    trim = f"atrim=duration={MAXLEN[typ]}," if typ in MAXLEN else ""
    ms = int(max(0, at - 0.05) * 1000)
    chains.append(f"[{1+j}:a]{trim}volume={vol},"
                  f"aformat=channel_layouts=stereo,adelay={ms}|{ms}[s{j}]")
    labels.append(f"[s{j}]")

n = len(labels)
fc = chains + [f"{''.join(labels)}amix=inputs={n}:duration=longest:normalize=0[mix]",
               f"[mix]volume=2.0dB,alimiter=limit=0.88:level=false[out]"]

final = OUT / "radio_tingshu.mp3"
run([FF, "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[out]",
     "-t", f"{total:.1f}", "-c:a", "libmp3lame", "-b:a", "192k", str(final)])

# 验证人声覆盖
vd = probe(final)
r = subprocess.run([FF, "-hide_banner", "-i", str(final), "-af", "volumedetect",
                    "-f", "null", "-"], capture_output=True, text=True)
vol = dict(re.findall(r"(mean_volume|max_volume):\s*(-?[\d.]+ dB)", r.stderr))
# 抽查 3 个时间点
spots = []
for check_t in [5, 35, 60, 100, 150]:
    rr = subprocess.run([FF, "-hide_banner", "-ss", str(check_t), "-t", "2",
                         "-i", str(final), "-af", "volumedetect", "-f", "null", "-"],
                        capture_output=True, text=True)
    m = re.search(r"mean_volume: (\S+ dB)", rr.stderr)
    spots.append(f"t={check_t}s:{m.group(1) if m else 'DEAD'}")

print(f"OK {vd:.1f}s mean={vol.get('mean_volume')} max={vol.get('max_volume')}")
print("人声抽查:", " | ".join(spots))
