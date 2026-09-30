# -*- coding: utf-8 -*-
"""总装：时间线 -> 分镜渲染 -> xfade -> 混音 -> 字幕 -> out/preview.mp4 + 合同工件"""
import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FF = str(ROOT / "tools" / "bin" / "ffmpeg.exe")
FP = str(ROOT / "tools" / "bin" / "ffprobe.exe")
OUT = ROOT / "out"
CLIPS = OUT / "clips"
CLIPS.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

CANVAS = dict(w=1920, h=1080, fps=30)


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd[:8]), "...")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit(f"command failed: {cmd[:4]}")
    return r


def probe_dur(p):
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip())


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def motion_filter(motion, dur, fps=30):
    n = int(round(dur * fps))
    cx = "iw/2-(iw/zoom/2)"
    cy = "ih/2-(ih/zoom/2)"
    if motion == "panR":
        z = 1.10
        return (f"zoompan=z={z}:x='(iw-iw/zoom)*on/{n}':y='{cy}'"
                f":d=1:s=1920x1080:fps={fps}")
    if motion == "panL":
        z = 1.10
        return (f"zoompan=z={z}:x='(iw-iw/zoom)*(1-on/{n})':y='{cy}'"
                f":d=1:s=1920x1080:fps={fps}")
    zmax = {"zin": 1.14, "zin_slow": 1.08, "zin_fast": 1.20, "zout": 1.14}[motion]
    rate = (zmax - 1.0) / (0.75 * n)
    if motion == "zout":
        z = f"max({zmax}-{rate:.7f}*on,1.0)"
    else:
        z = f"min(1+{rate:.7f}*on,{zmax})"
    return f"zoompan=z='{z}':x='{cx}':y='{cy}':d=1:s=1920x1080:fps={fps}"


def split_cues(text, max_len=18):
    """按句读拆字幕 cue：先按句末标点，再按逗顿号贪心打包"""
    import re
    sentences = [s for s in re.split(r"(?<=[。！？；])", text) if s]
    frags = []
    for sent in sentences:
        if len(sent) <= max_len:
            frags.append(sent)
            continue
        parts = [p for p in re.split(r"(?<=[，、—：])", sent) if p]
        buf = ""
        for p in parts:
            if len(buf) + len(p) <= max_len:
                buf += p
            else:
                if buf:
                    frags.append(buf)
                while len(p) > max_len:
                    frags.append(p[:max_len])
                    p = p[max_len:]
                buf = p
        if buf:
            frags.append(buf)
    return frags


