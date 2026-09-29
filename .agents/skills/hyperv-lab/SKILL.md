---
name: hyperv-lab
description: 在 Windows 专业版上零第三方依赖地部署一台可抛弃式 Linux 实验服务器（Hyper-V + Ubuntu 官方云金镜像 + cloud-init 静默部署 + 底片快照回滚 + 系统报告）。用户提到 装 Linux 环境/要台测试服务器/学习部署上线/WSL 替代/静默装机/金镜像/虚拟机实践环境/重装练习 时使用。内含已在本机踩平的全部坑（Hyper-V 参数名/PS5.1 stderr/国内镜像源）与整套可移植脚本。
---

# hyperv-lab：Windows 里的 Linux 实验服务器

目标：给学习"真实项目上线部署"的人一台**随开随用、随关随净、练废秒回滚**的 Linux 服务器，全部文件集中一个目录、不占 C 盘数据、绝不开机自启、零第三方虚拟化软件。

## 第 0 步：适用判断（红线）

1. Windows **Pro/Enterprise/Education** 才有 Hyper-V（`Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'` 看 EditionID）。Home 版不适用本技能，走 WSL2 调优路线（另行讨论）。
2. BIOS 虚拟化：`Get-CimInstance Win32_ComputerSystem` 的 `HypervisorPresent=True`（VBS/内核隔离开着就必然 True）即已就绪；若 False 且 CPU 支持虚拟化 → 进 BIOS 开 SVM/VT-x。
3. 目标网段 `192.168.100.0/24` 不能与宿主真实网卡冲突（脚本里有守卫，冲突就改 `config.ps1` 的 `$Subnet/$HostIP/$VmIP`）。
4. **不装任何第三方虚拟化软件**（VirtualBox/VMware 全家桶），只用 Windows 自带功能。
5. 提权脚本纯 ASCII、bat 必须 CRLF（PS 5.1 按 GBK 读无 BOM UTF-8 的中文 .ps1 会静默失效）——沿用 syscheck 红线。

## 心智模型

```
Windows 宿主
├─ Hyper-V（系统自带；VBS 本就加载 hypervisor，启用它不新增开机项）
│   └─ VM「lab」= 一台真·Linux 服务器（等价云 ECS）
│       ├─ 系统：Ubuntu 官方云金镜像 + cloud-init 首启自动配置
│       │        （固定 IP、建用户、装包、时区、镜像源、NTP——全程零交互）
│       ├─ 资源：2 vCPU / 内存 0.5-4G 气球动态 / 磁盘动态 VHDX 按需增长
│       ├─ 网络：内部 NAT 192.168.100.0/24（.1=宿主网关 .10=VM 固定 IP）
│       │        外网可出、外人/家庭局域网进不来（弱密码可接受）
│       └─ 底片：baseline-clean-* 离线快照，一条命令整厂回滚
└─ 互通：ssh 别名 / scp / Hyper-V 文件直推 / hosts 别名（Navicat 可填主机名 lab）
```

部署范式与云厂商同构：**金镜像（golden image）+ cloud-init + 任务链（RunOnce 自动续跑）+ 回执验收（VERIFIED/日志/系统报告）**。不跑系统安装器，首启 2~5 分钟出机器；重装=删盘重放 20 号脚本，约 2 分钟。

## 部署七步（首次约 30 分钟，下载占大头）

设 `<root>` 为实验根目录（示例 D:\lab）。

