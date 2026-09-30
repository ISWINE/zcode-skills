# -*- coding: utf-8 -*-
"""novelkit —— 小说系统辨识器（stdlib 零依赖）
txt 小说 → analysis.json（章回/对白/说话人归属/人物统计/场景节拍）
         + 角色卡骨架（对接 voicekit schema）
         + 分镜节拍草稿（对接 scenes.json 改编流程）

用法:
  python novel_analyzer.py 小说.txt --out 输出目录 \
      [--names 孙悟空=行者,大圣,猴王,悟空 唐僧=三藏,唐三藏,长老]
不带 --names 时自动从「言说动词前缀」挖掘候选人物（适合未知文本摸底）。
"""
import argparse
import collections
import json
import re
from pathlib import Path

QUOTE_RE = re.compile(r'[「『“"]([^」』”"]{1,140})[」』”"]')
SAY_VERB = (r"(?:说道?|喊道?|叫道?|骂道|笑道?|哭道|答道|问道?|喝道?|言道|回道|叹道|"
            r"冷笑道?|应道|沉声道?|高声道?|低声道?|吩咐道?|吩咐|答话|叫唤|嚷道|商议|"
            r"喜道|怒道|惊道|呼道|嘲讽|回应|嘀咕|安慰|自语|道)")
ONOMATOPOEIA = {"咔嚓", "呜呜", "轰", "哗啦", "砰", "咣当", "嗡嗡", "滋滋", "滴"}
PRE_RE = re.compile(r"([\u4e00-\u9fa5]{2,6}?)" + SAY_VERB)
POST_RE = re.compile(SAY_VERB + r"[，。！？\s]{0,2}([\u4e00-\u9fa5]{2,6})")
LEAD_JUNK = ("只见", "却说", "便", "又", "连忙", "急", "那", "正", "遂", "即", "听得",
             "原来", "忽", "却", "半", "一", "他", "她", "你", "我", "乃", "今", "才",
             "刚", "先", "后", "此", "彼", "众", "那怪", "那魔", "妖精", "长老", "师父",
             "然后", "顿时", "突然", "接着", "不由", "忍不住", "直接", "开口", "只是",
             "同时", "随即", "立刻", "马上", "当即", "随后", "继续", "有些", "似乎",
             "已经", "再次", "一边", "赶忙", "急忙", "淡淡", "幽幽", "忽然", "猛然",
             "果然", "竟然", "居然", "显然", "依然", "仍然", "蓦然", "旋即", "不禁",
             "不由得", "喃喃", "自语", "低声", "高声", "大声", "小声", "冷声", "沉声")
# 自动挖掘时的角色名黑名单（虚词/拟声/残留），v2 由《巫界》实测失败模式驱动
AUTO_STOP = {"然后", "一声", "比如", "自语", "了起来", "起来", "顿时", "突然", "接着",
             "不由", "忍不住", "直接", "开口", "只是", "同时", "随即", "立刻", "马上",
             "当即", "随后", "继续", "有些", "似乎", "已经", "再次", "一边", "一声",
             "嘴里", "口中", "低声", "高声", "大声", "小声", "冷声", "沉声", "喃喃",
             "果然", "竟然", "居然", "显然", "依然", "仍然", "蓦然", "旋即", "不禁",
             "说道", "解释", "不知", "问他", "问她", "问我", "心想", "暗想", "心中",
             "暗道", "大喊", "大叫", "嘀咕", "嘟囔", "反问", "追问", "回答", "补充",
             "对他", "对她", "对我", "对他们", "对两人", "咬牙", "咧嘴", "皱眉",
             "摊手", "耸肩", "挑眉", "翻了个", "低头", "抬头", "转头"}
PREPOSITIONS = ("对", "冲", "朝", "跟", "和", "与", "向", "被", "给")
FUNC_CHARS = set("的了着呢吗吧啊嘛么吗被把将和与跟或者地得")
CHAPTER_RE = re.compile(r"^第[\u4e00-\u9fa50-9]{1,8}[回章节]")
LOC_RE = re.compile(r"([\u4e00-\u9fa5]{1,6}?(?:山|岭|林|洞|村|庄|国|寺|观|河|涧|府|宫|殿))")
SCENE_SHIFT = re.compile(r"(行至|来到|至.{0,8}前|进山|出山|不上|须臾|不多时|当夜|次日|"
                         r"且说|话说|却说|一昼夜|此时|顷刻|半路|转步|回至|辞了)")
