# Windows Terminal 关闭命令行错误提示音

## 需求 / 症状

命令行里敲错命令（或不存在的命令）执行后，系统发出「叮」一声报错音。只想去掉声音，保留文字报错。

## 原理

shell 出错时向终端输出 BEL 控制字符（ASCII 7）。Windows Terminal 收到 BEL 后按 profile 的 `bellStyle` 决定反应（响声 / 闪窗 / 闪任务栏）。设为 `"none"` = 收到也忽略。响不响是终端说了算，所以对 cmd / PowerShell / Git Bash 所有 shell 一视同仁。

## 改法

settings.json 路径：

- Store 版：`C:\Users\<用户名>\AppData\Local\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json`
- 非 Store / 解包版：`%LOCALAPPDATA%\Microsoft\Windows Terminal\settings.json`

在 `profiles.defaults` 写入（对所有配置文件生效）：

```json
"profiles": {
    "defaults": {
        "bellStyle": "none"
    }
}
```

保存即生效（热加载），已开着的标签页也生效，无需重启。

GUI 等价路径：`Ctrl + ,` 打开设置 → 左栏「默认值 Defaults」→「高级 Advanced」→「铃声通知样式 Bell notification style」→ 取消勾选「可听 Audible」。

## 验证

1. 随便敲一个不存在的命令执行：只剩文字报错，无声。
2. 手改 JSON 的话先跑一次语法校验：`python -m json.tool` 或 PowerShell `ConvertFrom-Json`，防止写坏整个设置文件。

## 回滚 / 变体

- 恢复响声：`"audible"`
- 想要无声反馈：`"window"`（出错时窗口标题栏/任务栏闪烁）
- 系统级备选（连弹窗报错音一起去掉）：`Win + R` → `mmsys.cpl` →「声音」选项卡 → 程序事件里「默认响声 Default Beep」「关键性停止 Critical Stop」→ 声音改「(无)」。动的是全系统所有程序，非必要不用。

---

状态：已验证 2026-09-29，本机 Windows 10.0.26200 / Windows Terminal Store 版
