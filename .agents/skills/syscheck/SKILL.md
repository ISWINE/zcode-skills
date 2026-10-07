---
name: syscheck
description: Windows 系统深度体检与清理（deep system check & cleanup），可移植到任何电脑。用户提到 系统体检/清理C盘/清理D盘/孤岛扫描/反推理垃圾/系统垃圾/磁盘清理/迁移到D盘/环境变量检查/组策略检查/软件清单/体检报告/大致报告/精细报告，或想找出无用软件残留时使用——即使只是说"C盘又满了"也应触发。两阶段出报告：INIT 初始化 → 阶段A 粗扫（Everything 秒级加速）出大致报告 → 用户圈定范围 → 阶段B 精扫出精细报告。含防误杀红线（联接农场）。
---

# syscheck：Windows 深度体检与清理（v2 可移植 + 两阶段报告）

方法论：先建"已安装白名单"，再反向判定一切无主项为孤岛。流程固定为 **INIT 初始化 → 阶段A 粗扫出大致报告（分钟级）→ 用户拍板圈范围 → 阶段B 精扫出精细报告**。红线规则优先于一切效率考虑。

## 第 0 步：INIT 环境初始化（每次会话第一步，新电脑必跑）

1. 跑 `scripts/init.ps1`（非提权 ~10 秒），拿机器画像：OS/硬件/卷与文件系统/是否提权/PS 版本/工具探测（es.exe、Everything、winget）。
2. **harness 自识别 = 看自己**：你跑在什么环境里自己的提示词和工具集就是证据（ZCode/Claude Code/Codex/Gemini CLI/纯人工终端），直接写进报告头，不做任何脚本探测。
3. **家机/陌生机判定**：「本机专属档案」节列出的真相源文件存在 → 家机模式（复用清单快照、本机专属红线生效）；不存在 → 陌生机模式（无既有真相可复用，白名单从零自建，红线只取通用集，报告头标注陌生机）。
4. 报告与工件输出目录：`<当前工作区>\syscheck-out\<yyyyMMdd-HHmm>\`，不做任何盘符假设。

## 阶段A：粗扫 → 大致报告（目标：分钟级，先广后深）

1. `scripts/diag.ps1`（非提权 ~30 秒）：健康红旗——盘/TRIM/转储/待重启/Defender/防火墙/自启未跑服务/更新缓存/Installer 体积/监听端口/WinINET 代理。
2. `scripts/esquick.ps1`：Everything 全卷枚举，六类快扫——tmp/dmp 垃圾（分盘汇总）、>50mb 大日志、>500mb 大文件 top30、>10mb 转储、msi/iso 安装包堆积、node_modules 与 .venv 农场计数。脚本自动拉起 everything.exe 引擎、跑完尝试 `-exit` 复原（尊重"平时不驻留"的机器）。EFU 明细落 `TEMP\syscheck-es-*`，供精扫直接复用不再重查。
3. **es.exe 自补给（陌生机器默认动作）**：es.exe 只是 everything.exe 的 IPC 遥控器，**单独存在毫无用处**（实测 Error 8: Everything IPC not found），两者必须成对。机器上没有（init.ps1 的 ES_EXE 为空、且用户没说有）→ 下载 Everything 官方便携 zip 到 `<工作区>\syscheck-out\tools\everything\` 解压自用（免安装不进系统，es.exe+everything.exe 都在里面，用 `-EsPath` 指过去；用完连同索引库一起删，不留痕）。下载源 `https://www.voidtools.com/downloads/`（Everything 便携 x64 zip），直连失败再问用户要镜像，别静默放弃。注意：便携引擎读 NTFS MFT 要管理员权限，可能自弹一次 UAC；提权实例非提权 es 关不掉（UIPI），esquick 会如实报告残留。
4. 下载也失败/用户拒绝：跳过 es 步骤，大致报告标注「文件面缺口，需阶段B 补全」。
5. **大致报告**（一页，到此停下等用户拍板）：报告头（日期/机器画像摘要/harness/家机or陌生机）+ 健康红旗 + 回收潜力**区间**（es 数据是上界：含排除区外的误报、未做白名单反证，不许写成承诺值）+ 建议深挖项清单（每项标预计耗时/风险/收益）。

## 阶段B：精扫 → 精细报告（用户圈定范围后才跑）

