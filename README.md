# zcode-skills

个人 ZCode 技能仓库（personal agent skills）。目录结构遵循 ZCode 技能发现规范：`.agents/skills/<name>/SKILL.md`——整个仓库克隆到任何项目目录下，里面的技能即可被 ZCode 项目级发现自动加载。

## 当前技能

| 技能 | 用途 | 触发方式 |
|---|---|---|
| `syscheck` | Windows 系统深度体检与清理（地面真相→孤岛反推理→缓存分类→系统底层→规则层审计），含联接农场防误杀红线 | 说"清理C盘/系统体检/扫孤岛"自动触发，或 `/syscheck` |
| `hyperv-lab` | Windows Pro 上零第三方依赖部署可抛弃式 Linux 实验服务器：Hyper-V + Ubuntu 官方云金镜像 + cloud-init 静默部署 + 底片快照回滚 + 系统报告（企业部署范式的个人机复刻） | 说"装 Linux 环境/要台测试服务器/静默装机/金镜像/重装练习"自动触发 |

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
