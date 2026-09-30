---
name: nvidia-img
description: 英伟达（NVIDIA build.nvidia.com）免费生图。用户说 英伟达生图/NVIDIA 生图/flux 生图/用英伟达画一张/nvimg 时使用——走 NVIDIA 免费 credits 的 flux.1-dev（约 12s/张、JPEG 输出），不耗 AutoClaw/即梦积分；与 autoclaw-ops 的即梦生图互为替补。
---

# nvidia-img — NVIDIA 免费生图（flux.1-dev）

## 什么时候用

- 用户点名 英伟达 / NVIDIA / flux 生图
- 即梦积分紧张、或想批量白嫖出图时的免费替补（每张约扣 1 credit，个人账户共 1000）

## 快速用法

```bash
python ~/.agents/skills/nvidia-img/scripts/nvimg.py "a red cat sitting on a windowsill, watercolor style" -o cat.jpg
```

脚本全自动：找 key → 调接口 → 存 JPEG → 打印路径。提示词建议英文（flux 对中文提示词理解弱）。

## 提示词英文重构协议（调用方 LLM 必读）

接口只吃**一个英文 prompt 字符串**：任何额外字段（aspect_ratio / size / negative_prompt…）都会 422；不支持负向提示词。
用户给中文或口语化描述时，调用脚本前先把提示词重构为英文：

1. **意图零丢失**：主体、动作、环境、风格、氛围全保留，不擅自加戏
2. 写成一句连贯英文描述（flux-dev 对自然语言友好），约 30–60 词、逗号分节，顺序：主体+动作 → 环境/背景 → 光线/色调 → 艺术风格/媒介 → 画质收尾
3. 风格词给具体媒介与流派（watercolor / oil painting / cinematic photo / 3D render），**不要堆 "8k, masterpiece, best quality" 这类 SD 老咒语**，flux 不吃
4. 重构完把英文直接写进脚本 prompt 参数执行；回复用户时附上最终英文提示词，方便他复用微调
5. 想再精细可先过 `prompt-optimizer` 技能精准档再落英文（可选，不强制）

## 接口要点（2026-10-01 实测）

| 项 | 值 |
|---|---|
| 端点 | `POST https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev` |
| host 坑 | 生图在 `ai.api.nvidia.com`，**不是**聊天的 `integrate.api.nvidia.com` |
| 认证 | `Authorization: Bearer nvapi-...` |
| body | `{"prompt": "..."}` —— 只确认 prompt 可用，加 aspect_ratio 等额外字段会 422 |
| 返回 | `artifacts[0].base64` = JPEG |
| 耗时 | 约 12s/张，超时给 180s |
| curl 坑 | 本机 curl.exe 必须带 `--ssl-no-revoke` |

## Key 解析（脚本自动，无秘钥入库）

1. 环境变量 `NVIDIA_API_KEY`
2. `C:\Users\12696\.zcode\v2\provider_config.json` 里 `providerName=nvidia` 的 `access.apiKey`（ZCode 里换 key 后技能自动跟随）

## 模型现状快照（会过期，异常时重测）

- `black-forest-labs/flux.1-dev` ✅ 可用
- `black-forest-labs/flux.1-schnell` ⚠️ 端点活着但 GPU 不调度（挂起数分钟无响应），勿用
- SDXL / SD3 / SD3.5 / stable-image-core / Sana ❌ 全部 404 已下线

## 和其他生图渠道的关系

- `autoclaw-ops` 即梦 Seedream = 日常主力（中文理解好、管线全、垫图 --ref）
- 本技能 = 免费替补 / 批量出图 / 即梦额度紧张时
