# -*- coding: utf-8 -*-
"""voicekit —— 角色声音卡（Voice Card）工具
用法:
  python voicecard_gen.py new 孙悟空          # 生成骨架卡（待人工/LLM 填写分析与社区参考）
  python voicecard_gen.py validate card.json  # 校验 schema
  python voicecard_gen.py compile card.json   # 编译为 tts_drama 可用的 voice_map + 情绪预设
  python voicecard_gen.py match card.json     # 只看音色匹配评分

角色卡方法论：先人物分析（性格轴/年龄/背景/说话习惯）→ 音色画像 →
对照社区配音理解（community_refs）→ 落到双引擎参数（edge=即用，neural=参考音策略）。
"""
import json
import sys
from pathlib import Path

# 本机 edge-tts 实测可用 zh-CN 音色及其声学特征画像（0-1 标度）
EDGE_VOICES = {
    "zh-CN-YunjianNeural": {"gender": "男", "age": "中青年", "pitch": 0.35, "energy": 0.95,
                            "timbre": "浑厚圆润", "tags": ["武将", "豪迈", "爆发力", "纪录片解说"]},
    "zh-CN-YunxiNeural":   {"gender": "男", "age": "青年",   "pitch": 0.60, "energy": 0.75,
                            "timbre": "清亮活泼", "tags": ["少年", "阳光", "机灵", "邻家"]},
    "zh-CN-YunyangNeural": {"gender": "男", "age": "中年",   "pitch": 0.45, "energy": 0.55,
                            "timbre": "端正播音", "tags": ["庄重", "新闻", "权威", "平稳"]},
    "zh-CN-YunxiaNeural":  {"gender": "男", "age": "少年",   "pitch": 0.75, "energy": 0.80,
                            "timbre": "娃娃音", "tags": ["孩童", "软萌", "喜剧"]},
    "zh-CN-XiaoxiaoNeural":{"gender": "女", "age": "青年",   "pitch": 0.60, "energy": 0.65,
                            "timbre": "温暖亲和", "tags": ["温柔", "通用女声", "戏剧可塑"]},
    "zh-CN-XiaoyiNeural":  {"gender": "女", "age": "青年",   "pitch": 0.65, "energy": 0.75,
                            "timbre": "轻快俏皮", "tags": ["活泼", "旁白", "少女"]},
    "zh-CN-liaoning-XiaobeiNeural": {"gender": "女", "age": "中年", "pitch": 0.55, "energy": 0.70,
                            "timbre": "东北方言", "tags": ["方言", "喜剧", "大碴子味"]},
    "zh-CN-shaanxi-XiaoniNeural":  {"gender": "女", "age": "中年", "pitch": 0.50, "energy": 0.60,
                            "timbre": "陕西方言", "tags": ["方言", "朴实"]},
}

REQUIRED = ["name", "franchise", "profile", "voice_design"]
PROFILE_KEYS = ["age_apparent", "gender", "archetype", "personality_axes",
                "background", "signature_lines", "speech_traits"]
AXES = ["energy", "aggression", "playfulness", "warmth", "composure"]
EMOTIONS_STD = ["平静", "暴怒", "焦急", "得意", "悲伤", "恐惧", "谄媚", "威严"]

SKELETON = {
    "name": "", "franchise": "",
    "profile": {
        "age_apparent": "", "gender": "", "archetype": "",
        "personality_axes": {k: 0.5 for k in AXES},
        "background": "", "motivation": "",
        "relationships": "",
        "signature_lines": [],
        "audition_lines": [],
        "speech_traits": {"pace": "", "pitch": "", "timbre": "", "accent": ""},
    },
    "community_refs": [
        {"source": "（出处标题）", "insight": "（社区/配音圈对这个角色声音的理解）", "url": ""}
    ],
    "voice_design": {
        "target": {"gender": "", "age": "", "pitch": 0.5, "energy": 0.5,
                   "timbre_keywords": []},
        "edge_engine": {"voice": "", "adjust": {"rate": "+0%", "pitch": "+0Hz"}, "why": ""},
        "neural_engine": {"reference_strategy": "", "emotion_presets": {},
                          "model_pack": {"ckpt": "", "pth": "", "wav": "", "txt": ""}},
    },
    "emotion_presets": {e: {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%"}
                        for e in EMOTIONS_STD},
}
# v2 说明：motivation/relationships/audition_lines（试音台词，招募线传统）、
# model_pack（GPT-SoVITS 音色包四件套 ckpt/pth/wav/txt，AI 音色包传统）、
# 全书调性（voice_bible）建议每部作品单建 _voice_bible.json


def score_voices(card):
    t = card["voice_design"]["target"]
    scores = []
    for vid, f in EDGE_VOICES.items():
        if f["gender"] != t.get("gender", f["gender"]):
            scores.append((vid, 0.0, "性别不符"))
            continue
        s = 1.0
        s -= abs(f["pitch"] - t.get("pitch", 0.5)) * 1.2
        s -= abs(f["energy"] - t.get("energy", 0.5)) * 0.8
        kw = set(t.get("timbre_keywords", []))
        tag_hit = len([k for k in kw if any(k in tag for tag in f["tags"])])
        s += tag_hit * 0.15
        scores.append((vid, round(max(0.0, s), 3), f"{f['age']}/{f['timbre']}"))
    return sorted(scores, key=lambda x: -x[1])


def validate(path):
    card = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = []
    for k in REQUIRED:
        if k not in card:
            problems.append(f"缺少顶层字段 {k}")
    if "profile" in card:
        for k in PROFILE_KEYS:
            if k not in card["profile"]:
                problems.append(f"profile.{k} 缺失")
        for a in AXES:
            v = card["profile"].get("personality_axes", {}).get(a)
            if not isinstance(v, (int, float)) or not 0 <= v <= 1:
                problems.append(f"personality_axes.{a} 应为 0-1 数值")
    if "community_refs" not in card or not card["community_refs"]:
        problems.append("community_refs 为空——角色卡要求有社区配音理解的对照（可注明搜索无果）")
    if "emotion_presets" not in card:
        problems.append("emotion_presets 缺失")
    print(f"[{card.get('name','?')}] {'PASS' if not problems else 'FAIL'}")
    for p in problems:
        print("  -", p)
    return not problems


def compile_(path):
    card = json.loads(Path(path).read_text(encoding="utf-8"))
    ve = card["voice_design"]["edge_engine"]
    out = {
        "name": card["name"],
        "voice_map_entry": {card["name"]: {
            "voice": ve["voice"],
            "desc": f"{card['profile']['archetype']}｜{ve.get('why','')}",
            "base_adjust": ve.get("adjust", {}),
        }},
        "emotion_presets": card.get("emotion_presets", {}),
        "neural": card["voice_design"].get("neural_engine", {}),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "new":
        name = sys.argv[2]
        card = json.loads(json.dumps(SKELETON, ensure_ascii=False))
        card["name"] = name
        Path(f"{name}.card.json").write_text(
            json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"骨架已生成: {name}.card.json（填 profile/community_refs/voice_design 后再 compile）")
    elif cmd == "validate":
        sys.exit(0 if validate(sys.argv[2]) else 1)
    elif cmd == "compile":
        compile_(sys.argv[2])
    elif cmd == "match":
        card = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        for vid, s, d in score_voices(card):
            print(f"{s:5.2f}  {vid:34} {d}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
