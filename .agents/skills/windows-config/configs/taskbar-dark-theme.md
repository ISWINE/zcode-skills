# 任务栏暗色 + 护眼中灰通透调（Windows 11）

## 需求 / 症状

任务栏默认浅色太白刺眼，想换暗色；但系统暗色是死黑（#202020）显压抑，套用户原有主题色又变成一条饱和色带，与桌面色差过大、看久了眼睛不舒服。目标：暗色系、不太暗、半透明、无色相冲突。

## 原理

三层各管一摊，必须一起动，只改一处必翻车：

1. `Personalize\SystemUsesLightTheme=0`：壳层（任务栏/开始菜单/通知中心）切暗色，**不影响应用**（`AppsUseLightTheme` 独立）。
2. `Personalize\ColorPrevalence=1`：把主题色铺到任务栏+开始菜单（半透明混壁纸）。系统暗色的死黑没有官方"调浅"旋钮，唯一办法就是用主题色覆盖。
3. 主题色真源有**多处**：`Explorer\Accent\AccentPalette`（8 级调色板二进制）+ `AccentColorMenu` + `StartColorMenu` + `DWM\AccentColor` + `DWM\ColorizationColor/Afterglow`。只改 DWM 一处，壳层仍读旧色 → 任务栏呈旧色（实测残留青色）。

注册表直改后 Explorer 不自动重绘，需广播 `WM_SETTINGCHANGE("ImmersiveColorSet")`，免重启 explorer。

### 定色依据（护眼证据链）

- 近白桌面 × 饱和暗青任务栏 = 色相差 81 通道差 + 亮差 2.9:1，双重刺激；青/蓝是暗底最刺眼色系（ColorArchive）。
- 定为**中性微冷灰 #383C40**（通道差仅 4，读作无彩色），经系统 ~55% 透明度混入壁纸后实际渲染 **≈#7B8083 中灰**：亮差压到 1.85:1、色相差归零，且明显深于浅色默认 #EBEBEB。
- 依据：纯黑/过暗放大光晕效应 halation（Google Material 可读性研究，#121212+抬升面）；暗底高饱和产生光学振动致眼疲劳（atmos.style / uxmisfit）；冷灰比暖灰更被眼宽容（jamesrobinson.io）。

## 改法（命令行，Git Bash）

⚠️ Git Bash 下 reg 的 `/v /t /d /f` 开关会被 MSYS 转成路径，**必须加 `MSYS_NO_PATHCONV=1` 前缀**。

```bash
# 1. 壳层切暗（应用不动）
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" /v SystemUsesLightTheme /t REG_DWORD /d 0 /f

# 2. 主题色铺到任务栏
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" /v ColorPrevalence /t REG_DWORD /d 1 /f

# 3. 全套色源写中性微冷灰（8 级调色板 浅→深 + 三处 DWORD，均为 ABGR）
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Accent" /v AccentPalette /t REG_BINARY /d D9DBDD00C0C3C600A7ABAF008D92970074797F005C616600464A4F00383C4000 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Accent" /v AccentColorMenu /t REG_DWORD /d 0xFF403C38 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Accent" /v StartColorMenu /t REG_DWORD /d 0xFF3C3834 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\DWM" /v AccentColor /t REG_DWORD /d 0xFF403C38 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\DWM" /v ColorizationColor /t REG_DWORD /d 0xC4403C38 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\DWM" /v ColorizationAfterglow /t REG_DWORD /d 0xC4403C38 /f
```

调色板二进制字节序 = 每色 4 字节按 **R,G,B,A** 排（即存为 ABGR DWORD）；ABGR 规则：`0xAABBGGRR`，对称灰（R=G=B）时与 RGB 同形。

广播刷新（存为纯 ASCII 的 .ps1 再跑，PS5.1 中文注释会炸）：

```powershell
$sig = @'
[DllImport("user32.dll", SetLastError=true)]
public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
'@
$t = Add-Type -MemberDefinition $sig -Name W -Namespace P -PassThru
$r = [UIntPtr]::Zero
[void]$t::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, 'ImmersiveColorSet', 2, 1000, [ref]$r)
```

GUI 等价：设置 > 个性化 > 颜色 → 模式"深色" + 展开选一个灰色 + 打开"在开始菜单和任务栏上显示主题色"（GUI 调不出 8 级灰板细节，色值以注册表为准）。

## 验证

DPI 感知截屏采样（**必须先 `SetProcessDPIAware()`**，否则缩放屏上截到的 960px 画面根本不含任务栏，白值假阴性坑）：

```powershell
$sig = '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
$d = Add-Type -MemberDefinition $sig -Name D -Namespace P -PassThru
[void]$d::SetProcessDPIAware()
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.X, $b.Y, 0, 0, $bmp.Size); $g.Dispose()
$c = $bmp.GetPixel([int]($b.Width*0.25), $b.Height-24)
"R={0} G={1} B={2}" -f $c.R, $c.G, $c.B
```

预期：任务栏 ≈ **RGB(123,127,131)** ±5，三点采样一致，通道差 ≤8；开始菜单同色调。近白桌面（≈RGB 234）下亮差约 1.85:1。

## 回滚 / 变体

回滚 = 原值全套（本机 2026-10-07 前原状，青色主题色）：

```bash
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" /v SystemUsesLightTheme /t REG_DWORD /d 1 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" /v ColorPrevalence /t REG_DWORD /d 0 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Accent" /v AccentPalette /t REG_BINARY /d 69FCFF0029F7FF0000D5E10000B7C300009FAA000067700000343B004A545900 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Accent" /v AccentColorMenu /t REG_DWORD /d 0xffc3b700 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Accent" /v StartColorMenu /t REG_DWORD /d 0xffaa9f00 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\DWM" /v AccentColor /t REG_DWORD /d 0xffc3b700 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\DWM" /v ColorizationColor /t REG_DWORD /d 0xc400b7c3 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\DWM" /v ColorizationAfterglow /t REG_DWORD /d 0xc400b7c3 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\DWM" /v ColorizationColorBalance /t REG_DWORD /d 0x59 /f
MSYS_NO_PATHCONV=1 reg add "HKCU\Software\Microsoft\Windows\DWM" /v ColorizationBlurBalance /t REG_DWORD /d 0x1 /f
```

（+ 广播刷新一次）

变体与实测边界：

- **深浅档**：整体 ±1 档 = 调色板与三处 DWORD 同步换基色。浅一档 #464A4F（渲染≈#8E9296），深一档 #2E3236（渲染≈#6E7276）。
- **`ColorizationColorBalance`/`ColorizationBlurBalance` 对任务栏材质无效**（26300 实测像素零变化），调任务栏通透度别碰它们。
- **Windows 无官方任务栏不透明度滑杆**（EnableTransparency 仅开/关）。要真通透唯一方案是 TranslucentTB（开源/商店/可完全卸载，Clear+百分比不透明度）——2026-10-07 用户决定暂不装。
- 开始菜单/通知中心随壳层同步变色，属预期。

已验证 2026-10-07，本机 Windows 11 内测版 26300（2160x1440@150%，Git Bash + PS5.1）
