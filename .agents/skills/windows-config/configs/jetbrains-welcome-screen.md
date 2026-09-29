# JetBrains IDE 去除启动欢迎页（含 DataGrip 2026.2.5 本机配置）

## 需求 / 症状

每次启动 IDE 都弹「欢迎使用 XX」，且它出现在**项目窗口内部**（窗口标题形如 `项目名 – 欢迎使用 DataGrip`）。项目其实已正常打开——欢迎页只是压在上面的 tab（non-modal welcome screen）。快捷方式带项目路径、Reopen projects on startup 等**老办法全部无效**。

## 原理

2025.3+ / 2026.x 新 UI 的 advanced setting `welcome.screen.non.modal.enabled` 默认 `true`：welcome 以 tab 塞进项目 → 每次都见。设 `false` 退回经典独立欢迎窗 → 只在"没有最近项目可恢复"时才出现，有项目时直接进项目。key 命名规则：界面里的 `advanced.setting.FOO` → advancedSettings.xml 中 `<entry key="FOO" />`。

## 改法

1. **完全退出 IDE**（`taskkill /IM datagrip64.exe /F` 或正常关窗；不先杀进程，改动会被退出时回写覆盖）
2. 编辑 `%APPDATA%\JetBrains\<产品><版本>\options\advancedSettings.xml`
   本机 DataGrip 例：`C:\Users\<用户名>\AppData\Roaming\JetBrains\DataGrip2026.2\options\advancedSettings.xml`
3. `<map>` 里加一行：

```xml
<entry key="welcome.screen.non.modal.enabled" value="false" />
```

GUI 等价：设置 → Appearance & Behavior → 高级设置（Advanced Settings）→ 取消「以非模态模式显示"欢迎"屏幕」。

## 验证

启动 IDE，窗口标题不再含「欢迎使用 XX」。

## 回滚 / 变体

- 恢复：高级设置勾回「以非模态模式显示"欢迎"屏幕」
- 适用全家桶（IDEA / PyCharm / GoLand / WebStorm / CLion…），同一开关只换目录 `IntelliJIdea2026.2` / `PyCharm2026.2` …
- 2024.x 及更早无 non-modal 模式，用经典方案：勾 Reopen projects on startup + 关窗时停留在项目内 + 保底快捷方式目标末尾加项目路径（任务栏固定图标/公共开始菜单不带参数，从这些入口启动照样弹）
- 深挖（中文界面找设置项 id、老版本细节、JetBrains 通用排查套路）：笔记 `E:\笔记\笔记\JetBrains IDE 去除启动欢迎页.md`

## 本机 DataGrip 2026.2.5 事实档案

- 安装位置 `D:\Program Files\JetBrains\DataGrip 2026.2.5`；**注册表 InstallLocation 少写 `.5`，别信，以实际目录为准**
- 项目 `C:\Users\<用户名>\DataGripProjects\default`，已连 localhost 数据源（test 库）
- 桌面 + 用户开始菜单有带项目路径的 DataGrip.lnk
- 欢迎页已根治（2026-09-23 验证）

---

状态：已验证 2026-09-23，本机 DataGrip 2026.2.5（新 UI，写法适用 2025.3+ 全家桶）
