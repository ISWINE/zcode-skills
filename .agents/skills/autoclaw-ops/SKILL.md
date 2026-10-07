---
name: autoclaw-ops
description: >
  把 AutoClaw 账号能力当工具直调（无需打开 AutoClaw 客户端）。成本分诊铁律：对话/推理/写码
  一律走用户 coding-plan key（免费套餐，open.bigmodel.cn/api/coding/paas/v4）；只有生图
  （即梦 Seedream）、视频（HappyHorse）等生成类才走 AutoClaw 登录态积分端点。用户说"生成图片/
  画一张/即梦生图/做个视频/HappyHorse"时用积分端点（scripts/ac-api.js img|video）；说"用免费模型/
  coding plan 跑一下/随便问"或任何普通分析写码任务时用 chat（免费）。另含联网搜索、起标题、
  模型目录查询。登录态用 DPAPI+AES-GCM 从 Roaming\AutoClaw\accounts 解密，AutoClaw 在线时自动续票。
---

# AutoClaw 账号能力直调

统一入口：`node <本技能>/scripts/ac-api.js <子命令>`

## 成本分诊（最重要的一张表）

| 任务类型 | 通道 | 成本 | 命令 |
|---|---|---|---|
| 对话/推理/写码/分析/翻译 | coding-plan key → open.bigmodel.cn | **免费**（套餐内） | `ac-api.js chat "问题"` |
| 指定免费模型 | 同上 | 免费 | `ac-api.js chat glm-5.3 "问题"`（先 `models-free` 看可用） |
| **生图（即梦 Seedream）** | AutoClaw 积分 | **积分** | `ac-api.js img "提示词"` |
| 视频（HappyHorse，3-15秒） | AutoClaw 积分 | **积分（贵，先确认）** | `ac-api.js video "提示词"` |
| 识图（image-recognition） | AutoClaw 积分 | **积分** | `POST /skills/image-recognition {image_url,prompt}` |
| OCR（ocr） | AutoClaw 积分 | **积分** | `POST /skills/ocr`（multipart file） |
| 搜图（search-image） | AutoClaw 积分 | **积分** | `POST /skills/search-image {query}` |
| 联网搜索 | AutoClaw | 免费 | `ac-api.js search "关键词"` |
| 会话起标题（GLM 代理） | AutoClaw | 免费 | `ac-api.js title "内容"` |
| 模型目录 | 两侧 | 免费 | `ac-api.js models-managed` / `models-free` |

**纪律**：积分很宝贵（用户原话）。默认一律 chat（免费）；img/video 必须是用户明确要"生成图片/视频"才调；video 单次最多 20 分钟 + 更多积分，调用前向用户确认。

## 底层配方（排障时看）

- **免费通道**：`POST https://open.bigmodel.cn/api/coding/paas/v4/chat/completions`，`Authorization: Bearer b6c020b885ac453e816975a4b42a5a55.lu6PYgytajBGp1Vj`（用户 coding-plan 套餐 key，已授权）。OpenAI 兼容。
- **积分通道**：`Authorization: Bearer <AutoClaw accessToken>` + 指纹头 `X-Auth-Appid:100003 / X-Auth-TimeStamp:<秒> / X-Auth-Sign:md5("100003&<ts>&38d2391985e2369a5fb8227d8e6cd5e5") / X-Version:2.0.1 / X-Tm:win / X-Product:autoclaw / X-Lang:zh-CN / X-Channel:official`，origin `https://autoglm-acceleration-api.zhipuai.cn`。
  - 已验证端点：`/agentdr/v1/assistant/skills/generate-image-seedream`（生图）、`/skills/happy-horse-create`（视频）、`/skills/search-image|image-recognition|ocr`、`/skills/web-search`、`/generate-session-title`、`/autoclaw-proxy/proxy/autoclaw-model-config`。另有 tianyan/jianwei/ifind/wind/legal 系（路径搜 main.cjs `/agentdr/v1`）。
- **登录态解密**（脚本自动做）：`Local State`→os_crypt.encrypted_key→DPAPI→32B key→`accounts/<64hex>/account-credentials.enc`(v10=AES-256-GCM)→accessToken(24h)/refreshToken(30d)。AutoClaw 客户端在线会自动刷新磁盘凭据，重读即新票。C 侧 Roaming\AutoClaw 是联接（真身 D:\cshift），路径用 %APPDATA% 即可透明穿透。
- **未破**：`/autoclaw-proxy/proxy/autoclaw/chat/completions` 直连 flash 恒 400（不认账号 token，另有客户端签名层）——**不需要了**，对话需求由免费通道覆盖。

## 红线

- 本技能含用户私密 key 与解密逻辑，仅本机使用，不得进公开仓库、不得把 token/key 打进交付物。
- HappyHorse/即梦是计费端点，严禁循环调用或"顺手测试"。
- AutoClaw 大版本升级后若端点 401/404：重跑解密链拿新票；仍失败则按 [[autoclaw-cloud-api]] 记忆里的攻坚方向排查。