EMO_WORDS = {"怒": "怒", "骂": "怒", "喊": "急", "叫": "急", "惊": "惊", "怕": "惧",
             "慌": "惧", "喜": "喜", "笑": "喜", "哭": "悲", "悲": "悲", "苦": "悲",
             "冷笑": "怒", "大怒": "怒", "咬牙": "怒"}



# ── 性能：预编译常驻正则（原为循环内重建，163 万字 × 200 段 × 10 别名 = O(n·m) → O(1)）──
_names_re = re.compile(".")  # 占位，analyze() 时重建
_pron_re = re.compile(r"[他她][^，。]{0,3}$")

def clean_name(cand, aliases):
    cand = cand.strip()
    for p in PREPOSITIONS:          # 「对安迪」→「安迪」
        if cand.startswith(p) and len(cand) > 2:
            cand = cand[1:]
            break
    for j in LEAD_JUNK:
        if cand.startswith(j) and len(cand) > len(j) + 1:
            cand = cand[len(j):]
    if cand.endswith("知"):      # 「安迪知道」被懒惰匹配截出的「安迪知」
        cand = cand[:-1]
    return cand


PERF_MAP = [
    (r"笑吟吟|满面春生|陪俏语|喜道|心中欢", "轻笑+谄媚"),
    (r"哭道|悲|泪", "哭腔"),
    (r"骂道|大怒|怒道|发怒", "怒"),
    (r"大惊|惊道|慌|害怕", "惊"),
    (r"唆嘴|挑唆|谗言", "挑唆"),
    (r"作念|念咒|念念", "念咒"),
]
# 描写性引导词黑名单：候选含这些 → 真主语在其前面的描写短语之前
DESC_JUNK = re.compile(r"笑吟|满面|陪[^，。]{0,4}语|不胜欢|回心转意|作念|"
                       r"耳听善|扯住|唆嘴|自忖|思量|没奈何|心中欢|跪下[^，。]{0,4}|大惊")
# 主语回收：「那女子笑吟吟，忙陪俏语道」→ 主语=女子（允许 ≤16 非引号字符的描写链）
DESC_RECOVER = re.compile(r"(?:那|这)?([\u4e00-\u9fa5]{2,4})(?=[^”\"]{0,16}" +
                          r"(?:说道?|喊道?|叫道?|骂道|笑道?|哭道|答道|问道?|喝道?|言道|"
                          r"回道|叹道|冷笑道?|应道|沉声道?|高声道?|低声道?|吩咐道?|吩咐|"
                          r"答话|叫唤|嚷道|商议|喜道|怒道|惊道|呼道|道)" + r")")
# 变身注册表：妖/怪/精 主体「变作个X」→ X 是其伪装称谓
DISGUISE_RE = re.compile(r"(妖|怪|精|魔)[\u4e00-\u9fa5]{0,14}?变(?:作|做|个|成)个?"
                         r"([\u4e00-\u9fa5]{2,6})")
GENERIC_ROLES = ("女子", "女儿", "妇人", "老妇人", "老妇", "婆婆", "老翁", "老公公",
                 "公公", "村姑", "男子", "老者", "长老", "秀才", "书生")
# 同义称谓：变身句注册「女儿」，叙述里常改称「女子/村姑」
ROLE_SYNONYMS = {
    "女儿": ["女子", "村姑", "女儿", "小女"], "妇人": ["妇人", "老妇人", "婆子"],
    "老妇": ["老妇", "婆婆", "老妇人"], "老公公": ["老公公", "公公", "老翁", "老者"],
    "老翁": ["老翁", "老公公", "老者"], "村姑": ["村姑", "女子"],
}


