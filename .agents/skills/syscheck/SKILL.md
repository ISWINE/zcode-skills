---
name: syscheck
description: Windows 系统深度体检与清理。用户提到 系统体检/清理C盘/清理D盘/孤岛扫描/反推理垃圾/系统垃圾/磁盘清理/迁移到D盘/环境变量检查/组策略检查/软件清单，或想找出无用软件残留时使用——即使只是说"C盘又满了"也应触发。v1 方法论原样 + es.exe 加速（写死家机路径，查不到=新机器=自动下载 Everything 便携版）。内含防误杀红线（联接农场）。
---

# syscheck：Windows 深度体检与清理（v1 + es.exe 加速）

本技能封装一套已在 2026-09-28 全流程验证过的反推理方法论：先建"已安装白名单"，再反向判定一切无主项为孤岛。目标机器是高定制环境（联接农场、D 盘搬迁），**红线规则优先于一切效率考虑**。

## es.exe 就位（一切之前；写死，查不到=新机器）

- 写死 `E:\*\Everything*\es.exe`，查得到直接用；查不到 → 肯定是新机器：不问，直接下载 Everything 官方便携 zip（`https://www.voidtools.com/downloads/`，x64）到 `<当前工作区>\syscheck-out\tools\everything\` 解压，es.exe+everything.exe 必须成对（es 只是 IPC 遥控器，引擎没跑就是 Error 8），esquick 用 `-EsPath` 指过去，用完连同索引库删净不留痕。直连失败换镜像再试；仍失败才降级 PowerShell 慢遍历，报告标注文件面缺口。
- 新机器同样意味着 `E:\笔记\笔记\系统软件清单.md` 不存在：清单快照不复用、结果不回写，联接/敏感目录拓扑扫描中自己从头摸，只信当场实测。
- 便携引擎读 NTFS MFT 可能自弹一次 UAC；提权实例非提权 es 关不掉（UIPI），esquick 收尾限时兜底并如实报告。

## 第 0 步：红线（动手前必读）

1. **删除任何目录前先查联接**：`cmd //c dir /AL <目录>`。本机 C:\Users\12696 下大量目录是 JUNCTION，真身在 D:\cshift（.gradle/.m2/.cargo/.rustup/.android/.codegeex/.qoder-cn/Roaming\npm/Roaming\Code/Roaming\BambuStudio/Local+Roaming\Autodesk 等）。删 C 侧联接 = 毁数据。联接农场全表以 `E:\笔记\笔记\系统软件清单.md` 第 9 节为唯一真相源。
2. **永不触碰**：`~/.zcode`（运行时+记忆）、`AppData\Local\Microsoft`、`AppData\Local\Packages`（Appx 数据）、`PCManger`/华为目录、`KimiData`（用户明示保留）、`D:\cshift` 整体、`Local\Temp` 内 24 小时的新文件。
3. **提权脚本必须纯 ASCII**：PS 5.1 按 GBK 读无 BOM 的 UTF-8 .ps1，中文行会静默失效（B1/B2 神秘失败的真实原因）。cmd 批处理用 LF 行尾会碎，别用 .cmd。
4. **Git Bash 会吞 robocopy 的 /E /COPYALL 开关**（MSYS 路径转换）。robocopy 一律走 .ps1 文件或 `MSYS_NO_PATHCONV=1`。
5. **用户决定在案**：BitLocker 不开（性能优先）；dev-sidecar 的休眠代理残留不处理；商店版预装应用不主动卸。
6. **es 加速，别裸遍历**：优先复用 `E:\笔记\笔记\系统软件清单.md` 的现状快照，只对疑点增量扫描；一切按文件名/大小/扩展名的查询走 es.exe（MFT 索引，秒级），别上来就 du 全盘（Git Bash du 极慢，曾卡死）。体积精确值与删除仍走 PowerShell。
7. 完成后把变更写回清单文件并更新文首日期；重大陷阱写记忆，明细写清单，防两处漂移。

## Phase 1：地面真相采集（白名单）

先跑 `scripts/esquick.ps1`（Everything 六类快扫：tmp/dmp 垃圾分盘汇总、>50mb 大日志、>500mb 大文件 top30、>10mb 转储、msi/iso 安装包堆积、node_modules 与 .venv 农场计数；自动拉起 everything.exe、跑完 `-exit` 复原，EFU 明细落 `TEMP\syscheck-es-*` 供后续复用）。

运行 `scripts/groundtruth.ps1`（非提权，~30 秒），采集六路证据：
卸载注册表（HKLM×2 + HKCU）、Appx 包、三方服务路径、Run/RunOnce 自启动、计划任务、运行中进程路径。
**再做四项补充**：IDEA/DataGrip 插件目录（`Roaming\JetBrains\*\plugins`，插件不进注册表！CodeGeeX/Qoder/TranslationPlugin 的配置目录全靠这步救回）、开始菜单 .lnk 扫描、`winget upgrade`（过期软件只报告）、D 盘 `D:\Program Files` 与 `D:\Users\12696\AppData\Local\Programs`（electron 应用常装 D 侧 profile）。

