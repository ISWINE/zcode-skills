# -*- coding: utf-8 -*-
"""clone_drama：序章克隆版台词引擎——克隆(旁白/安迪) + edge(网友ABC) → tts_clone/{id}.mp3+timing.json
产出目录与 tts_drama 隔离，供 audio_drama_clone.py 拼混。
"""
import asyncio
import json
import subprocess
import time
import urllib.request
import http.client
_JSON_HDR = {"Content-Type": "application/json"}
from pathlib import Path

import edge_tts  # 需 sdbgj venv 运行；克隆部分走 HTTP

ROOT = Path(__file__).resolve().parent
FF = str(ROOT / "tools" / "bin" / "ffmpeg.exe")
FP = str(ROOT / "tools" / "bin" / "ffprobe.exe")
API = "http://127.0.0.1:9880/tts"
C = Path("D:/tools/voicekit/refs/clean")
TTS = ROOT / "materials" / "tts_clone"
TTS.mkdir(parents=True, exist_ok=True)

CLONE_MAP = {
    "旁白": {"wav": str(C / "ref_nar2_(Vocals)_UVR-MDX-NET-Voc_FT.wav"),
             "pt": "什么情况？这正道联盟怎么突然就内讧了？我果然没猜错，王富贵，你果然是那个天选之子"},
    "安迪": {"wav": str(C / "ref_dialogue_raw_(Vocals)_UVR-MDX-NET-Voc_FT.wav"),
             "pt": "想到什么？你们全家都是狗。灵根无灵根，回去种田吧"},
}
EDGE_VOICES = {
    "网友A": "zh-CN-liaoning-XiaobeiNeural",
    "网友B": "zh-CN-shaanxi-XiaoniNeural",
    "网友C": "zh-CN-YunxiaNeural",
}
SPD = {"nar2": 0.92, "dlg": 0.95}   # 听书语速：旁白/安迪微降


def probe(p):
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def clone_line(text, ref, pt, out):
    if out.exists() and probe(out) >= len(text) / 9.0:
        return True
    for _ in range(4):
        ref_key = "nar2" if "nar2" in ref else "dlg"
        req = {"text": text, "text_lang": "zh", "ref_audio_path": ref,
               "prompt_text": pt, "prompt_lang": "zh", "text_split_method": "cut0",
               "media_type": "wav", "parallel_infer": False,
               "speed_factor": SPD.get(ref_key, 1.0)}
        data = json.dumps(req, ensure_ascii=False).encode()
        r = urllib.request.Request(API, data=data,
                                   headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=900) as resp:
            Path(out).write_bytes(resp.read())
        if probe(out) >= len(text) / 9.0:
            return True
    return False


async def edge_line(text, voice, rate, pitch, volume, out):
    for r_, p_ in ((rate, pitch), (rate, "+0Hz")):
        try:
            await edge_tts.Communicate(text, voice, rate=r_, pitch=p_,
                                       volume=volume).save(str(out))
            if out.stat().st_size > 400:
                await asyncio.sleep(0.3)
                return
        except Exception:
            await asyncio.sleep(1.5)


def make_silence(dur, out):
    subprocess.run([FF, "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                    "-t", f"{dur:.2f}", "-c:a", "libmp3lame", "-b:a", "48k",
                    str(out)], capture_output=True, check=True)


async def main():
    import sys as _s
    scenes_path = Path(_s.argv[1]) if len(_s.argv) > 1 else ROOT / "materials" / "scenes_xuzhang2.json"
    cfg = json.loads(scenes_path.read_text(encoding="utf-8"))
    for s in cfg["scenes"]:
        lines = s.get("lines", [])
        if not lines:
            continue
        parts, timing, sfx_events, t = [], [], [], 0.0
        sil_dir = TTS / "_sil"
        sil_dir.mkdir(exist_ok=True)
        for i, ln in enumerate(lines):
            gap = lines[i - 1].get("gap", 0.35) if i else 0
            if parts:
                sil = sil_dir / f"sil_{gap:.2f}.mp3"
                if not sil.exists():
                    make_silence(gap, sil)
                parts.append(sil)
                t += gap
            sp = ln["speaker"]
            f = TTS / f"{s['id']}_{i:02d}"
            ok_dur = None
            if sp in CLONE_MAP:
                w = f.with_suffix(".wav")
                if not clone_line(ln["text"], CLONE_MAP[sp]["wav"],
                                  CLONE_MAP[sp]["pt"], w):
                    fb = "zh-CN-YunyangNeural" if sp == "安迪" else "zh-CN-YunjianNeural"
                    await edge_line(ln["text"], fb, "+10%", "+8Hz", "+0%",
                                  f.with_suffix(".mp3"))
                    print(f"  !! {s['id']}#{i} clone 截断 -> edge 兜底 {fb}")
                # 统一转 mp3（拼接器吃 mp3）
                subprocess.run([FF, "-y", "-i", str(w), "-c:a", "libmp3lame",
                                "-b:a", "48k", str(f.with_suffix('.mp3'))],
                               capture_output=True, check=True)
            else:
                m = f.with_suffix(".mp3")
                await edge_line(ln["text"], EDGE_VOICES[sp],
                                ln.get("rate", "+0%"), ln.get("pitch", "+0Hz"),
                                ln.get("volume", "+0%"), m)
                f = m
            f = f.with_suffix(".mp3")
            d = probe(f)
            cue = ln["text"] if ln.get("as") == "narr" else f"{sp}：{ln['text']}"
            timing.append({"start": round(t, 3), "end": round(t + d, 3),
                           "speaker": sp, "as": ln.get("as", "dialog"),
                           "text": ln["text"], "cue": cue})
            if ln.get("sfx"):
                t_ev = t + d if ln.get("sfx_at") == "end" else t
                sfx_events.append({"t": round(t_ev, 3), "type": ln["sfx"]})
            parts.append(f)
            t += d
        # concat
        final = TTS / f"{s['id']}.mp3"
        lst = TTS / f"{s['id']}_list.txt"
        lst.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in parts),
                       encoding="utf-8")
        subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c:a", "libmp3lame", "-b:a", "48k", str(final)],
                       capture_output=True, check=True)
        (TTS / f"{s['id']}.timing.json").write_text(
            json.dumps({"duration": round(probe(final), 3), "lines": timing,
                        "sfx": sfx_events}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"{s['id']}: {len(lines)} lines, {probe(final):.2f}s")

asyncio.run(main())