def build_disguise_map(paras, alias_map):
    """妖精变身称谓 → 妖类本体：段落级判定（段落含妖类称谓 + 含「变作/做个X」）"""
    dm = {}
    demon = None
    for canon, al in alias_map.items():
        if any(k in canon for k in ("妖", "精", "怪", "魔")) or \
           any(k in a for a in al for k in ("妖精", "那怪", "怪物")):
            demon = demon or canon
    if not demon:
        return dm
    demon_tokens = [demon] + alias_map.get(demon, []) + ["妖", "怪", "精"]
    for i, p in enumerate(paras):
        ctx = (paras[i - 1] if i else "") + p   # 变身句常与主语段被排版拆行
        if not any(t in ctx for t in demon_tokens):
            continue
        for m in re.finditer(r"变(?:作|做|个|成)(?:个|一)?([\u4e00-\u9fa5]{2,12})", p):
            role = m.group(1)
            for g in GENERIC_ROLES:
                if g in role:
                    for s in ROLE_SYNONYMS.get(g, [g]):
                        dm.setdefault(s, demon)
    return dm


def resolve(cand, alias_map, disguise_map=None):
    if not cand:
        return None
    for canon, al in alias_map.items():
        if cand == canon or cand in al:
            return canon
    if disguise_map:
        for g, canon in disguise_map.items():
            if g in cand or cand in g:
                return canon
    for canon, al in alias_map.items():
        for a in [canon] + al:
            if a and len(a) >= 2 and a in cand:
                return canon
    return None


