# 踩坑档案（lessons learned）

本文件是 syscheck 技能的实战教训库，2026-09-28 全流程验证。改 SKILL.md 前先读这里。

## 工具链陷阱

1. **MSYS 路径转换吞参数**：Git Bash 里 `robocopy ... /E /COPYALL` 的开关被转成路径，robocopy 打印用法并 exit 16。解法：.ps1 文件承载，或 `MSYS_NO_PATHCONV=1`。
2. **PS 5.1 GBK 读 UTF-8**：无 BOM 的含中文 .ps1 被当 ANSI 读，个别行静默失效——现象是"脚本跑完了但那几步没执行、日志里也找不到"。sysdeep 脚本 B1/B2 失败、纯 ASCII 重写一遍过的实证。**提权脚本只写 ASCII**。
3. **cmd 批处理 + LF 行尾**：Write 工具写出 LF，cmd 解析碎成乱命令。别用 .cmd，用 .ps1。
4. **robocopy 退出码**：0-7 都是成功（1=有复制），≥8 才是失败。bash 会把非零当错误，别被 exit=1 吓到。
5. **注册表 InstallLocation 带引号**（如 `loc="C:\Program Files\pot"`）：Test-Path 把引号算进路径，误报 MISSING。复核用 `ls <路径>`。差点误杀 pot。
6. **Git Bash du 极慢**：全盘/全 profile du 会卡死会话。只对候选目录并行算：`xargs -P 12`，或先读清单文件复用旧数据。
7. **PowerShell `Start-Process -Verb RunAs`**：弹 UAC，加 `-Wait` 可同步；长任务（DISM 10-20 分钟）要落日志文件+done 标记轮询，别死等标准输出。

## 判定方法论教训

8. **插件不进卸载表**：IDEA 插件（codegeex/qoder/TranslationPlugin）在 `Roaming\JetBrains\*\plugins`，不看这步会把 951M/286M 活数据当孤岛删掉。Yii.Guxing=TranslationPlugin 作者目录，身份全靠 ls 内容识别。
9. **联接是双向雷**：C 侧 `ls` 一切正常（联接透明），删 D:\cshift 整体=毁 npm/VSCode/BambuStudio/Fusion/gradle 等。判孤岛必须双向：C 侧 `dir /AL` 无联接指向 + D 侧无程序引用。删除前逐目录查，不能只查顶层（联接可以埋在深层）。
10. **迁移错峰**：只迁冷数据（mtime>2 周）；热数据迁移技术可行但单盘 NVMe 下零收益。会话运行中不可迁 `~/.zcode`（自拆脚下）。
11. **畸形排除项**：Defender ExclusionPath 里 8 个路径挤成一个字符串（AutoClaw 写坏），按单路径删永远删不掉。解法：读全量→关键词过滤→`Set-MpPreference -ExclusionPath` 重设。验证要用提权回读，非提权读不到。
12. **DISM error 5**：StartComponentCleanup 在有待重启（PFR）时 91% 处拒绝访问。先重启再跑，一遍过。
13. **electron 应用指纹**：`*-updater`=更新器缓存（分"在装清内容/已卸整删"两态）、`com.xxx.desktop`=Tauri、`EBWebView`=WebView2 壳、作者名目录=应用数据。
14. **商店版应用是平行世界**：MSIX 装的在 Get-AppxPackage，不在卸载表（Claude/Codex 桌面版当初就是这么漏的）；还能注册开机自启服务（CodexSandboxService），npm 卸载不清它。

## 本机档案（易变，以清单文件为准）

- 联接农场全表：`E:\笔记\笔记\系统软件清单.md` §9（12 条）
- 软件分类清单：同文件 §1-11
- 用户决定：BitLocker 不开（性能优先）、dev-sidecar 代理残留不处理、KimiData 保留
- 休眠地雷：WinINET ProxyServer 残留 dev-sidecar 配置（ProxyEnable=0 无害；浏览器集体断网先查这里）
- 提权惯例：日志落 `Temp\`，done 标记轮询，ASCII 脚本
