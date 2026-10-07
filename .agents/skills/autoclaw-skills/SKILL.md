---
name: autoclaw-skills
description: >
  直接调用 AutoClaw（智谱 Zwork，装于 D:\Program Files\AutoClaw）内置的 100+ 技能库，
  无需打开 AutoClaw 客户端。用户说"用 autoclaw 的 xx 技能/用 dcf-model 建模/
  按它的深度研究跑/autoclaw 里那个报告技能"时使用——先查本索引路由到具体技能，
  再 Read 其 SKILL.md 按工序执行。覆盖：金融建模（dcf/lbo/comps/三表）、法律全流程
  （检索/合同/风险）、深度研究、财报/研报生成、xlsx/pptx/docx/pdf 生产线、
  ASR 翻译/去背景/文件上云等。
---

# AutoClaw 技能直调路由

AutoClaw 2.0.1（ZCode 同门，OpenClaw 系内核）在安装目录预置了 103 个标准 SKILL.md
格式技能。技能本体不复制（随 AutoClaw 升级自动更新），本路由只做索引与适配。

**技能库根目录**（唯一读取入口，下称 `$AC`）：
`D:\Program Files\AutoClaw\resources\app\dist\resources\skills-preinstall`
另有 `$AC-agent` = `...\resources\agent-skills`（lark/飞书四件套，走飞书开放平台 API，
需飞书凭证，外部直调价值低）。

## 使用流程

1. 按下方分类索引锁定技能名（拿不准就把用户需求与各 description 匹配，或读
   `$AC/manifest.json` 全量清单）。
2. `Read $AC/<技能名>/SKILL.md`，把其工序当作自己的执行指导。
3. 概念适配（AutoClaw 内部设施 → 本环境等价物）：
   - `{run_dir}` 工作目录 → 当前工作区下自建 `./ac-run/<任务>/`
   - "Agent 集群 / worker / S5 / SOP" → 我自己分角色推进或 spawn 子 agent
   - "GLM-Office / write-skill 交付" → 我直接产出文档文件
   - "进度协议 / [来源] 标注" → 保留遵守（deep-research 等对信度分级要求严格）
4. B 类脚本直接跑：`python $AC/<技能名>/xxx.py`（优先用 `$AC` 同级的
   `D:\Program Files\AutoClaw\resources\vendor\python|bun|node` 保持版本一致，
   系统 Python 缺依赖时改用 vendor）。

## 三类可用性（动手前必判）

| 类 | 条件 | 技能 |
|---|---|---|
| **A 纯指令** 82个 | 零依赖，直接照做 | 金融建模：3-statement-model, dcf-model, lbo-model, comps-analysis, deal-comps, sources-uses, accretion-dilution, scenario-analysis, bond-profile, curve-spread, index-valuation…；投研：deep-research, research-report, earnings-*, morning-note, sector-overview, macro-dashboard, idea-generation, watchlist, event-monitor, peer-benchmark…；法律：case-retrieval, contract-review, contract-desensitize, legal-*, dispute-issue-identification, evidence-evaluation…；财报线：financial-reporting, financial-reporting-core, financial-analysis-core, audit-xls, ledger-reconciliation, month-end-close-review…；通用：multi-document-summarization, memory, find-skills, frontend-page-design, model-update |
| **B 带脚本** 18个 | 脚本自足，直接跑；个别内部调云 API（跑前 grep 确认） | xlsx, xlsx-author, pptx, pptx-author, docx, pdf, pdf-text-extractor, report-render, financial-reporting-report-render, financial-reporting-xlsx-author, legal-docx-generator, legal-legal-docx-revisor, legal-research-drafting, autoglm-remove-bg, jianwei, tianyancha, wecom-unified, skill-creator |
| **C 云桥** 3个 | 需 AutoClaw 后台进程活着（本地桥 127.0.0.1:18432 出 token；启动 `D:\Program Files\AutoClaw\AutoClaw2.exe` 后窗口可最小化，无需 UI 操作） | autoglm-asr-translate, autoglm-file-upload, autoclaw-billing |

注：jianwei/tianyancha/wecom/feishu 系虽归 B，实质依赖外部账号数据源，跑前看脚本的鉴权方式；
`autoclaw-migration`、`zwork-orchestration`（agent-skills-core）是 AutoClaw 内部编排，勿外部调用。

## 内容创作专区（type=content，官方分类 2026-09-30 快照，共 21 个）

按「用途 × 成本」标记。**带 💰 = 消耗积分**（走 [[autoclaw-ops]] 积分通道，调用前告知用户）；其余免费（本地或纯文本）。

**🎨 生图/改图（💰 积分）**
- 💰 即梦生图（Seedream 文生图/改图，配图、视觉设计首选）
- 💰 图片编辑（加字/换背景/改风格，官方标注"消耗积分"）
- 💰 图片搜索（AutoGLM 搜图接口）

（vidu图片/视频生成已剔除：需自带 Vidu 账号 token 才可用，本机无 Vidu 账号，不纳入路由）

**🎬 视频（💰 积分，贵——HappyHorse 官方原话"费用较高请按需使用"）**
- 💰 HappyHorse 视频生成（广告/科技风文生视频；vidu 已剔除，视频仅此一条路）

**✍️ 写作（免费）**
- 文案写作（落地页/邮件/广告/销售页文案）
- blog-writer（个人风格博客长文）
- 卡兹克写作（公众号长文，风格化）
- SEO内容优化（关键词布局/标题层级/精选摘要）
- 内容策略（内容日历/渠道选择/营销体系）
- AI文本去味器（中文去 AI 味）
- Prompt-Generation（丢参考图→产高质量生图提示词；喂给即梦省钱省积分）
- 头脑风暴（先探索意图需求再动手的前置工序）

**🖥️ 设计/网页/PPT（免费，本地渲染）**
- UI设计与PPT制作（含设计专家 agent，无问答版=不中途提问直接产）
- 落地页与网页设计（官网/落地页/作品集展示页）
- website-builder（可部署代码，含电商站）
- ppt-swarm（多智能体协同产 PPT，基于数据/项目摘要）
- delivery-artifact（成果→单文件 HTML：文档/杂志长文/交互页/PPT 四形态）

**🔧 图片/视频处理（免费，本地）**
- 去除背景（autoglm-remove-bg，纯色底→透明 PNG，即梦产物配套）
- ffmpeg-video-editor（自然语言→FFmpeg：剪切/转码/压缩/提取音频）

> 纪律：写作/网页/PPT 需求默认走免费组；只有用户明确要"生成图片/视频"才动 💰 组。生图前可先用 Prompt-Generation（免费）打磨提示词，一次出图成功率更高=更省积分。
> 其余 8 类（金融投研52/办公效率27/财务分析17/法律17/系统工具14/信息收集13/赛博灵魂10/开发工具9）全量清单在 `$AC/manifest.json` 与本地预装目录，按需读。

## 红线

- `$AC` 目录只读——AutoClaw 升级会校验 manifest 的 contentSha256，改写=更新器报损。
- C 类技能的 token 只从本地桥取，不要缓存/打印到交付物。
- AutoClaw 升级后技能集可能变化，索引与本清单漂移时以 `$AC/manifest.json` 为准。
- 💰 组技能等价于 autoclaw-ops 的积分端点，严禁顺手测试/循环调用。


