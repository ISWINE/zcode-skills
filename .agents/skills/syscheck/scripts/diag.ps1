# diag.ps1 - Non-elevated system deep diagnostics
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File diag.ps1
# Covers: SSD health, TRIM, root big files, dumps, pending reboot, Defender,
#         firewall, auto-but-stopped services, recycle bin, update cache, Installer size.
# ASCII only. Some sections need admin and will show errors/empty - rerun elevated if needed.
$ErrorActionPreference = 'SilentlyContinue'

Write-Host "=== [1] Physical disk health ==="
Get-PhysicalDisk | Select-Object FriendlyName,HealthStatus,MediaType,BusType | Format-Table -AutoSize

Write-Host "=== [2] TRIM (0 = correct) ==="
fsutil behavior query DisableDeleteNotify 2>&1

Write-Host "=== [3] Root big files (hiberfil/pagefile) ==="
Get-ChildItem C:\ -Force -File | Where-Object { $_.Length -gt 100MB } |
  ForEach-Object { "{0,8:N1} GB  {1}" -f ($_.Length/1GB), $_.Name }

Write-Host "=== [4] Crash dumps ==="
$md = Get-Item C:\Windows\MEMORY.DMP
if ($md) { "MEMORY.DMP: {0:N1} GB" -f ($md.Length/1GB) } else { "no MEMORY.DMP" }
$mini = @(Get-ChildItem C:\Windows\Minidump -File).Count; "minidumps: $mini"

Write-Host "=== [5] Pending reboot ==="
$rb = @()
if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') { $rb += 'CBS' }
if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') { $rb += 'WU' }
if ((Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations).PendingFileRenameOperations) { $rb += 'PFR' }
if ($rb) { "PENDING: $($rb -join ',')" } else { "clean" }

Write-Host "=== [6] Defender ==="
Get-MpComputerStatus | Select-Object AMServiceEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated | Format-List

Write-Host "=== [7] Firewall profiles (all False = URGENT) ==="
Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction | Format-Table -AutoSize

Write-Host "=== [8] Auto-start but stopped services ==="
Get-Service | Where-Object { $_.StartType -eq 'Automatic' -and $_.Status -ne 'Running' } |
  Select-Object Name,DisplayName | Format-Table -AutoSize

Write-Host "=== [9] Update cache size ==="
"{0,8:N1} MB  SoftwareDistribution\Download" -f ((Get-ChildItem 'C:\Windows\SoftwareDistribution\Download' -Recurse -Force | Measure-Object Length -Sum).Sum/1MB)

Write-Host "=== [10] Installer size (>2GB = run orphan cross-ref) ==="
"{0,8:N2} GB  C:\Windows\Installer" -f ((Get-ChildItem 'C:\Windows\Installer' -Recurse -Force | Measure-Object Length -Sum).Sum/1GB)

Write-Host "=== [11] Listening ports (non-localhost) ==="
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalAddress -notmatch '::1|127\.0\.0\.1' } |
  ForEach-Object { '{0,-16} {1,-6} {2}' -f $_.LocalAddress, $_.LocalPort, (Get-Process -Id $_.OwningProcess).ProcessName } |
  Sort-Object | Get-Unique

Write-Host "=== [12] WinINET proxy (dev-sidecar landmine: ProxyEnable=0 is harmless) ==="
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' |
  Select-Object ProxyEnable,AutoConfigURL | Format-List

Write-Host "=== [13] C drive ==="
Get-PSDrive C | Select-Object @{n='UsedGB';e={[math]::Round($_.Used/1GB)}},@{n='FreeGB';e={[math]::Round($_.Free/1GB)}} | Format-List
