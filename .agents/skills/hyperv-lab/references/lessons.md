# hyperv-lab 实踩坑与经验（2026-09-29 全流程验证）

按"炸过/绕过"的程度排序，给未来排障用。

## 1. Hyper-V PowerShell 参数名不信记忆（对象属性名也不信）

- `Set-VM`：内存参数是 `-MemoryMinimumBytes / -MemoryMaximumBytes / -MemoryStartupBytes`（不是 -MinimumMemory/-MaximumMemory，那是 Set-VMMemory 的 -MinimumBytes 系列的近亲，极易混）。
- `Set-VMNetworkAdapter`：固定 MAC 是 `-StaticMacAddress`（没有 -MacAddress 参数；`-MacAddressSpoofing` 是另一回事）。
- `Get-VMMemory` 返回**对象**的属性名是 `Minimum / Startup / Maximum`（原始字节，不带 Bytes 后缀）——只有 Set 的**参数**带 Bytes。同名不同缀，炸过一次报告里内存全显 0。
- 验证命令：`(Get-Command Set-VM).Parameters.Keys` 查参数；对象属性翻模块自带格式定义 `C:\Windows\System32\WindowsPowerShell\v1.0\Modules\Hyper-V\2.0.0.0\Hyper-V.Format.ps1xml`（无需任何权限）。

## 2. PS 5.1 原生命令 stderr 致命化

- `$ErrorActionPreference='Stop'` 时，原生命令（ssh/qemu 等）往 stderr 写任何一行（包括无害的 "Warning: Permanently added ..."）都会抛 terminating error，跳进 catch。
- 解法：`cmd /c "ssh ... 2>nul"` 把 stderr 关在 cmd 里；配合 `ssh-keygen -R` 清旧指纹 + `ssh-keyscan` 预写 known_hosts，让首连零警告。
- 重部署=新主机指纹：known_hosts 旧条目会让 ssh 直接拒连，必须先 `-R`。

## 3. IMAPI2 制 ISO（Windows 原生，免第三方）

- COM 对象 `IMAPI2FS.MsftFileSystemImage`；`FileSystemsToCreate=3`（ISO9660+Joliet）；写文件用 C# IStream 拷贝循环（Add-Type）。
- `$fsi.Root.AddFile(name, path)` 报"无法转换 string→Object"（第二参要 IStream）→ 改 `AddTree(目录, $false)` 打包目录树。
- **卷标必须 `CIDATA`**：cloud-init NoCloud 靠文件系统卷标发现种子（ISO 或 vfat 均可）。

## 4. 国内镜像源实测（2026-09）

- 阿里云 `mirrors.aliyun.com/ubuntu-releases/`：目录页可达，但 ISO 下载 302 到 `iso-osm.mirrors.aliyuncs.com`（纯 HTTP），本机直连不通。
- ISO 可靠源：华为云 `repo.huaweicloud.com/ubuntu-releases/24.04/`（直连 200）。
- 云金镜像（qcow2）：清华 `mirrors.tuna.tsinghua.edu.cn/ubuntu-cloud-images/noble/current/noble-server-cloudimg-amd64.img`（约 625M，带 SHA256SUMS）。
- qemu-img Windows 便携版：cloudbase.it（页面实际文件名 `qemu-img-win-x64-2_3_0.zip`，站内链接会变，先抓下载页再拼 URL）。

## 5. qemu 2.3 转换格式名

- VHD 格式名在 qemu 2.3 叫 **`vpc`**（`-O vhd` 报 Unknown file format）。
- 完整命令：`qemu-img.exe convert -f qcow2 -O vpc -o subformat=dynamic in.qcow2 out.vhd`。
- 产物虚拟 3.5G、实占约 1.9G；后续 `Convert-VHD -VHDType Dynamic` + `Resize-VHD 40GB` 交给 Hyper-V。

## 6. 金镜像 + cloud-init 链路要点

