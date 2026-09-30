# -*- coding: utf-8 -*-
"""用 edge-tts 生成每场景旁白 mp3（.venv Python 3.12 运行）"""
import asyncio
import json
import sys
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent
VOICE = "zh-CN-YunjianNeural"
RATE = "-10%"


async def main():
    cfg = json.loads((ROOT / "materials" / "scenes.json").read_text(encoding="utf-8"))
    out_dir = ROOT / "materials" / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    for s in cfg["scenes"]:
        text = s.get("narration")
        if not text:
            continue
        out = out_dir / f"{s['id']}.mp3"
        if out.exists() and "--force" not in sys.argv:
            print("skip:", out.name)
            continue
        com = edge_tts.Communicate(text, VOICE, rate=RATE)
        await com.save(str(out))
        print("tts ok:", out.name, len(text), "chars")


asyncio.run(main())
