# init.ps1 - syscheck STEP-0 environment probe (portable, non-elevated, ~10s)
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File init.ps1
# Emits a KEY=VALUE machine profile. Harness identity is NOT probed here:
# the agent already knows what it runs in from its own prompt/toolset.
# ASCII only (PS5.1 GBK trap).
$ErrorActionPreference = 'SilentlyContinue'

Write-Output '=== [1] OS / HOST ==='
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
"OS_NAME={0}" -f $os.Caption
"OS_BUILD={0}" -f $os.BuildNumber
"OS_ARCH={0}" -f $os.OSArchitecture
"HOST={0} MODEL={1}" -f $cs.Name, $cs.Model
"LASTBOOT={0}" -f $os.LastBootUpTime

Write-Output '=== [2] CPU / RAM ==='
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
"CPU={0}" -f $cpu.Name.Trim()
"CORES={0} LOGICAL={1}" -f $cpu.NumberOfCores, $cpu.NumberOfLogicalProcessors
"RAM_GB={0:N1} FREE_RAM_GB={1:N1}" -f ($cs.TotalPhysicalMemory/1GB), ($os.FreePhysicalMemory*1KB/1GB)
# CAUTION (lessons.md #21): CurrentClockSpeed / % of Maximum Frequency are fake
# on some OEM boxes - never use them to judge frequency scaling.

Write-Output '=== [3] USER / SHELL ==='
"USER={0}" -f $env:USERNAME
"PROFILE={0}" -f $env:USERPROFILE
"PS_VERSION={0}" -f $PSVersionTable.PSVersion.ToString()
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
"ELEVATED={0}" -f $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
"EXECUTIONPOLICY={0}" -f (Get-ExecutionPolicy)
"BASH={0}" -f (Get-Command bash.exe).Source

Write-Output '=== [4] VOLUMES (Everything covers NTFS only) ==='
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
  "VOL={0} LABEL={1} FS={2} TOTAL_GB={3:N0} FREE_GB={4:N0}" -f $_.DeviceID, $_.VolumeName, $_.FileSystem, ($_.Size/1GB), ($_.FreeSpace/1GB)
}

Write-Output '=== [5] TOOL PROBE ==='
$es = $null
$c = Get-Command es.exe -ErrorAction SilentlyContinue
if ($c) { $es = $c.Source } else {
  foreach ($p in @("$env:ProgramFiles\Everything\es.exe",
                   "${env:ProgramFiles(x86)}\Everything\es.exe",
                   "$env:LOCALAPPDATA\Programs\Everything\es.exe") ) {
    if (Test-Path $p) { $es = $p; break }
  }
}
if (-not $es) {
  # portable copies often live in a CJK-named folder - wildcard keeps script ASCII
  foreach ($g in 'E:\*\Everything*\es.exe','D:\*\Everything*\es.exe','C:\*\Everything*\es.exe') {
    $hit = Resolve-Path $g -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) { $es = $hit.Path; break }
  }
}
"ES_EXE={0}" -f $es
"EVERYTHING_RUNNING={0}" -f [bool](Get-Process everything -ErrorAction SilentlyContinue)
"WINGET={0}" -f (Get-Command winget.exe).Source

Write-Output '=== [6] PROFILE SUMMARY (quote this block in the report header) ==='
"SUMMARY os={0} build={1} ram={2:N0}GB user={3} elevated={4} es={5} everything_running={6}" -f `
  $os.Caption, $os.BuildNumber, ($cs.TotalPhysicalMemory/1GB), $env:USERNAME, `
  $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator), `
  ([bool]$es), [bool](Get-Process everything -ErrorAction SilentlyContinue)
