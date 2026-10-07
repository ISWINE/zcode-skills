# 屏幕色温暖白护眼（免安装版 f.lux，随时间自动切换）

## 需求 / 症状

晚间屏幕白点 6500K 偏冷偏刺眼，想要暖白护眼效果，且白天/晚上自动切换、重启不丢、不装任何第三方软件（f.lux/Night Light 之外的零依赖路线）。

## 原理

`SetDeviceGammaRamp`（**gdi32.dll**，不是 user32）直接写显卡扫描输出 LUT，按色温算三通道增益（Tanner Helland 黑体近似公式）。三个实测坑：

1. P/Invoke 声明错库会报 EntryPointNotFoundException——伽马 API 在 **gdi32**，GetDC 才在 user32。
2. PS 5.1 不认 `ushort[]` 字面量，数组要用 `[uint16[]]::new(256)`。
3. **截图验证不了伽马**：CopyFromScreen 抓的是 LUT 之前的帧缓冲，所以必须 `GetDeviceGammaRamp` 回读验证；同理用户开着此效果时截图颜色是"正常"的。

LUT 是易失的（重启/注销/部分驱动事件清空）→ 登录任务兜底 + 每天两个切换点定时：**07:00 → 5000K，22:00 → 4200K**（2026-10-08 定稿：用户确认两档均可、白天不回中性；每小时自愈方案因 powershell 每小时闪窗被否，一律走 wscript 无窗启动器）。

## 改法

脚本真身：`D:\tools\SetGamma\SetGamma.ps1`（参数：`-Temp <K>` 手动档、`-Dim <0-1>` 叠加压亮度、`-Reset` 复位、`-Auto` 按时间表自动选档）。全文：

```powershell
param(
  [int]$Temp = 5000,
  [double]$Dim = 1.0,
  [switch]$Reset,
  [switch]$Auto
)
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class GammaHelper {
  [DllImport("user32.dll")] public static extern IntPtr GetDC(IntPtr hWnd);
  [DllImport("gdi32.dll")] public static extern bool SetDeviceGammaRamp(IntPtr hDC, ref RAMP lpRamp);
  [DllImport("gdi32.dll")] public static extern bool GetDeviceGammaRamp(IntPtr hDC, ref RAMP lpRamp);
  [StructLayout(LayoutKind.Sequential)]
  public struct RAMP {
    [MarshalAs(UnmanagedType.ByValArray, SizeConst=256)] public ushort[] red;
    [MarshalAs(UnmanagedType.ByValArray, SizeConst=256)] public ushort[] green;
    [MarshalAs(UnmanagedType.ByValArray, SizeConst=256)] public ushort[] blue;
  }
}
"@

function Get-ChannelValue([double]$t, [string]$ch) {
  if ($ch -eq 'r') {
    if ($t -le 66) { return 255.0 }
    return 329.698727446 * [Math]::Pow(($t - 60), -0.1332047592)
  }
  if ($ch -eq 'g') {
    if ($t -le 66) { return 99.4708025861 * [Math]::Log($t) - 161.1195681661 }
    return 288.1221695283 * [Math]::Pow(($t - 60), -0.0755148492)
  }
  if ($t -ge 66) { return 255.0 }
  if ($t -le 19) { return 0.0 }
  return 138.5177312231 * [Math]::Log($t - 10) - 305.0447927307
}

if ($Auto) {
  $h = (Get-Date).Hour
  if ($h -ge 7 -and $h -lt 22) { $Temp = 5000 }
  else                          { $Temp = 4200 }
}

$dc = [GammaHelper]::GetDC([IntPtr]::Zero)
$ramp = New-Object GammaHelper+RAMP
$ramp.red = [uint16[]]::new(256)
$ramp.green = [uint16[]]::new(256)
$ramp.blue = [uint16[]]::new(256)

if ($Reset -or $Temp -ge 6500) {
  for ($i = 0; $i -lt 256; $i++) {
    $ramp.red[$i] = $i * 256; $ramp.green[$i] = $i * 256; $ramp.blue[$i] = $i * 256
  }
  $ok = [GammaHelper]::SetDeviceGammaRamp($dc, [ref]$ramp)
  Write-Output ("identity ramp applied: " + $ok)
  return
}

$t = $Temp / 100.0
$rm = (Get-ChannelValue $t 'r') / 255.0 * $Dim
$gm = (Get-ChannelValue $t 'g') / 255.0 * $Dim
$bm = (Get-ChannelValue $t 'b') / 255.0 * $Dim
for ($i = 0; $i -lt 256; $i++) {
  $ramp.red[$i]   = [Math]::Min(65535, [int]([Math]::Round($i * 256 * $rm)))
  $ramp.green[$i] = [Math]::Min(65535, [int]([Math]::Round($i * 256 * $gm)))
  $ramp.blue[$i]  = [Math]::Min(65535, [int]([Math]::Round($i * 256 * $bm)))
}
$ok = [GammaHelper]::SetDeviceGammaRamp($dc, [ref]$ramp)
$check = New-Object GammaHelper+RAMP
$check.red = [uint16[]]::new(256)
$check.green = [uint16[]]::new(256)
$check.blue = [uint16[]]::new(256)
[void][GammaHelper]::GetDeviceGammaRamp($dc, [ref]$check)
Write-Output ("set={0} readback ramp[255]: R={1} G={2} B={3}" -f $ok, $check.red[255], $check.green[255], $check.blue[255])
```