### B1 地面真相采集（白名单）
`scripts/groundtruth.ps1`（非提权 ~30 秒）六路证据：卸载注册表（HKLM×2+HKCU）、Appx 包、三方服务路径、Run/RunOnce 自启动、计划任务、运行中进程路径。**再做四项补充**：JetBrains 插件目录（插件不进注册表！）、开始菜单 .lnk、`winget upgrade`（只报告）、非系统盘 Program Files 与用户级 Programs 目录（electron 应用常装侧位 profile）。

### B2 孤岛反推理
对 `~/`（含点开头目录）、`AppData\Local`、`AppData\Roaming`、数据盘逐项与白名单比对。判定孤岛需**四重证据全空**：无卸载表项、无 Appx、无插件引用、无快捷方式/服务/进程引用。体积并行算：`printf '%s\n' <dirs> | xargs -P 12 -I{} du -sh {}`（有 Everything 时可先用 es 反查引用再算体积，省遍历）。
身份不明目录先看内容再判（实战指纹）：`com.xxx.desktop`=Tauri 应用数据；`EBWebView`=WebView2 缓存壳；`*-updater`=electron 更新器缓存（在装→清内容；已卸→整删）；作者名目录=应用数据不是垃圾；InstallLocation 带引号会让 Test-Path 误报 MISSING，用 ls 复核。

### B3 缓存分类清理
| 类别 | 判定 | 处置 |
|---|---|---|
| 已卸载应用残留 | 四重证据全空 | 整删 |
| 在装应用 updater 缓存 | `*-updater` 里的 installer.exe/pending | 清内容留目录 |
| 可再生开发缓存 | go-build / npm-cache / uv\cache / node-gyp / electron | 删 |
| 系统管理 | Microsoft / Packages / Comms / D3DSCache | 不动 |
| 用户数据 | Documents / Downloads / 项目目录 | 永不动 |

### B4 系统底层（需提权，走 UAC 一次打包）
配方（16G 内存基准）：pagefile 固定 `2048 8192`、`powercfg /h /type reduced`、DISM `/startcomponentcleanup`（报错 5=有待重启，先重启再跑，勿用 /ResetBase）、卷影 >10G 才干预、防火墙三配置文件启用+按机器实际补入站白名单。提权执行模式：`Start-Process powershell -Verb RunAs -Wait -ArgumentList '-File','<ascii.ps1>'`，结果一律落日志文件再回读验证，**声明成功前必须有回执**。

### B5 规则层审计
组策略（`HKLM/HKCU\SOFTWARE\Policies` 树 + `gpresult /r`）、根证书 MITM 过滤（非微软 CA 逐个看 Subject）、WinINET 代理（`ProxyEnable=0` 即无害）、hosts、Defender 排除项死链（关键词过滤重设，畸形合并条目按整条删）、监听端口（排除 127/::1）、数据库绑定应 127.0.0.1、CDM 推广开关、激活/UAC/Storage Sense（`08` 必须保持 0，否则会永久删 Downloads 用户文件）。

### es.exe 补充审查（精扫阶段的四个用法）
- 孤岛候选名全盘反查：`es -n 100 -search "<目录名>"`，看是否有别处引用/快捷方式指向。
- 删除前文件清单快照：`-export-efu` 留档，事后对账。
- 删除后残留复核：同查询再跑一遍对比计数。
- 迁移前源目录清单：与 migrate.ps1 的核对步骤互补。

## es.exe 加速原理与陷阱（为什么快/怎么会错）
- **为什么快**：Everything 常驻读 NTFS MFT/USN 日志，索引内全卷枚举是秒级；递归 Get-ChildItem/du 是真遍历，小时级且曾卡死会话。粗扫一切"按文件名/大小/扩展名"的查询都应走 es，体积精确值与删除仍走 PowerShell。
- **陷阱**：多词查询必须 `-search` 传（位置参数会被搅碎）；`!path:` 排除不可靠→排除在 PowerShell 层做；默认只回 64 条，必须 `-n` 拉大、结果**绝不 head 截断**（会静默漏文件）；EFU 行 attribute 带 0x10 位是目录；es.exe 报 Error 8=Everything 没跑（esquick.ps1 已自动处理）。
- **覆盖缺口**：只索引 NTFS 卷，FAT/exFAT/网络卷不在内——粗扫报告必须标注哪些卷没被覆盖。

