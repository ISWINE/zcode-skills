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
15. **WinSxS 里两个"假垃圾"（2026-09-29 实证）**：
    - `WinSxS\Temp\InFlight` + `PendingDeletes`（本机 219.5M）：**硬链接农场**。`fsutil hardlink list` 显示每个文件 3~4 条链接，真实负载同时在 `Windows\SystemApps\...` 和 `WinSxS\amd64_*` 里。**按文件大小枚举会严重虚报，删除释放约 0 字节**，且要抢 TrustedInstaller 所有权 → 纯风险零收益。判定：INFO，不列入可回收量。
    - `WinSxS\Backup`（本机 188.6M / 3143 文件）：**设计内的组件备份**（字体/manifest 备份，用于组件修复），抽样链接数为 1 即真占空间，但**必须存在**。判定：must-exist 守卫项，不是垃圾。
    - 推论：**预测"重启后能回收多少"时绝不能把 WinSxS 的 Temp/Backup 算进去**——本机因此把 +0.71G 误报成 +1.24G。DISM `analyzecomponentstore` 的「实际大小」才是权威口径（本机枚举 11.29GiB ≈ 权威 11.55GiB，口径基本吻合）。
16. **函数名撞内置别名会静默降级**：自定义删除函数取名 `Del` → PowerShell 里 `del` 是 `Remove-Item` 的内置别名，**别名优先级高于函数**，调用时参数全丢（无 `-Recurse`）→ 弹确认框 + 删除失败。用 `Remove-Target` 这类名字，并加 `-Confirm:$false`。
17. **Storage Sense 开启即触发首轮清扫**：`StoragePoliciesLastTrigger` 为空即说明**从未跑过**，一旦打开会自动清掉积累的临时区（本机一次放出 1.7G）。副作用：若同时打开 `08`（下载文件夹清理），超期会**永久删除** Downloads 里的用户文件——违反红线，必须保持 `08=0`（`256` 是它的天数阈值，本机 30）。回收站清理是 `32`/`128`（本机 30 天）。
18. **回收站 API 会撒谎**：`Clear-RecycleBin -Force` 返回 OK 却一个字节没删（目录里只剩孤儿 `$R` 内容文件、配对 `$I` 已丢 → Shell 报 "cannot find the file specified"）。**必须按终态 0 字节验收**，必要时 `Remove-Item -LiteralPath` 直删。
19. **"重启过了"要用日志证伪**：`LastBootUpTime` 会被快速启动干扰，别单信它。权威判据 = `Microsoft-Windows-Kernel-General` Event 12（OS 启动）/13（OS 关闭）+ `explorer` 启动时间 + **PFR 是否归零**（真重启必清）。本机两次遇到"用户说重启了"但 Event 12 没动。
20. **Edge 旧版残留谁在占用要分版本查**：`EdgeCore\153` 无人加载（可立即删），但 `EdgeWebView\Application\153` 被 **`SearchHost.exe`（Windows 搜索）** 加载 → 热删会坏搜索界面，必须重启。用 `Get-Process | %{ $_.Modules }` 按 `FileName -like '*EdgeCore\153*'` 做模块级检测，别只看目录。
21. **本机 CPU 频率字段是假的（2026-09-29 实测）**：`Win32_Processor.CurrentClockSpeed` 与 `\Processor Information(_Total)\Processor Frequency` **恒为标称 3000MHz**（无效字段），`% of Maximum Frequency` **恒为 100**。**判升频/降频只能用 `\Processor Information(_Total)\% Processor Performance` × 标称频率**。本机实测负载峰值 130.14% ≈ 3905MHz、全核稳态 117.6–118.1% ≈ 3530MHz——用假字段会得出"CPU 被锁死在 3000MHz"的错误结论。
22. **"无法归因启动慢"是本机结构性缺口**：`Microsoft-Windows-Diagnostics-Performance/Operational` 日志**根本不存在**（不是空）。`Get-WinEvent -ListLog` 匹配 0 条 → 没有官方启动降级归因、没有各阶段耗时、没有启动项耗时排名。要归因必须提权 `wevtutil sl Microsoft-Windows-Diagnostics-Performance/Operational /e:true` 或上 WPA/xperf。替代度量只能用 Kernel-General Event 12 → 6005 → explorer.StartTime 的差值。
23. **"读不到"不能写成"健康"**：非提权下 SMART 全断（`Get-StorageReliabilityCounter` 返回 $null、`MSStorageDriver_FailurePredict*` 不支持、`MSFT_StorageReliabilityCounter` 拒绝访问、无 smartctl），温度源（`MSAcpi_ThermalZoneTemperature`、`\Thermal Zone Information(*)\Temperature`）实例也不存在。**只能报"数据缺口，需提权"，不能报"健康"**——`HealthStatus=Healthy` 来自存储栈而非盘内 SMART。
24. **PS 5.1 四个静默坑（2026-09-29 实测）**：① **形参与局部变量只差大小写 = 同一个变量**（`[int]$Threads` 与 `$threads` 冲突 → 抛异常后整个采样循环静默失效）；② 本机 ExecutionPolicy 禁直接跑 .ps1，用 `[scriptblock]::Create((Get-Content -Raw $f))` 内存执行并对脚本块传参；③ `Get-Counter` 传多个计数器时**只要 1 个不存在就整条失败**，须先逐个校验路径；④ `ConvertFrom-Json` 得到的 `PSCustomObject` **不支持 `$obj['key']` 索引器**，要用 `$obj.key`。
25. **AC 最小处理器状态 80% 的溯源困境（本机未解）**：`powercfg /query` 明确报 AC=80%，但**遍历 `HKLM\SYSTEM\CurrentControlSet\Control\Power` 全树只有该设置的"定义键"，找不到任何方案下的 AC/DC 持久化值**，方案默认值与活动叠加(overlay)都没有该值 → 说明是**运行时被写入当前活动方案**的（最可能是 OEM 电源服务，但无直接证据）。**验证方法**：`powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMIN 5` + `/setactive` → 重启后若回到 80% 即为组件施加，保持 5% 则为一次性残留。**教训：powercfg 的"当前值"可能没有对应的注册表落盘位置，别硬找。**
26. **"日志不存在"往往是权限假象——必须用 `wevtutil gl` 复核（2026-09-29 踩实）**：非提权跑 `Get-WinEvent -ListLog` / `-LogName` / **连直接读 .evtx 文件（`-Path`）** 对 `Microsoft-Windows-Diagnostics-Performance/Operational` 全部返回空或抛"未经授权的操作"，我据此误判"日志不存在 → 启动慢结构性无法归因"，还把它当成"最该先做的事"。**真相：日志存在、已启用、340 条记录**，只是 ACL 只给 Administrators：
   ```powershell
   wevtutil gl "Microsoft-Windows-Diagnostics-Performance/Operational"   # 非提权可跑！
   #   enabled: true
   #   channelAccess: O:BAG:SYD:(D;;0xf0007;;;AN)(D;;0xf0007;;;BG)(A;;0xf0007;;;SY)(A;;0x7;;;BA)...
   #                  ↑ BA=Administrators 有 0x7；普通交互用户 SID 不在允许列表 → 读不到
   ```
   **规矩：任何"读不到数据"的结论，先排除权限原因（用 `wevtutil gl` 看 `channelAccess`），再下"结构性缺口"的判断。** 这类通行证还适用于 Security 日志等受保护通道。