## Phase 2：孤岛反推理

对 `~/`（含点开头目录）、`AppData\Local`、`AppData\Roaming`、`D:\` 逐项与白名单比对。判定孤岛需**四重证据全空**：无卸载表项、无 Appx、无插件引用、无快捷方式/服务/进程引用。有 Everything 时先 `es -n 100 -search "<目录名>"` 全盘反查引用再算体积，省遍历；体积并行算：`printf '%s\n' <dirs> | xargs -P 12 -I{} du -sh {}`。

身份不明目录先看内容再判（本机实战指纹）：
- `com.xxx.desktop` = Tauri 应用数据；`EBWebView` = WebView2 缓存壳
- `*-updater` = electron 更新器缓存（应用在装→只清内容；应用已卸→整删）
- 作者名目录（如 `hiroi-sora`=pot 作者）是应用数据，不是垃圾
- 路径里带引号的注册表 InstallLocation 会让 Test-Path 误报 MISSING，用 ls 复核

## Phase 3：缓存分类清理

| 类别 | 判定 | 处置 |
|---|---|---|
| 已卸载应用残留 | 四重证据全空 | 整删 |
| 在装应用 updater 缓存 | `*-updater` 里的 installer.exe/pending | 清内容留目录 |
| 可再生开发缓存 | go-build / npm-cache / uv\cache / node-gyp / electron | 删 |
| 系统管理 | Microsoft / Packages / Comms / D3DSCache | 不动 |
| 用户数据 | Documents / Downloads / 项目目录 | 永不动 |

## Phase 4：系统底层（需提权，走 UAC 一次打包）

配方（16G 内存基准）：pagefile 固定 `2048 8192`、`powercfg /h /type reduced`、DISM `/startcomponentcleanup`（**报错 5 = 有待重启，先重启再跑**，勿用 /ResetBase）、卷影 >10G 才干预、防火墙三配置文件启用+给 LocalSend/dev-sidecar/华为服务补入站白名单。诊断脚本 `scripts/diag.ps1` 非提权可先跑（SSD/TRIM/转储/PFR/Defender/监听端口/更新缓存/Installer 体积）。
提权执行模式：`Start-Process powershell -Verb RunAs -Wait -ArgumentList '-File','<ascii.ps1>'`，结果一律落日志文件再回读验证，**声明成功前必须有回执**。

## Phase 5：规则层审计

组策略（`HKLM/HKCU\SOFTWARE\Policies` 树 + `gpresult /r`，Edge/Copilot 禁用是反广告轮次故意设的）、根证书 MITM 过滤（非微软 CA 逐个看 Subject）、WinINET 代理（`ProxyEnable`+`ProxyServer`——dev-sidecar 残留在档，ProxyEnable=0 即无害）、hosts、Defender 排除项死链（按关键词过滤重设，畸形合并条目按整条删）、监听端口（`Get-NetTCPConnection -State Listen` 排除 127/::1）、MySQL 绑定（my.ini bind-address 应为 127.0.0.1）、CDM 推广开关、激活/UAC/Storage Sense。

## es.exe 陷阱与补充用法

- 陷阱：多词查询必须 `-search` 传（位置参数会被搅碎）；`!path:` 排除不可靠→排除在 PowerShell 层做；默认只回 64 条，必须 `-n` 拉大、结果**绝不 head 截断**；EFU 行 attribute 带 0x10 位是目录；Error 8=引擎没跑（esquick 已处理）；只索引 NTFS 卷，FAT/exFAT/网络卷不在内，报告标注未覆盖卷。
- 补充用法：孤岛候选名全盘反查；删除前 `-export-efu` 留档对账；删除后同查询复核计数；迁移前源目录清单。

## 迁移配方（C→D 联接搬迁）

只迁冷数据（mtime 排序，>2 周未动），热数据（当天有写入）不迁。单盘 NVMe 分区场景迁移无性能损益，纯属搬占用。用 `scripts/migrate.ps1 -src <绝对路径>`：robocopy `/E /COPY:DAT /DCOPY:DAT /XJ` → 文件数核对 → 删源 → New-Item Junction → 通透抽检。目标统一放 `D:\cshift\Users\12696\<name>` 维持农场结构。

## 产出规范

最终报告：释放量表（按项）+ 误杀救回项（体现反推理价值）+ 遗留决定项（用户拍板）+ 磁盘前后对比。同步更新 `E:\笔记\笔记\系统软件清单.md` §9（联接表）/§12-13（体检记录）。深挖细节见 `references/lessons.md`。
