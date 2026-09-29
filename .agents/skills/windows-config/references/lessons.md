# windows-config 踩坑记录

## Git Bash 调 Windows 原生工具被 MSYS 路径转换坑

Git Bash 会把 `/E` 这类开关当路径转成 `E:/`，robocopy 报「无效参数」、mklink 引号被 cmd 吃掉报「文件名、目录名或卷标语法不正确」。解法：

- 命令前加 `MSYS_NO_PATHCONV=1`
- 或建联接改用 PowerShell：`New-Item -ItemType Junction -Path <link> -Target <target>`（junction 免管理员权限，比 cmd mklink 省引号）

## 本机无全局 git 身份

git commit 报 Author identity unknown。各仓库用仓库级 config（不动全局）：

```
git -C <repo> config user.name "ISWINE"
git -C <repo> config user.email "<GitHub数字ID>+ISWINE@users.noreply.github.com"
```

数字 ID 用 `gh api user -q '.id'` 取。

## 技能真身/联接红线

C: 侧 `~/.agents/skills/<name>` 是 junction 不是真身；真身在 `D:\projects\zcode-skills\.agents\skills\<name>`。清理孤岛时先 `dir /AL` 双向核实（沿用 syscheck 红线）：删联接不删数据，D 侧真身别当孤儿删。