27. **启动慢的归因要认 Event 100 的口径（本机实测）**：Windows 官方"全启动"= `BootTime`（本机 **36.4–75.5 s**），其中 `BootPostBootTime`（启动应用/服务后续工作）占 23.8–43.9 s 是大头，`BootKernelInitTime` 仅 53 ms。**"内核→explorer 13.5 s"只量到 shell 就绪，不能当启动耗时汇报。** 同一日志里 **Event 101=应用 / 102=驱动 / 103=服务 / 109=降级**；本机 59 条降级事件**全是 101**（102/103/109 = 0 条）→ 说明**旧驱动没造成启动问题**，锅全在应用层（头号 `MsMpEng.exe` 最大 61.5 s / 均 33 s，第二梯队华为 PCManager 套件）。
28. **文件关联的 UserChoice 是"可移除的 DENY ACE"，不是内核封锁——实测能删（2026-09-29 跑通）**：`FileExts\<ext>\UserChoice` 非提权打开会抛"不允许所请求的注册表访问权"，`Remove-Item` 报**误导性**的"该子项不存在，因此无法删除子项目录树"（加不加 `-Recurse` 都一样）。**真因是 DACL 里一条 DENY ACE**：提权后读 SDDL 可见
    `D:AI(D;;DC;;;<user SID>)(A;OICIID;KA;;;<user SID>)…` —— 就是 `(D;;DC;;;<用户>)`（Deny DeleteChild）挡住的，其余本已 Allow FullControl。
    **Win11 下每个扩展名有 2 个键**：`UserChoice`（值 ProgId+Hash）与**兄弟键** `UserChoiceLatest`（值 Hash + 子键 `ProgId`）。
    **可复现做法（提权）**：`SeTakeOwnership/SeRestore/SeBackup` 三特权 → 以 `TakeOwnership` 权限 `OpenSubKey` → `GetAccessControl(AccessControlSections::None)` + `SetOwner` → 以 `ChangePermissions` 权限重开 → 删掉全部 Deny 规则 + 补 FullControl Allow → `DeleteSubKeyTree`。本机 **24 键 removed=24/failed=0**。
    **重要反直觉点**：`UCPD.sys`（用户选择保护驱动，StartMode=System、Running）**并没有拦截**——它施加的是这个 DACL，而非阻断写入系统调用；**删掉键后 UCPD 也不会重建**。删除后 `OpenWithList`/`OpenWithProgids` 保留，"打开方式"列表仍可用。
    **复核关联是否真失效必须用合并视图 `Registry::HKEY_CLASSES_ROOT\<ProgId>`**（只看 `HKLM\SOFTWARE\Classes` 会把 AppX 关联全误判为死链），并拿 `.txt/.png` 当对照组。
    **ProgId/键名比对必须看长度与首字符码**：本机 Bambu Studio 注册的 ProgId 真名是 ` Bambu.Studio.1`（**带前导空格**，长度 15、首字符码 32），带空格可解析、不带空格返回 False —— 我肉眼扫空格时得出过相反的（错误）结论。`"$name".Length` + `[int][char]$name[0]` 一查就清楚。
    **元教训**：我先前凭"UCPD 会拦"的机制推测就下了"风险大于收益、建议不做"的结论 —— **"做不到"的判断也要先实测再下**。