def analyze(text, names_cfg):
    alias_map = {}
    for item in names_cfg or []:
        canon, _, al = item.partition("=")
        alias_map[canon] = [a for a in al.split(",") if a]
    # 段落构建：按引号配平合并跨行对白（开引号与闭引号常被排版拆到两行）
    paras, buf = [], ""
    for ln in text.split("\n"):
        s = ln.strip()
        if not s or "<" in s or "&" in s or "=" in s or "#" in s:
            continue
        buf = s if not buf else buf + s
        if buf.count("“") == buf.count("”") and buf.count("「") == buf.count("」"):
            paras.append(buf)
            buf = ""
    if buf:
        paras.append(buf)

    chapters, cur_ch, cur_paras = [], None, []
    for p in paras:
        if CHAPTER_RE.match(p):
            if cur_ch is not None:
                chapters.append((cur_ch, cur_paras))
            cur_ch, cur_paras = p, [p]
        else:
            cur_paras.append(p)
    if cur_ch is None:
        cur_ch = "(无回目)"
    chapters.append((cur_ch, cur_paras))

    # ---- 自动挖掘候选人物（未提供 --names 或补充）----
    cand_freq = collections.Counter()
    for _, pl in chapters:
        for p in pl:
            for q in QUOTE_RE.finditer(p):
                pre = p[:q.start()]
                m = None
                for m in PRE_RE.finditer(pre[-24:]):
                    pass
                if m:
                    cand_freq[clean_name(m.group(1), alias_map)] += 1
                post = p[q.end():q.end() + 24]
                m2 = POST_RE.search(p[q.end():q.end() + 24])
                if m2:
                    cand_freq[clean_name(m2.group(1), alias_map)] += 1
    auto_cast = [c for c, n in cand_freq.most_common(40)
                 if n >= 2 and len(c) >= 2 and c not in AUTO_STOP
                 and not (set(c) & FUNC_CHARS)][:8]
    if not alias_map:
        for c in auto_cast[:6]:
            alias_map[c] = []
        print("[auto-cast]", ", ".join(f"{c}({cand_freq[c]})" for c in auto_cast[:6]))

    # ---- 逐段归属 ----
    dialogues = []          # 全书扁平
    mentions = collections.Counter()
    last_speaker = None
    global _names_re
    _names_re = re.compile("|".join(sorted(
        {a for _, al in alias_map.items() for a in [_c for _c in [_] + al if _c]},
        key=len, reverse=True)))
    disguise_map = build_disguise_map([p for _, pl in chapters for p in pl], alias_map)
    if disguise_map:
        print("[disguise]", disguise_map)
    for ci, (title, pl) in enumerate(chapters):
        for pi, p in enumerate(pl):
            for canon, al in alias_map.items():
                for a in filter(None, [canon] + al):
                    mentions[canon] += p.count(a)
            for q in QUOTE_RE.finditer(p):
                pre, post = p[:q.start()], p[q.end():]
                # 拟声词：不是台词，是音效指令（直接喂配音管线的 sfx 位）
                if q.group(1).strip() in ONOMATOPOEIA:
                    dialogues.append({"ch": ci, "para": pi, "speaker": None,
                                      "conf": "onomatopoeia", "raw_speaker": None,
                                      "perf": "sfx:" + q.group(1).strip(),
                                      "text": q.group(1), "emotion_hint": None,
                                      "para_head": p[:30]})
                    continue
                # 段内实体追踪（供代词回指）
                last_narrated = None
                for canon, al in alias_map.items():
                    for a in filter(None, [canon] + al):
                        if a in p:
                            last_narrated = canon
                speaker, conf = None, "alt"
                emo = None
                ctx = (pre[-12:] + q.group(1))[:40]
                for w, e in EMO_WORDS.items():
                    if w in ctx:
                        emo = e
                        break
                raw = None
                m = None
                for m in PRE_RE.finditer(pre[-24:]):
                    pass
                if m:
                    raw = clean_name(m.group(1), alias_map)
                    speaker = resolve(raw, alias_map, disguise_map)
                    if speaker:
                        conf = "pre"
                if speaker is None and raw and DESC_JUNK.search(raw):
                    # 描写性引导词：真主语藏在描写短语之前（那女子|笑吟吟，忙陪俏语|道）
                    dm = DESC_RECOVER.search(pre[-30:])
                    if dm:
                        raw = clean_name(dm.group(1), alias_map) or raw
                        speaker = resolve(raw, alias_map, disguise_map)
                        if speaker:
                            conf = "desc"
                if speaker is None:
                    m2 = POST_RE.search(post[:24])
                    if m2:
                        raw2 = clean_name(m2.group(1), alias_map)
                        if raw2:
                            raw = raw2
                            speaker = resolve(raw, alias_map, disguise_map)
                            if speaker:
                                conf = "post"
                if speaker is None:
                    m3 = _names_re.search(post[:14])
                    if m3:
                        speaker = resolve(m3.group(0), alias_map, disguise_map)
                        if speaker:
                            conf = "post-name"
                if speaker is None and _pron_re.search(pre[-6:]):
                    # 代词回指：段内最后出现的实体（他就嘲讽了句…）
                    if last_narrated:
                        speaker, conf = last_narrated, "pron"
                perf = None
                for pat, name in PERF_MAP:
                    if re.search(pat, pre[-18:]):
                        perf = name
                        break
                if speaker is None and raw and len(raw) >= 2 and \
                        raw not in AUTO_STOP and not (set(raw) & FUNC_CHARS):
                    conf = "unknown-name"   # 临时称谓（变身/路人）：显式浮出，不盲猜
                elif speaker is None:
                    speaker = last_speaker
                    conf = "alt"
                else:
                    last_speaker = speaker
                dialogues.append({"ch": ci, "para": pi, "speaker": speaker,
                                  "conf": conf, "raw_speaker": raw, "perf": perf,
                                  "text": q.group(1), "emotion_hint": emo,
                                  "para_head": p[:30]})

    # ---- 人物统计 ----
    cast = []
    total_ds = sum(1 for d in dialogues if d["speaker"])
    ncast = max(1, len(alias_map))
    unknown_names = collections.Counter(d["raw_speaker"] for d in dialogues
                                        if d["conf"] == "unknown-name")
    for canon, al in alias_map.items():
        ds = [d for d in dialogues if d["speaker"] == canon]
        emo_hist = collections.Counter(d["emotion_hint"] for d in ds if d["emotion_hint"])
        lens = [len(d["text"]) for d in ds] or [0]
        samples = [d["text"] for d in ds[:3]]
        dlgs = max(1, len(ds))
        avg_len = sum(lens) / len(lens)
        # 四轴自动估值（粗粒度先验，供 LLM 层修正；公式为启发式）
        share = len(ds) / max(1, total_ds)
        axes_est = {
            "energy": round(min(1, share * ncast * 0.55 +
                                max(0, (28 - avg_len) / 28) * 0.45), 2),
            "aggression": round(min(1, 2.2 * emo_hist.get("怒", 0) / dlgs +
                                    0.5 * emo_hist.get("急", 0) / dlgs), 2),
            "playfulness": round(min(1, 2.2 * emo_hist.get("喜", 0) / dlgs), 2),
            "composure": round(max(0, 1 - 2.2 * sum(emo_hist.values()) / dlgs), 2),
        }
        cast.append({"name": canon, "aliases": al,
                     "mentions": mentions.get(canon, 0), "dialogues": len(ds),
                     "avg_line_len": round(avg_len, 1),
                     "emotion_hist": dict(emo_hist), "sample_lines": samples,
                     "axes_estimate": axes_est,
                     "conf_dist": dict(collections.Counter(
                         d["conf"] for d in ds))})

    # ---- 场景节拍 ----
    beats, beat = [], {"start_para": 0, "loc": None, "dialogues": 0, "speakers": set()}
    for d in dialogues:
        beats and None
    beats = []
    cur = {"start_d": 0, "loc": None, "speakers": [], "n": 0}
    last_para = 0
    for idx, d in enumerate(dialogues):
        para_jump = d["para"] - last_para
        head = d.get("para_head", "")
        loc_m = LOC_RE.search(head)
        if idx and (para_jump >= 3 or SCENE_SHIFT.search(head)):
            cur["end_d"] = idx - 1
            beats.append(cur)
            cur = {"start_d": idx, "loc": loc_m.group(1) if loc_m else None,
                   "speakers": [], "n": 0}
        if cur["loc"] is None and loc_m:
            cur["loc"] = loc_m.group(1)
        if d["speaker"]:
            cur["speakers"].append(d["speaker"])
        cur["n"] += 1
        last_para = d["para"]
    cur["end_d"] = len(dialogues) - 1
    beats.append(cur)
    for b in beats:
        b["speakers"] = sorted(set(b["speakers"]))
    return {"chapters": [t for t, _ in chapters], "n_paras": len(paras),
            "n_dialogues": len(dialogues),
            "attribution_rate": round(sum(1 for d in dialogues
                                          if d["conf"] != "none") / max(1, len(dialogues)), 3),
            "unknown_speakers": dict(unknown_names.most_common(10)),
            "cast": cast, "dialogues": dialogues,
            "beats": beats}