## 通用红线（任何机器，任何 harness）
1. **删除任何目录前先查联接**：`cmd //c dir /AL <目录>`。联接可埋在深层，逐目录查不能只查顶层；删联接侧=毁真身数据。
2. **永不触碰**：agent 自身运行时与记忆目录、`AppData\Local\Microsoft`、`AppData\Local\Packages`、Temp 内 24 小时新文件、用户 Documents/Downloads/项目目录。
3. **提权脚本必须纯 ASCII**（PS 5.1 按 GBK 读无 BOM UTF-8，中文行静默失效）；不用 .cmd（LF 行尾会碎）。
4. **Git Bash 吞 robocopy 开关**（MSYS 路径转换）：robocopy 一律走 .ps1 文件或 `MSYS_NO_PATHCONV=1`。
5. **声明成功前必须有回执**：日志落盘+回读验证，别信返回码单独作证。
6. 陌生机器的"读不到"先排除权限（`wevtutil gl` 看 channelAccess）再下"结构性缺口"结论；非提权 SMART 全断，只能报"数据缺口"，不能报"健康"。

## 本机专属档案（仅家机模式生效；陌生机以 init.ps1 实测为准）
- harness：ZCode。es.exe=`E:\软件\Everything-1.4.1.1032.x64\es.exe`（便携版，Everything 平时不驻留，用完 `-exit` 复原；脚本用 `E:\*\Everything*\es.exe` 通配定位以保持 ASCII）。
- 本机提权怪癖（2026-10-07 实测）：从这里拉起 everything.exe 会自申请管理员（UAC 点一次），提权后非提权 es.exe 的 `-exit` 被 UIPI 拦死（会挂）→ esquick 收尾已改为限时 job + Stop-Process 兜底 + 如实报告残留；真杀提权实例需再走一次提权 taskkill。
- 真相源（家机判定依据）：`E:\笔记\笔记\系统软件清单.md` §9 联接表 / §12-13 体检记录。联接农场真身 `D:\cshift`（.gradle/.m2/.cargo/.rustup/.android/Roaming\npm 等 12 条）。
- 专属红线：`~/.zcode`、`D:\cshift` 整体、`KimiData`、PCManger/华为目录、`Documents\dsh`。
- 用户在案决定：BitLocker 不开（性能优先）；dev-sidecar 休眠代理残留不处理；商店版预装应用不主动卸。
- 完成后把变更写回清单文件并更新文首日期；重大陷阱写记忆，明细写清单，防两处漂移。

## 迁移配方（C→D 联接搬迁）
只迁冷数据（mtime>2 周未动），热数据不迁。`scripts/migrate.ps1 -src <绝对路径> [-dst <目标>]`：目标缺省自动选**容量最大的非系统 NTFS 卷** `\cshift\Users\<用户>\<name>`（陌生机器无 D 盘假设）。流程：robocopy `/E /COPY:DAT /DCOPY:DAT /XJ` → 文件数核对 → 删源 → 建联接 → 通透抽检。

## 产出规范
- **大致报告**（阶段A末）与**精细报告**（阶段B末）各一份，落输出目录。精细报告：释放量表（按项）+ 误杀救回项（体现反推理价值）+ 遗留决定项（用户拍板）+ 磁盘前后对比；家机模式同步回写清单文件 §9/§12-13。
- 两份报告头部固定带：日期、机器画像摘要（init.ps1 [7] 段）、harness、家机/陌生机、es 覆盖的卷。
- 深挖细节与 28 条实战教训见 `references/lessons.md`（改本文件前先读它）。

## 移植到其他电脑
1. 整仓克隆 `zcode-skills` 到目标机任意目录 → 技能随 `.agents/skills/` 被项目级发现；或单拷 `syscheck/` 文件夹进目标 harness 的技能目录（ZCode 用户级=`~/.agents/skills/`）。
2. 首次调用先跑 INIT：init.ps1 全部路径从环境变量推导（无 C:\Users\12696/D:\cshift 假设），harness 由 agent 自报+进程链复核。
3. 缺什么就降级什么：无 es.exe → 粗扫文件面标注缺口；无 winget → 跳过该补充项；非提权 → 只出诊断面，提权项列成待办等用户开 UAC。