29. **es.exe 不是独立程序（2026-10-07 实测）**：es.exe 只是 everything.exe 的 IPC 遥控器，引擎没跑就是一句 `Error 8: Everything IPC not found`，什么都查不了。所谓"用 es 加速"的完整闭环=拉起 everything.exe → es 查询 → 用完 `-exit` 复原。新机器自补给要下载**便携整包**（含双 exe），只下 es.exe 没有意义。
30. **提权 Everything 收不回来（2026-10-07 实测）**：便携 everything.exe 读 NTFS MFT 要管理员，本机启动时自申请提权（UAC 被点掉后成为提权实例）。后果链：非提权 es.exe 的 `-exit` 消息被 UIPI 静默拦截且 **es.exe 调用本身挂死**（不是报错返回）；非提权 taskkill/Stop-Process 拒绝访问；Get-Process 看不到其 Path。教训：**任何"发消息控制可能提权的进程"的收尾步骤必须限时兜底**（Start-Job + Wait-Job -Timeout），并如实报告残留，绝不能裸调。杀提权实例只能再提权一次（UAC taskkill）。
31. **PS 函数的管道污染（2026-10-07 实测）**：函数里 `Write-Output` 状态行 + `return $rows`，调用方 `$x = Func` 拿到的是 `[状态行, rows]` 混合数组——下游 Group/Sort/Measure 全炸（Null 调用、0.00 GB 假行）。**函数要既回报状态又返回数据时，状态一律 `Write-Host`（走宿主流，不进管道）**。另：EFU 是 UTF-8，PS5.1 的 `Import-Csv` 不加 `-Encoding UTF8` 会把中文路径读成乱码。

## 本机档案（易变，以清单文件为准）

- 联接农场全表：`E:\笔记\笔记\系统软件清单.md` §9（12 条）
- 软件分类清单：同文件 §1-11
- 用户决定：BitLocker 不开（性能优先）、dev-sidecar 代理残留不处理、KimiData 保留
- 休眠地雷：WinINET ProxyServer 残留 dev-sidecar 配置（ProxyEnable=0 无害；浏览器集体断网先查这里）
- 提权惯例：日志落 `Temp\`，done 标记轮询，ASCII 脚本