1. **体检**：第 0 步三项 + `Get-Volume` 确认 D 盘 ≥10G 空闲。
2. **落脚本**：把本技能 `scripts/` 全部文件复制到 `<root>`，`assets/seed/` 三个模板复制到 `<root>\seed\`。所有路径集中读 `<root>\config.ps1`（单一事实源，搬家/克隆只改它）。
3. **配种子**：
   - `ssh-keygen -t ed25519 -f <root>\ssh\lab_key -N '' -C lab-key`（目录先建）
   - Git Bash 里 `openssl passwd -6 '<你的密码>'` 出哈希
   - 把公钥与哈希填进 `seed\user-data`（替换 `<PUBKEY>` / `<SHA512-HASH>` 占位符），`seed\network-config` 的 macaddress 与 `config.ps1` 的 `$VmMac` 保持一致
   - `powershell -File <root>\build-seed.ps1` → 生成 `seed\cidata.iso`（IMAPI2 原生制盘，卷标必须 CIDATA）
4. **备金镜像**：下载 `noble-server-cloudimg-amd64.img`（qcow2，约 625M；清华源 `mirrors.tuna.tsinghua.edu.cn/ubuntu-cloud-images/noble/current/`，SHA256 对照同目录 SHA256SUMS）到 `<root>\images\`，再用便携 qemu-img 转 Hyper-V 盘：
   `qemu-img.exe convert -f qcow2 -O vpc -o subformat=dynamic <qcow2> <root>\images\lab-golden.vhd`
   （qemu-img Windows 便携版：cloudbase.it/qemu-img-windows/；**qemu 2.3 里 VHD 格式名是 vpc**）
5. **`10-enable-hyperv.bat`**：UAC → 启用 Hyper-V → 选 Y 设 RunOnce 自动续跑 → 重启（仅此一次）。
6. **`20-run.bat`**（重启登录后 RunOnce 自动弹，或手动双击）：建交换机/NAT/VM、金镜像转动态 VHDX、挂种子、开机、轮询 SSH，打出 **VERIFIED** 才算成。日志 `<root>\logs\20-create-vm.log`。
7. **`30-baseline.bat`**：收 guest+host 系统报告 → 干净关机 → 离线底片快照 `baseline-clean-<时间戳>` → 报告落 `<root>\reports\lab-report-<时间戳>.md`。

## 底片与回滚纪律（学习环境的核心价值）

- 做危险实验前：`lab.ps1 ck <名字>`；玩砸：`lab.ps1 restore baseline-clean-<时间戳>`。
- 底片=部署完未动手的原始状态；练习部署流程本身也可以整段重放（删 `vm\lab.vhdx` → 20 → 30）。
- 快照会占磁盘（增量），废弃的用 `lab.ps1 rmck <名字>` 清掉。

## 日常命令

```
lab.ps1 status / start / stop / ssh / ip / push <file> / report
lab.ps1 ck <名字> / lsck / restore <名字> / rmck <名字>
```

VM 控制台（极少需要）：`vmconnect . lab`。

## 坑清单（全部实踩，详见 references/lessons.md）

1. Hyper-V 模块参数名与记忆不符：`Set-VM` 用 `-MemoryMinimumBytes/-MemoryMaximumBytes`；`Set-VMNetworkAdapter` 固定 MAC 用 `-StaticMacAddress`（没有 -MacAddress）。**写 Hyper-V 脚本前先 `(Get-Command <cmdlet>).Parameters.Keys` 实测。**
2. PS 5.1 + `$ErrorActionPreference='Stop'` 会把原生命令任何 stderr 行（如 ssh 的 "Warning: Permanently added"）当致命错误 → 原生命令一律 `cmd /c "... 2>nul"` 隔离。
3. IMAPI2 制 ISO：`AddFile` 不吃路径字符串，要 `AddTree` 打包目录；卷标必须 `CIDATA`（NoCloud 靠卷标识别）。
4. 阿里云 ubuntu-releases 的 ISO 会 302 到连不通的下载节点；ISO 用华为云 `repo.huaweicloud.com/ubuntu-releases/`，云镜像用清华 TUNA。
5. VM 挂着的 ISO 被 vmms 锁文件——移动/删除种子目录前先 `Set-VMDvdDrive` 换路径或停机。
6. Hyper-V Administrators 组成员加入后要**注销重登**才生效（新进程不够，要新登录会话）。
7. 金镜像 Gen2/UEFI 可直接引导（secure boot 用 MicrosoftUEFICertificateAuthority 模板）；`Resize-VHD` 扩盘后首启 growpart 自动扩根分区。
8. 固定 IP 靠"两处 MAC 一致"：`config.ps1 $VmMac` ↔ `seed\network-config` 的 macaddress。

## 脚本清单（scripts/）

| 文件 | 阶段 | 作用 |
|---|---|---|
| `config.ps1` | 全程 | 单一事实源：路径/网段/MAC/名字 |
| `10-enable-hyperv.bat` | 部署① | 启用 Hyper-V + RunOnce 任务链 + 重启 |
| `20-run.bat` + `20-create-vm.ps1` | 部署② | 网络+VM+静默部署+SSH 回执验证 |
| `30-baseline.bat` + `30-baseline.ps1` | 部署③ | 系统报告+底片快照（产物在 reports/） |
| `lab.ps1` | 日常 | status/start/stop/ssh/push/report/ck/restore |
| `build-seed.ps1` | 种子 | seed 目录 → cidata.iso（改种子后重跑） |
| `guest-report.sh` | 客体 | VM 内只读系统报告（scp 到 ~/guest-report.sh） |
| `mysql-first-deploy.sh` | 验收 | 首次"上线"练习：部署 MySQL 供宿主 Navicat 连通 |

assets/seed/：user-data / network-config / meta-data 模板（占位符版）。

## 卸载（反悔出口）

管理员：`Disable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All` → 删 `<root>` → hosts 删 VM IP 行 → `ssh-keygen -R <VmIP>`。