定时（Git Bash 记得 `MSYS_NO_PATHCONV=1`）：

```bash
# 无闪窗启动器（wscript 是 GUI 子系统，零窗口）。D:\tools\SetGamma\apply.vbs 一行：
# CreateObject("WScript.Shell").Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\tools\SetGamma\SetGamma.ps1 -Auto", 0, False

# 每天只在两档切换点跑（用户级可建；每小时自愈已废弃=powershell 每小时闪窗惹用户嫌）
MSYS_NO_PATHCONV=1 schtasks /create /tn "SetGamma-Day" /tr "wscript.exe \"D:\tools\SetGamma\apply.vbs\"" /sc daily /st 07:00 /f
MSYS_NO_PATHCONV=1 schtasks /create /tn "SetGamma-Night" /tr "wscript.exe \"D:\tools\SetGamma\apply.vbs\"" /sc daily /st 22:00 /f

# 登录兜底（重启清 LUT/关机错过切换点时补齐）：onlogon 要管理员，UAC 提权跑脚本文件执行。
# 坑：Start-Process -ArgumentList 直接传含内嵌引号的 /tr 会穿 UAC 碎掉（实测 exit 1），必须提权执行 .ps1、在脚本内部用 PS 引号传参、结果落日志+回读 XML <Command> 验证。
# change2.ps1 核心行：& schtasks.exe /change /tn "SetGamma-Logon" /tr 'wscript.exe "D:\tools\SetGamma\apply.vbs"' *> $log
```

GUI 等价：系统自带"夜灯"（设置 > 系统 > 显示 > 夜灯）也能暖色+日落日出调度，但强度只有档位、无时间表细控；上述方案是它的无依赖精细版。

## 验证

LUT 层验证（截图无效！）：

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File D:\tools\SetGamma\SetGamma.ps1 -Reset
MSYS_NO_PATHCONV=1 schtasks /run /tn "SetGamma-Hourly"
# 等 >=10 秒（PS 冷启动 + Add-Type 编译延迟，5 秒不够会误判失败）
# 回读 probe（GetDeviceGammaRamp 打印 ramp[255]）：
# 5000K 预期 R=65280 G=58371 B=52718（identity=65280/65280/65280）
```

## 回滚 / 变体

```bash
MSYS_NO_PATHCONV=1 schtasks /delete /tn "SetGamma-Day" /f
MSYS_NO_PATHCONV=1 schtasks /delete /tn "SetGamma-Night" /f
# 删 SetGamma-Logon 需提权：同上 UAC + 脚本文件方式跑 & schtasks /delete /tn "SetGamma-Logon" /f
powershell -NoProfile -ExecutionPolicy Bypass -File D:\tools\SetGamma\SetGamma.ps1 -Reset   # 立即恢复 6500K
```

- 手动档：`-Temp 4200|4500|5000|5500|5800`；压亮度不变色：`-Dim 0.9`；恢复分时段自动（如白天 6500/晚上 5000）改脚本 `-Auto` 段即可。
- 亮度是独立维度：内屏走 WMI（`root/WMI WmiMonitorBrightness`），本机 40% 晚间已合适未动。

已验证 2026-10-07，本机 Windows 11 内测版 26300（计划任务端到端实测：Reset→/run→10s 后回读 5000K 斜坡分毫不差）