def emit_cards(analysis, src_name, out_dir):
    d = Path(out_dir) / "charcards_draft"
    d.mkdir(parents=True, exist_ok=True)
    for c in analysis["cast"]:
        if c["dialogues"] < 2:
            continue
        card = {
            "name": c["name"], "franchise": src_name,
            "profile": {
                "age_apparent": "TODO", "gender": "TODO", "archetype": "TODO",
                "personality_axes": {"energy": 0.5, "aggression": 0.5,
                                     "playfulness": 0.5, "warmth": 0.5,
                                     "composure": 0.5},
                "background": "TODO",
                "signature_lines": c["sample_lines"][:3],
                "speech_traits": {"pace": "TODO", "pitch": "TODO",
                                  "timbre": "TODO", "accent": "TODO"},
            },
            "auto_analysis": {k: c[k] for k in
                              ("mentions", "dialogues", "avg_line_len",
                               "emotion_hist", "aliases", "conf_dist")},
            "community_refs": [
                {"source": "TODO-搜索社区配音理解", "insight": "", "url": ""}],
            "voice_design": {
                "target": {"gender": "TODO", "age": "TODO", "pitch": 0.5,
                           "energy": 0.5, "timbre_keywords": []},
                "edge_engine": {"voice": "TODO", "adjust": {"rate": "+0%",
                                                           "pitch": "+0Hz"},
                                "why": ""},
                "neural_engine": {"reference_strategy": "",
                                  "emotion_presets": {}},
            },
            "emotion_presets": {},
        }
        (d / f"{c['name']}.card.json").write_text(
            json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"角色卡骨架 x{len([c for c in analysis['cast'] if c['dialogues'] >= 2])} -> {d}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("novel")
    ap.add_argument("--out", required=True)
    ap.add_argument("--names", nargs="*", default=[])
    a = ap.parse_args()
    text = Path(a.novel).read_text(encoding="utf-8")
    res = analyze(text, a.names)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "analysis.json").write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    emit_cards(res, Path(a.novel).stem, out)
    (out / "beats_draft.json").write_text(
        json.dumps(res["beats"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"章回 {len(res['chapters'])}｜段落 {res['n_paras']}｜对白 {res['n_dialogues']}｜"
          f"归属率 {res['attribution_rate']*100:.0f}%｜节拍 {len(res['beats'])}")
    for c in sorted(res["cast"], key=lambda x: -x["dialogues"])[:8]:
        print(f"  {c['name']:6} 提及{c['mentions']:3} 对白{c['dialogues']:3} "
              f"均长{c['avg_line_len']:5.1f} 情绪{c['emotion_hist']}")


if __name__ == "__main__":
    main()
