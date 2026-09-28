# groundtruth.ps1 - Collect installed-software ground truth (6 evidence sources)
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File groundtruth.ps1
# Runs NON-elevated, ~30s. ASCII only (PS5.1 GBK trap - see lessons.md).
$ErrorActionPreference = 'SilentlyContinue'

Write-Host "=== [1] UNINSTALL REGISTRY (loc/exists/key) ==="
$paths = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
         'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
         'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
Get-ItemProperty $paths | Where-Object { $_.DisplayName } |
  ForEach-Object {
    $loc = $_.InstallLocation
    $exists = if ($loc -and (Test-Path $loc)) { 'OK' } elseif ($loc) { 'CHECK-BY-HAND' } else { '-' }
    # NOTE: quoted InstallLocation makes Test-Path lie; re-verify MISSING with dir/ls
    "{0} | loc={1} [{2}] | key={3}" -f $_.DisplayName, $loc, $exists, $_.PSChildName
  } | Sort-Object

Write-Host "`n=== [2] APPX PACKAGES (non-framework) ==="
Get-AppxPackage | Where-Object { -not $_.IsFramework -and -not $_.NonRemovable } |
  ForEach-Object { "{0} v{1}" -f $_.Name, $_.Version } | Sort-Object -Unique

Write-Host "`n=== [3] SERVICES (3rd-party paths) ==="
Get-CimInstance Win32_Service |
  Where-Object { $_.PathName -and $_.PathName -notmatch 'Windows\\|system32' } |
  ForEach-Object { "{0} | {1} | {2}" -f $_.Name, $_.State, $_.PathName }

Write-Host "`n=== [4] RUN/STARTUP KEYS ==="
foreach ($rk in 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
                'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
                'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce',
                'HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce') {
  $props = Get-ItemProperty $rk
  if ($props) {
    $props.PSObject.Properties | Where-Object { $_.Name -notmatch '^PS' } |
      ForEach-Object { "$rk :: $($_.Name) = $($_.Value)" }
  }
}
Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup" -Filter *.lnk |
  ForEach-Object { "StartupFolder :: $($_.Name)" }

Write-Host "`n=== [5] SCHEDULED TASKS (3rd-party) ==="
Get-ScheduledTask | ForEach-Object {
  $t = $_
  $t.Actions | Where-Object { $_.Execute -and $_.Execute -notmatch 'Windows\\|system32' } |
    ForEach-Object { "{0}{1}`n  -> {2}" -f $t.TaskPath, $t.TaskName, $_.Execute }
}

Write-Host "`n=== [6] RUNNING PROCESS PATHS (3rd-party) ==="
Get-Process | Where-Object { $_.Path -and $_.Path -notmatch 'Windows\\|system32' } |
  Select-Object -ExpandProperty Path -Unique | Sort-Object

Write-Host "`n=== [7] IDE PLUGINS (not in registry!) ==="
Get-ChildItem "$env:APPDATA\JetBrains\*\plugins" -Directory |
  ForEach-Object { $_.Parent.Name + ' :: ' + $_.Name }

Write-Host "`n=== [8] START-MENU LNK sweep ==="
Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs",
              'C:\ProgramData\Microsoft\Windows\Start Menu\Programs' -Recurse -Filter *.lnk |
  Select-Object -ExpandProperty Name | Sort-Object -Unique