- Ubuntu 官方云镜像 Gen2/UEFI 直接可引导；secure boot 模板用 `MicrosoftUEFICertificateAuthority`。
- `Resize-VHD` 扩到 40G 后首启 growpart 自动扩根分区（实测 3.5G→38G 可用）。
- 固定 IP：`seed\network-config`（netplan v2）`match: macaddress` + `set-name: eth0`；MAC 来自 `Set-VMNetworkAdapter -StaticMacAddress`，两处必须一致。
- cloud-init 顺序：网络（init 阶段）→ sshd 起来 → users/包安装（config 阶段）→ done。**端口 22 通 ≠ 用户配好**，验证要等 ssh 真登录成功（`echo CLOUD_INIT_DONE` 回执）。
- 改种子后对已部署 VM 无效（instance-id 没变）——重新部署：删 `vm\lab.vhdx` 重跑 20；或改 `seed\meta-data` 的 instance-id。

## 7. Hyper-V 文件锁与权限时机

- VM 挂载中的 ISO/种子盘被 vmms 锁定：改名/删除目录会 Permission denied → 先停机或 `Set-VMDvdDrive` 换路径再动文件。
- `Hyper-V Administrators` 组加入后需**注销重登**；期间 Get-VM 等在非提权 shell 报无权限（旧登录令牌）。
- RunOnce（HKLM\...\RunOnce）在登录时以用户身份跑 bat，bat 内自提权弹 UAC——任务链的"个人机等价物"，条目跑完自删。

## 8. 部署纪律（对齐 syscheck 红线）

- 提权 .ps1/.bat 纯 ASCII；bat 用 CRLF（`unix2dos`）；PS5.1 无 BOM UTF-8 中文=静默失效。
- 一切声明成功前要有**回执**：transcript 日志 + 产物文件（reports/、VERIFIED 输出）。
- 供应链校验：镜像必须 SHA256 对照官方 SUMS。
- 脚本幂等：重跑显示 [SKIP] 跳过已完成步骤；关键参数名在脚本头注释里标注"已实测"。

## 9. 与安装器路（autoinstall）的取舍

- 安装器路（ISO+autoinstall 种子）保留在方法论里但默认不用：多一次确认交互、装机 5-10 分钟、无复用价值。
- 金镜像路：零交互、2-5 分钟、可无限重放——与云厂商一致，学习价值更高（练的就是真实上线方式）。

## 10. MySQL 企业精简三坑（2026-09-29 Ubuntu 24.04 / mysql-server 8.0.46）

- **`SHOW ENGINES` 不反映 `disabled_storage_engines`**：被禁引擎照样显示 YES/DEFAULT。验收必须用**行为证明**（`CREATE TABLE ... ENGINE=MyISAM` 应报 ERROR 3161）+ `SELECT @@disabled_storage_engines`。MyISAM/MEMORY/ARCHIVE/BLACKHOLE/FEDERATED 可禁；CSV 必须留（日志表用）；PERFORMANCE_SCHEMA 内置不可禁；MRG_MYISAM 内置无害。
- **`mysqlx` 是启动选项不是运行时系统变量**（`SELECT @@mysqlx` 报 Unknown variable）；Debian/Ubuntu 的 X Plugin 是**内置插件**（UNINSTALL PLUGIN 报 1619 不能删），`mysqlx = OFF` 写进配置重启即关（33060 消失）。读 error.log 注意区分 apt postinst 时序的旧 "X Plugin ready" 行，别误判。
- **`!includedir` 按文件名排序读取，后读者胜**：`99-xxx.cnf` 排在发行版 `mysqld.cnf` **前面**（数字<字母），bind-address 会被原配置的 127.0.0.1 反杀。覆盖发行版配置必须用 **`zz-` 前缀**排到最后。
- 企业免费商用的准确姿势：社区版（GPLv2，自用/服务化免费）+ 配置调优 + GTID/慢日志基线；付费企业版卖的是商业组件（审计/线程池/热备/支持），社区版用配置与 Percona 工具补位。
