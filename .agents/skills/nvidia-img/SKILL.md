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
