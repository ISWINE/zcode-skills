# zcode-skills

个人 ZCode 技能仓库（personal agent skills）。目录结构遵循 ZCode 技能发现规范：`.agents/skills/<name>/SKILL.md`——整个仓库克隆到任何项目目录下，里面的技能即可被 ZCode 项目级发现自动加载。

## 当前技能

| 技能 | 用途 | 触发方式 |
|---|---|---|
| `syscheck` | Windows 系统深度体检与清理，v2 可移植到任何电脑：INIT 机器画像（harness 由 agent 自认）→ 阶段A 粗扫出大致报告（Everything/es.exe 秒级全卷枚举，缺工具自动下载便携包到工作区）→ 阶段B 精扫（地面真相→孤岛反推理→缓存分类→系统底层→规则层审计）出精细报告，含联接农场防误杀红线 | 说"清理C盘/系统体检/扫孤岛/出体检报告"自动触发，或 `/syscheck` |
| `hyperv-lab` | Windows Pro 上零第三方依赖部署可抛弃式 Linux 实验服务器：Hyper-V + Ubuntu 官方云金镜像 + cloud-init 静默部署 + 底片快照回滚 + 系统报告（企业部署范式的个人机复刻） | 说"装 Linux 环境/要台测试服务器/静默装机/金镜像/重装练习"自动触发 |
| `windows-config` | Windows 系统配置项手册：每项含需求/原理/改法/验证/回滚，只收本机已验证的修改 | 说"关提示音/改 Windows 设置"自动触发，或说"把这个加进 windows 配置"收录新项 |
| `shadio-video` | 小说→动画/听书全管线：系统辨识→角色卡配音→分镜渲染→克隆听书（水墨/沙雕/克隆三种风格） | 说"制作动画/配音/沙雕动画/小说转视频/听书/声音克隆"自动触发 |
| `github-proxy` | GitHub 国内随机屏蔽自愈：镜像代理池（种子+scriptcat+聚合API 三层采集）→ 双探针测速 → 基线中位数 → 劣化自动换线；apply 后 git clone/raw/codeload 全透明走镜像 | GitHub 打不开/clone 慢/raw 超时/push 失败时自动触发，或说"换镜像/加速 github" |
| `nvidia-img` | 英伟达（NVIDIA build.nvidia.com）免费生图：flux.1-dev 直调（约 12s/张 JPEG），key 自动从 ZCode 配置读不入库；即梦生图的免费替补 | 说"英伟达生图/NVIDIA 生图/flux 生图/用英伟达画一张/nvimg"自动触发 |
| `ocr-codereview` | 阿里 OpenCodeReview（ocr CLI）AI 代码审查：工作区/单 commit/分支/全文件扫描/委托模式五种玩法，本机已配免费 coding plan 端点，行级定位+修复建议 | 说"ocr 审查/审审代码/code review/审这个提交/扫一下这个库"自动触发 |
| `playwright-toolkit` | Playwright 本机工具箱：npmmirror 镜像装 Chromium、cookie 注入开登录态页面、SPA 接口抓取（response 监听让页面自己暴露 API）、表单/文件上传自动化；附 B 站全代码投稿实录（扫码登录→抓稿件接口→upos 分片→edit 全量 videos[]） | 说"用 Playwright/抓接口/登录态页面自动化/装 Chromium/浏览器镜像"自动触发 |

## 本机部署方式（junction 联接）

真身在 `D:\projects\zcode-skills\.agents\skills\<name>`，用户级发现路径 `~/.agents/skills/<name>` 是指向它的 JUNCTION：

```cmd
mklink /J C:\Users\12696\.agents\skills\<name> D:\projects\zcode-skills\.agents\skills\<name>
```

改技能直接改本仓库文件即可（联接透明），改完记得 commit + push。

## 扩充新技能

1. 在 `.agents/skills/` 下新建 `<name>/SKILL.md`（frontmatter 必须含 `name` 和 `description`，name 与目录同名，kebab-case）
2. 可选挂 `scripts/`（可执行脚本）、`references/`（模型按需读的细节文档）、`assets/`（模板）
3. 需要用户级可用就在本机做联接（见上）；仅项目用则随仓库克隆自动生效
4. `SKILL.md` 控制在 500 行内，细节往 `references/` 拆

## 同步

```bash
cd /d/projects/zcode-skills
git add -A && git commit -m "..." && git push
```

## 注意

- `syscheck/references/lessons.md` 与 `E:\笔记\笔记\系统软件清单.md` 含本机路径与架构信息，仓库保持 **private**
- 技能里的机器特定事实（联接表、用户决定）以清单文件为唯一真相源，本仓库只存方法论与脚本
