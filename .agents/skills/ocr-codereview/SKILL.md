---
name: ocr-codereview
description: 阿里 OpenCodeReview（ocr CLI）驱动的 AI 代码审查。用户说"ocr 审查/审审代码/code review/代码评审/审这个提交/审分支/扫一下这个库/帮我审"时使用——本机已部署已配好 LLM（免费 coding plan 端点），直接调 ocr 命令出结构化审查意见（行级定位+修复建议），含工作区/分支/单 commit/全文件扫描/委托模式五种玩法与实测踩坑。
---

# ocr：AI 代码审查（OpenCodeReview）

## 本机部署现状（已就绪，无需安装）

- 二进制：`D:\Program Files\Alibaba\OpenCodeReview\ocr.exe`（静态，**不自动更新**），已加用户 PATH
- LLM 已配好：provider=z-ai + url 覆盖到用户 coding plan 免费端点 + glm-5.3 + 评论中文；配置在 `~/.opencodereview/config.json`（key 在配置文件里，**不入库**）
- 验证：`ocr llm test`（应看到 Connection test successful + Tool-call round trip verified）
- 依赖 Git ≥ 2.41（本机 2.55 ✓）

## 命令速查（按审查对象选模式）

| 场景 | 命令 |
|---|---|
| 工作区改动（staged+unstaged+untracked） | `ocr review` |
| 最近一次提交 | `ocr review -c HEAD` |
| 指定提交 | `ocr review -c <sha>` |
| 分支对比（merge-base 起） | `ocr review --from main --to feature` |
| 全文件扫描（审陌生库/无 diff 目录，不需要 git 历史） | `ocr scan --path <目录或文件>` |
| 注入业务背景 | `-b "重点看并发"` 或 `-B 需求文档.md` |
| 结果给机器读 | `-f json -o out.json`（配 `--audience agent` 抑制进度行） |
| 浏览器回放历史审查/标记已修复 | `ocr viewer`（localhost:5483） |
| 中断续审 | `ocr session list` → `--resume <id>` |

## agent 工作流（ZCode 会话内使用）

1. **定对象**：`git status` / `git log --oneline -5` 看用户要审什么——工作区用 `ocr review`，特定提交用 `-c`，没 diff 的老代码用 `ocr scan`
2. **跑审查**（1 文件组约 1.5-2 分钟，340 行级提交 5-8 分钟；建议后台跑，日志别接 `| tail`——管道缓冲会看不到进度，直接读输出文件）
3. **读结果按严重度处理**：critical/high（bug/安全）必须报告或修复；medium 附上下文；low 只在确有价值时提——ocr 自己也会丢低价值噪声，别把它丢的捡回来
4. 修复后可再跑一轮对比：`ocr session compare <before> <after>`

## 实测踩坑（2026-10-01 两轮实战）

- **round 2 超时**：coding plan 端点对长上下文偶尔 `context deadline exceeded`——round 1 的 findings 仍然有效可用，不是整体失败；重跑一次通常就好
- **速度参考**：单文件小改 ~33k token / 1.5 分钟（免费套餐内）；大提交按文件组数线性放大
- **effort**：默认 medium（每组 2 轮）；赶时间 `--effort low`，要召回 `--effort high`
- **--exclude**：工作区模式会把 untracked 全审进来，混入无关文件时用 `--exclude '目录/*'` 剔除
- **准确性实测**：玩具仓库 3 埋雷全中+行号全准；审自家 340 行提交 4/4 真问题、90 行 JS 6 条全真——误报率低，findings 可直接采纳
- **空跑安全**：`ocr review --preview` 只列将审哪些文件/排除原因，不调 LLM

## 委托模式（零 key 玩法，ZCode 当宿主）

不给 ocr 配 LLM 也能用：ocr 做文件筛选+规则解析，ZCode 自己审。

```bash
ocr delegate preview                    # 列可审文件+排除原因+mode/ref 元数据
ocr delegate rule src/A.java src/B.java # 按规则内容分组输出审查清单
```

宿主流程：preview 拿文件列表 → rule 拿规则 → `git diff <merge_base>..<to> -- <path>`（或 workspace 用 `git diff HEAD` / `cat`）→ 按清单逐文件深审 → 按 Critical/High/Medium/Low 分级报告。

## 维护

- 升级（静态二进制）：`python ~/.agents/skills/github-proxy/scripts/ghproxy.py download https://github.com/alibaba/open-code-review/releases/latest/download/opencodereview-windows-amd64.exe -o "D:\Program Files\Alibaba\OpenCodeReview\ocr.exe"`（ghproxy download 子命令自动竞速加速）
- 换模型：`ocr config model`（交互）或 `ocr config set model <名>`；`ocr llm providers` 看内置供应商
- 想要编辑器内行内评论：有 IDEA/VSCode 插件（`extensions/idea`，兼容 2026.2），但需 JDK21 自构建，CLI 够用就别折腾