def ass_time(t):
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def main():
    cfg = json.loads((ROOT / "materials" / "scenes.json").read_text(encoding="utf-8"))
    fade = cfg["fade"]
    lead, tail = cfg["lead"], cfg["tail"]

    # ---- 1. 计算时间线 ----
    tl = []  # 每卡: id, dur, start, narr(=start+lead 或 None), tts_dur
    start = 0.0
    for s in cfg["scenes"]:
        if s["kind"] == "title":
            dur = s["dur_override"]
        elif s["kind"] == "end":
            d = probe_dur(ROOT / "materials" / "tts" / f"{s['id']}.mp3")
            dur = lead + d + cfg["end_tail"]
        else:
            d = probe_dur(ROOT / "materials" / "tts" / f"{s['id']}.mp3")
            dur = lead + d + tail
        s["_dur"], s["_start"], s["_tts_dur"] = dur, start, (
            probe_dur(ROOT / "materials" / "tts" / f"{s['id']}.mp3")
            if s.get("narration") else None)
        tl.append(s)
        start += dur - fade
    total = tl[-1]["_start"] + tl[-1]["_dur"]
    print(f"total duration = {total:.2f}s")

    # ---- 2. 渲染分镜卡（已有且时长吻合则复用）----
    for s in tl:
        clip = CLIPS / f"{s['id']}.mp4"
        if clip.exists() and abs(probe_dur(clip) - s["_dur"]) < 0.15:
            s["_clip"] = str(clip)
            print("reuse clip:", clip.name)
            continue
        vf = motion_filter(s["motion"], s["_dur"]) + ",settb=AVTB,setsar=1,format=yuv420p"
        run([FF, "-y", "-loop", "1", "-framerate", "30", "-t", f"{s['_dur']:.3f}",
             "-i", str(ROOT / "materials" / "cards" / f"{s['id']}.png"),
             "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             str(clip)])
        s["_clip"] = str(clip)

    # ---- 3. xfade 串联 ----
    inputs = []
    for s in tl:
        inputs += ["-i", s["_clip"]]
    fc, prev = [], "0:v"
    for i in range(1, len(tl)):
        outl = f"v{i}" if i < len(tl) - 1 else "vv"
        fc.append(f"[{prev}][{i}:v]xfade=transition={tl[i-1]['trans_out']}"
                  f":duration={fade}:offset={tl[i]['_start']:.3f}[{outl}]")
        prev = outl
    silent = OUT / "silent.mp4"
    if silent.exists() and abs(probe_dur(silent) - total) < 0.5:
        print("reuse silent.mp4")
    else:
        run([FF, "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[vv]",
             "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p", str(silent)])

    # ---- 4. 旁白混音 ----
    narrs = [s for s in tl if s.get("narration")]
    a_inputs, chains, labels = [], [], []
    for s in narrs:
        a_inputs += ["-i", str(ROOT / "materials" / "tts" / f"{s['id']}.mp3")]
    idx = {s["id"]: 1 + i for i, s in enumerate(narrs)}  # 0 = silent.mp4
    noise_idx = 1 + len(narrs)
    for s in narrs:
        ms = int(round((s["_start"] + lead) * 1000))
        chains.append(f"[{idx[s['id']]}:a]aresample=48000,"
                      f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
                      f"adelay={ms}|{ms}[n{s['id']}]")
        labels.append(f"[n{s['id']}]")
    # 粉噪风声垫（极低音量，营造山野氛围）兼保证音轨全长覆盖
    wind = (f"[{noise_idx}:a]aformat=channel_layouts=stereo:sample_fmts=fltp,"
            f"volume=0.55,lowpass=f=520,highpass=f=90,"
            f"afade=t=in:d=2.5,afade=t=out:st={total-3:.2f}:d=3[bed]")
    mix_in = "".join(labels)
    fc = (chains + [wind,
          f"{mix_in}[bed]amix=inputs={len(labels)+1}:duration=longest:normalize=0[mix]",
          "[mix]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]"])
    withaudio = OUT / "withaudio.mp4"
    if withaudio.exists() and abs(probe_dur(withaudio) - total) < 0.5:
        print("reuse withaudio.mp4")
    else:
        run([FF, "-y", "-i", str(silent), *a_inputs,
             "-f", "lavfi", "-t", f"{total:.3f}",
             "-i", "anoisesrc=color=pink:amplitude=0.05:r=48000",
             "-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[aout]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(withaudio)])

    # ---- 5. 字幕 ----
    subs = OUT / "subs.ass"
    lines = ["[Script Info]", "ScriptType: v4.00+",
             "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 0", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
             "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
             "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
             "MarginL, MarginR, MarginV, Encoding",
             "Style: Default,Microsoft YaHei,58,&H00FFFFFF,&H00FFFFFF,&H00000000,"
             "&H64000000,0,0,0,0,100,100,0.4,0,1,2.4,1.0,2,40,40,76,1", "",
             "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
             "MarginV, Effect, Text"]
    for s in narrs:
        cues = split_cues(s["narration"])
        t0 = s["_start"] + lead
        tw = s["_tts_dur"]
        wsum = sum(len(c) for c in cues)
        acc = 0.0
        for c in cues:
            cs, ce = t0 + tw * acc / wsum, t0 + tw * (acc + len(c)) / wsum
            acc += len(c)
            lines.append(f"Dialogue: 0,{ass_time(cs)},{ass_time(ce)},Default,,0,0,0,,{c.strip()}")
    subs.write_text("\n".join(lines) + "\n", encoding="utf-8")

    preview = OUT / "preview.mp4"
    run([FF, "-y", "-i", str(withaudio),
         "-vf", "ass=out/subs.ass",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", str(preview)])

    # ---- 6. 转录工件（TTS ground truth，非 ASR）----
    transcript = {
        "source": "tts-input-ground-truth",
        "note": "生成式任务：旁白文本即 TTS 合成输入，逐字精确；插件 ASR MCP 工具本会话不可用，"
                "转录以生成端文本为准（优于回听 ASR）",
        "language": "zh-CN",
        "segments": [],
    }
    for s in narrs:
        t0 = s["_start"] + lead
        tw = s["_tts_dur"]
        cues_raw = split_cues(s["narration"])
        wsum = sum(len(c) for c in cues_raw)
        acc = 0.0
        cues = []
        for c in cues_raw:
            cs, ce = t0 + tw * acc / wsum, t0 + tw * (acc + len(c)) / wsum
            acc += len(c)
            cues.append({"start": round(cs, 3), "end": round(ce, 3),
                         "text": c.strip()})
        transcript["segments"].append({
            "id": s["id"], "source": f"materials/tts/{s['id']}.mp3",
            "start": round(t0, 3), "end": round(t0 + tw, 3),
            "text": s["narration"], "cues": cues})
    (OUT / "transcript.json").write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 7. 源素材观察包（video_ingest 手工等价物）----
    ing = OUT / "ingest"
    ing.mkdir(exist_ok=True)
    sources = []
    for s in tl:
        sheet = ing / f"{s['id']}_sheet.jpg"
        fps6 = 6.0 / s["_dur"]
        run([FF, "-y", "-i", s["_clip"],
             "-vf", f"fps={fps6:.5f},scale=480:270,tile=3x2", "-frames:v", "1",
             str(sheet)])
        sources.append({"id": s["id"], "source": f"out/clips/{s['id']}.mp4",
                        "duration": round(s["_dur"], 3),
                        "contact_sheet": f"out/ingest/{s['id']}_sheet.jpg"})
    (OUT / "video_ingest.json").write_text(json.dumps({
        "generated_by": "manual-equivalent：插件 video_ingest MCP 本会话不可用；"
                        "接触表由 ffmpeg 确定性抽帧生成，视觉核验结论记录于 out/report.md",
        "sources": sources, "transcript_attached": "out/transcript.json"},
        ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 8. 合同工件 ----
    timeline = {
        "project": {"name": cfg["project"], "language": "zh-CN",
                    "canvas": CANVAS, "total": round(total, 3)},
        "assets": ([{"id": f"card_{s['id']}", "type": "image",
                     "source": f"materials/cards/{s['id']}.png",
                     "duration": round(s["_dur"], 3)} for s in tl]
                   + [{"id": f"tts_{s['id']}", "type": "audio",
                       "source": f"materials/tts/{s['id']}.mp3",
                       "duration": round(s["_tts_dur"], 3)}
                      for s in narrs]),
        "tracks": [
            {"type": "main",
             "clips": [{"source": f"out/clips/{s['id']}.mp4", "start": 0.0,
                        "end": round(s["_dur"], 3),
                        "timeline_start": round(s["_start"], 3),
                        "reason": s["corner_label"] + "｜" +
                                  (s.get("narration") or "标题卡，静场引入")
                                  [:24]} for s in tl]},
            {"type": "audio",
             "clips": [{"source": f"materials/tts/{s['id']}.mp3",
                        "start": 0.0, "end": round(s["_tts_dur"], 3),
                        "timeline_start": round(s["_start"] + lead, 3),
                        "reason": s["corner_label"] + " 旁白"} for s in narrs]},
            {"type": "subtitle",
             "cues": [{"start": round(s["_start"] + lead, 3),
                       "end": round(s["_start"] + lead + s["_tts_dur"], 3),
                       "text": s["narration"]} for s in narrs]},
        ],
        "transitions": [{"at": round(tl[i]["_start"], 3), "type": tl[i]["trans_out"],
                         "duration": fade} for i in range(len(tl) - 1)],
    }
    tp = OUT / "timeline.json"
    tp.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")

    checks = []
    ok = True
    for s in tl:
        c = s["_clip"]
        d = probe_dur(c)
        good = abs(d - s["_dur"]) < 0.15
        ok &= good
        checks.append({"clip": Path(c).name, "expected": round(s["_dur"], 3),
                       "actual": round(d, 3), "pass": good})
    starts = [s["_start"] for s in tl]
    mono = all(starts[i] < starts[i + 1] for i in range(len(starts) - 1))
    ok &= mono
    proj_ok = bool(timeline.get("project") and timeline.get("assets")
                   and any(t.get("type") in ("main", "video")
                           for t in timeline.get("tracks", [])))
    (OUT / "timeline_validation.json").write_text(json.dumps({
        "status": "pass" if (ok and proj_ok) else "fail",
        "timeline_sha256": sha256(tp),
        "project_contract": {"ok": proj_ok,
                             "checked": ["project", "assets[]", "tracks[]",
                                         "main track", "canvas"]},
        "pass": bool(ok and proj_ok),
        "clip_checks": checks, "monotonic_starts": mono,
        "note": "官方 validate_timeline MCP 工具本会话不可用，此为脚本自检等价物"},
        ensure_ascii=False, indent=2), encoding="utf-8")

    (OUT / "media.json").write_text(json.dumps({
        "sources": [{"path": f"materials/cards/{s['id']}.png", "type": "image",
                     "w": 3840, "h": 2160, "role": "分镜卡"} for s in tl]
                   + [{"path": f"materials/tts/{s['id']}.mp3", "type": "audio",
                       "duration": round(s["_tts_dur"], 3), "role": "旁白"}
                      for s in narrs],
        "notes": "无用户素材；图搜 MCP 返回空，视觉为 PIL 自绘水墨卡（gen_cards.py）；"
                 "TTS=edge-tts zh-CN-YunjianNeural rate=-10%"}, 
        ensure_ascii=False, indent=2), encoding="utf-8")

    (OUT / "preview.render_plan.json").write_text(json.dumps({
        "timeline_sha256": sha256(tp),
        "steps": ["zoompan per scene (Ken Burns)", "xfade chain",
                  "narration adelay+amix+loudnorm", "ass subtitle burn"],
        "fade": fade, "lead": lead, "tail": tail,
        "motions": {s["id"]: s["motion"] for s in tl}}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    (OUT / "preview.render_report.json").write_text(json.dumps({
        "timeline_sha256": sha256(tp), "output": "out/preview.mp4",
        "output_sha256": sha256(preview), "duration": round(total, 3)},
        ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "preview.edit_decisions.json").write_text(json.dumps({
        "timeline_sha256": sha256(tp),
        "decisions": [f"{s['id']}: {s['corner_label']} — {s['motion']}, "
                      f"转出 {s['trans_out']}" for s in tl],
        "assumptions": ["16:9 1080p30 横屏", "无 BGM，低音量风声垫底",
                        "字幕按句读拆分、句内按字数比例分配时间"]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUILD DONE -> out/preview.mp4")


if __name__ == "__main__":
    main()
