# -*- coding: utf-8 -*-
"""QC：技术检查（黑帧/静音/响度/时长/流参数）+ 抽帧供目检"""
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FF = str(ROOT / "tools" / "bin" / "ffmpeg.exe")
FP = str(ROOT / "tools" / "bin" / "ffprobe.exe")
OUT = ROOT / "out"
FR = OUT / "qc_frames"
FR.mkdir(parents=True, exist_ok=True)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def main():
    rep = {}
    # 流参数与时长
    pr = run([FP, "-v", "error", "-print_format", "json", "-show_format",
              "-show_streams", str(OUT / "preview.mp4")])
    fmt = json.loads(pr.stdout)
    v = next(s for s in fmt["streams"] if s["codec_type"] == "video")
    a = next(s for s in fmt["streams"] if s["codec_type"] == "audio")
    tl = json.loads((OUT / "timeline.json").read_text(encoding="utf-8"))
    total = tl["project"]["total"]
    dur = float(fmt["format"]["duration"])
    rep["streams"] = {
        "video": {k: v.get(k) for k in ("codec_name", "width", "height",
                                        "r_frame_rate", "pix_fmt")},
        "audio": {k: a.get(k) for k in ("codec_name", "sample_rate",
                                        "channels", "bit_rate")},
    }
    rep["duration"] = {"expected": total, "actual": round(dur, 3),
                       "pass": abs(dur - total) < 0.5}
    checks = [rep["duration"]["pass"],
              v["width"] == 1920 and v["height"] == 1080,
              v["r_frame_rate"] == "30/1",
              a["sample_rate"] == "48000"]

    # 黑帧（fadeblack 转场中点为白名单）
    bl = run([FF, "-hide_banner", "-i", str(OUT / "preview.mp4"),
              "-vf", "blackdetect=d=0.25:pix_th=0.10", "-an", "-f", "null", "-"])
    blacks = []
    for m in re.finditer(r"black_start:(\S+) black_end:(\S+) black_duration:(\S+)",
                         bl.stderr):
        blacks.append(tuple(float(x) for x in m.groups()))
    wl = [[t["at"] + 0.15, t["at"] + 0.65] for t in tl["transitions"]
          if t["type"] == "fadeblack"]
    bad_blacks = [b for b in blacks
                  if not any(w[0] <= b[0] and b[1] <= w[1] for w in wl)]
    rep["black_frames"] = {"found": blacks, "whitelist_windows": wl,
                           "unexpected": bad_blacks, "pass": not bad_blacks}
    checks.append(not bad_blacks)

    # 静音段（>2.8s 视为异常；风声垫应保证底噪存在）
    si = run([FF, "-hide_banner", "-i", str(OUT / "preview.mp4"),
              "-af", "silencedetect=noise=-42dB:d=2.8", "-f", "null", "-"])
    sils = [(float(x), float(y)) for x, y in
            re.findall(r"silence_start: (\S+).*?silence_end: (\S+)", si.stderr)]
    rep["silence"] = {"gaps": sils, "pass": not sils,
                      "note": "旁白间隔约 1.9s 属预期；风声垫应避免死寂"}
    checks.append(not sils)

    # 响度
    vo = run([FF, "-hide_banner", "-i", str(OUT / "preview.mp4"),
              "-af", "volumedetect", "-f", "null", "-"])
    vol = dict(re.findall(r"(mean_volume|max_volume):\s*(-?[\d.]+ dB)", vo.stderr))
    rep["volume"] = vol
    checks.append(float(vol["max_volume"].split()[0]) <= -1.0)

    # 抽帧：每场景中段 + 每转场中点 + 首/尾
    times = [0.6, total - 1.2]
    for c in tl["tracks"][0]["clips"]:
        times.append(min(c["timeline_start"] + 2.6, total - 0.4))
    for t in tl["transitions"]:
        times.append(t["at"] + 0.4)
    for t in sorted(set(round(x, 2) for x in times if 0 < x < total - 0.2)):
        run([FF, "-y", "-ss", str(t), "-i", str(OUT / "preview.mp4"),
             "-frames:v", "1", "-vf", "scale=960:540",
             str(FR / f"f_{t:07.2f}.jpg")])
    rep["frames_sampled"] = sorted(p.name for p in FR.glob("*.jpg"))
    rep["pass"] = all(checks)
    rep["status"] = "pass" if rep["pass"] else "fail"
    rep["video_sha256"] = hashlib.sha256(
        (OUT / "preview.mp4").read_bytes()).hexdigest()
    rep["timeline_sha256"] = hashlib.sha256(
        (OUT / "timeline.json").read_bytes()).hexdigest()
    (OUT / "preview_qc_report.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("pass", "duration", "volume")},
                     ensure_ascii=False))
    print("blacks:", blacks, "| unexpected:", bad_blacks)
    print("silence gaps:", sils)


if __name__ == "__main__":
    main()
