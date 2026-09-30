---
name: shadio-video
description: 从小说原文到成品视频/听书音频的全管线制作技能。用户说「制作动画/做视频/配音/沙雕动画/小说转视频/听书/声音克隆/角色卡/多角色配音」时自动触发。支持三种风格：水墨故事卡视频、沙雕熊猫头动画、GPT-SoVITS 声音克隆听书。含小说系统辨识器（对白归属/变身注册/情绪分布）、角色卡工具（人物分析+音色匹配）、PIL 卡片生成、ffmpeg 渲染 QC、UVR 人声分离、零样本克隆。
---

# 沙雕动画制作技能（shadio-video）

从小说原文到成品视频/听书音频的全管线：小说系统辨识 → 角色卡配音 → 分镜渲染 → 混音质检。
支持三种输出风格（水墨故事卡 / 沙雕熊猫头 / GPT-SoVITS 声音克隆听书）。

用户说「制作动画 / 做视频 / 配音 / 沙雕动画 / 小说转视频 / 听书 / 声音克隆」时自动触发。

## 前置条件

| 依赖 | 检查 | 安装 |
|---|---|---|
| Python ≥3.10 | `python --version` | 系统 |
| PIL | `python -c "import PIL"` | `pip install pillow` |
| edge-tts | `sdbgj/.venv/Scripts/python -m edge_tts --version` | `pip install edge-tts` |
| ffmpeg + ffprobe | `ffmpeg -version` | [npmmirror 二进制](references/lessons.md#ffmpeg-安装) |
| GPT-SoVITS（可选） | `D:\tools\gpt-sovits\*\runtime\python.exe` 存在 | [整合包 7.6GB](references/lessons.md#gpt-sovits-安装) |
| faster-whisper（可选） | `python -c "import faster_whisper"` | `pip install faster-whisper` |
| audio-separator（可选） | `python -c "import audio_separator"` | `pip install audio-separator` |

无 GPT-SoVITS 时降级为 edge-tts 多角色分声；无 faster-whisper 时跳过 ASR 步骤。

## 管线总览

```
小说原文(txt)
  │
  ▼ scripts/novel_analyzer.py ─→ analysis.json + 角色卡骨架 + 场景节拍
  │
  ▼ scripts/voicecard_gen.py ─→ 角色卡（人物分析+社区理解+音色绑定）
  │
  ▼ 人工/LLM 编写 scenes.json（分镜+台词+情绪+音效标记）
  │
  ├──→ [水墨正传] gen_ink_cards.py → build_video.py → qc_video.py → out/preview.mp4
  │
  ├──→ [沙雕动画] gen_panda_cards.py → build_video.py → qc_video.py → out/preview.mp4
  │
  └──→ [克隆听书] uvr_clean.py → clone_drama.py → simple_mix.py → out/radio_*.mp3
```

## 快速开始

### 1. 分析小说

```bash
python scripts/novel_analyzer.py 小说.txt --out out \
  --names "主角=别名1,别名2" "女主=别名A"
```

输出 `analysis.json`（对白归属/人物统计/场景节拍/情绪分布）+ 角色卡骨架。

### 2. 建角色卡

```bash
python scripts/voicecard_gen.py new 角色名     # 骨架
# 填 profile/community_refs/voice_design 后
python scripts/voicecard_gen.py validate 角色名.card.json
python scripts/voicecard_gen.py match 角色名.card.json   # 音色评分
```

### 3. 编写 scenes.json

```json
{
  "voice_map": {
    "旁白": {"voice": "zh-CN-liaoning-XiaobeiNeural"},
    "主角": {"voice": "zh-CN-YunyangNeural"}
  },
  "scenes": [
    {"id": "S1", "lines": [
      {"speaker": "旁白", "as": "narr", "text": "原文照读。", "gap": 0.3}
    ]}
  ]
}
```

### 4. 渲染

**水墨视频**：
```bash
python scripts/gen_ink_cards.py   # 生成水墨卡
python scripts/tts_edge.py        # edge-tts 配音
python scripts/build_video.py     # zoompan+xfade+字幕+混音
python scripts/qc_video.py        # 黑帧/静音/响度/抽帧
```

**沙雕视频**：
```bash
python scripts/gen_panda_cards.py  # 熊猫头表情包卡
# 后续同上
```

**克隆听书**：
```bash
# 前提：GPT-SoVITS api_v2 已启动（见 lessons.md）
python scripts/uvr_clean.py ref1.wav ref2.wav   # 参考音频人声分离
python scripts/clone_drama.py scenes.json        # GPT-SoVITS 克隆合成
python scripts/simple_mix.py                     # 极简拼接+音效
```

## 配音铁律（踩坑换来的）

1. 一人一音色：Yunjian=武将/旁白位，Yunyang=主角位，Yunxi=搞笑配角位
2. 暴怒/叫阵 = **降调+放慢+加音量**（不是高音快语速——那是尖细）
3. 重读增益必须在 ffmpeg 拼接层做（TTS 端 volume 会被服务端压扁）
4. 分声剧集禁用 loudnorm（会压平刻意动态对比）
5. 动物拟声一律真音效不用 TTS
6. 老年男声基频上升（不下降）
7. 旁白开头禁用「话说」，每集开场句式必须不同
8. 音色评分器只出候选，人的耳朵+实测做裁决并记录否决理由

## 代码规范

- 复杂滤镜链 amix 多输入可能静默失败 → 产出必须抽查人声点
- concat 列表必须用绝对路径
- `replace()` 不命中时静默无错 → 改完必须 assert 验证
- edge-tts rate/pitch/volume 必须带显式符号（`+0%` 不是 `0%`）
- edge-tts 拒纯拟声词（"汪汪汪。"→ NoAudioReceived）
- Bash 管道 `| tail` 吞退出码 → `set -o pipefail`

## 网络规范

- GitHub 镜像：`scripts/gh_mirror.py` 每次现测速取最快
- ModelScope 下载 25MB/s（npmmirror 二进制同理）
- HF 模型走 hf-mirror.com
- curl.exe 必须 --ssl-no-revoke（dev-sidecar 代理环境）

## 详细参考

- [踩坑全记录](references/lessons.md)——ffmpeg 安装/GPT-SoVITS 部署/UVR 分离/edge-tts 陷阱/正则预编译优化等 30+ 坑
