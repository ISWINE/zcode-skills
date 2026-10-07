# esquick.ps1 - Everything (es.exe) accelerated rough-scan battery for syscheck Phase A
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File esquick.ps1 [-EsPath <es.exe>] [-OutDir <dir>] [-KeepEverything]
# Why: Everything keeps a live MFT/USN index -> whole-volume enumeration in seconds,
#      vs recursive Get-ChildItem/du which can take hours (Git Bash du once hung a session).
# NOTE: es.exe is ONLY an IPC remote control - it does nothing without a RUNNING
#      everything.exe (proven: "Error 8: Everything IPC not found"). So this script
#      starts the engine when needed and restores it to stopped afterwards.
#      On some machines the engine self-elevates (UAC) to read the NTFS MFT; a
#      non-elevated es.exe then CANNOT exit it (UIPI blocks the IPC) - shutdown is
#      time-bounded and honestly reported instead of hanging.
# ASCII only (PS5.1 GBK trap). es.exe traps baked in:
#   - multi-word queries MUST go via -search (positional args get mangled)
#   - '!path:' negation unreliable through es.exe -> exclusions done here in PS
#   - '-n 1000000' avoids the 64-row default cap; never head-truncate es output
#   - EFU rows with attribute bit 0x10 are directories
param(
  [string]$EsPath,
  [string]$OutDir = (Join-Path $env:TEMP ('syscheck-es-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))),
  [switch]$KeepEverything
)
$ErrorActionPreference = 'Continue'

function Find-Es {
  param([string]$Hint)
  if ($Hint -and (Test-Path $Hint)) { return (Resolve-Path $Hint).Path }
  $c = Get-Command es.exe -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  $fixed = @("$env:ProgramFiles\Everything\es.exe",
             "${env:ProgramFiles(x86)}\Everything\es.exe",
             "$env:LOCALAPPDATA\Programs\Everything\es.exe")
  foreach ($p in $fixed) { if (Test-Path $p) { return $p } }
  # portable copies often live in a CJK-named folder - wildcard keeps script ASCII
  foreach ($g in 'E:\*\Everything*\es.exe','D:\*\Everything*\es.exe','C:\*\Everything*\es.exe') {
    $hit = Resolve-Path $g -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) { return $hit.Path }
  }
  return $null
}

$es = Find-Es $EsPath
if (-not $es) {
  Write-Output 'ES_NOT_FOUND - download the Everything portable zip into the workspace (see SKILL.md Step 1), or pass -EsPath; rough file-face skipped.'
  exit 0
}
$everythingExe = Join-Path (Split-Path $es) 'everything.exe'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Write-Output ("[ES] tool=" + $es)

function Test-EsAlive {
  & $script:es -n 1 -search '.' 2>$null | Out-Null
  return ($LASTEXITCODE -eq 0)
}

$wasRunning = [bool](Get-Process everything -ErrorAction SilentlyContinue)
if (-not $wasRunning) {
  if (-not (Test-Path $everythingExe)) {
    Write-Output 'EVERYTHING_EXE_MISSING next to es.exe - cannot auto-start.'
    exit 0
  }
  Write-Output '[ES] Everything engine not running -> starting (will try es -exit at the end)...'
  Start-Process $everythingExe
  $deadline = (Get-Date).AddSeconds(90)
  while (-not (Test-EsAlive)) {
    if ((Get-Date) -gt $deadline) { Write-Output 'EVERYTHING_START_TIMEOUT'; exit 0 }
    Start-Sleep -Milliseconds 500
  }
  Write-Output '[ES] Everything engine up.'
}

function Get-Num([string]$s) { $v = [int64]0; [int64]::TryParse([string]$s, [ref]$v) | Out-Null; $v }

$exclRoots = @(
  (Join-Path $env:windir '').ToLower(),
  (Join-Path $env:ProgramData '').ToLower(),
  (Join-Path $env:ProgramFiles '').ToLower(),
  ("${env:ProgramFiles(x86)}\").ToLower(),
  ("$env:LOCALAPPDATA\Temp\").ToLower(),
  ("$env:SystemDrive\`$RECYCLE.BIN\").ToLower()
)
function Test-Excluded([string]$p) {
  $pl = $p.ToLower()
  foreach ($r in $script:exclRoots) { if ($pl.StartsWith($r, [StringComparison]::Ordinal)) { return $true } }
  return $false
}

function Read-Efu([string]$file, [switch]$DirsOnly) {
  $rows = @()
  foreach ($r in (Import-Csv $file -Encoding UTF8)) {
    $fn = [string]$r.Filename
    if (-not $fn) { continue }
    $isDir = ((Get-Num $r.Attributes) -band 0x10) -ne 0
    if ($DirsOnly -ne $isDir) { continue }
    if (-not $DirsOnly -and (Test-Excluded $fn)) { continue }
    $rows += [pscustomobject]@{ Path = $fn; Size = (Get-Num $r.Size) }
  }
  return ,$rows
}

function Invoke-Cat([string]$name, [string]$query, [switch]$DirsOnly) {
  # CAT status goes to Host on purpose - it must NOT pollute the returned rows
  # (first field-test: Write-Output mixed the status line into $rows and broke
  # every downstream Group/Sort/Measure - see lessons.md #29).
  $efu = Join-Path $OutDir ($name + '.efu')
  $sw = [Diagnostics.Stopwatch]::StartNew()
  & $script:es -n 1000000 -export-efu $efu -search $query 2>$null | Out-Null
  $code = $LASTEXITCODE
  $sw.Stop()
  if ($code -ne 0) { Write-Host ("CAT {0} ES_ERROR code={1}" -f $name, $code); return $null }
  $rows = Read-Efu $efu -DirsOnly:$DirsOnly
  $sum = [int64]0
  foreach ($r in $rows) { $sum += $r.Size }
  Write-Host ("CAT {0} files={1} bytes={2} elapsed_ms={3}" -f $name, $rows.Count, $sum, $sw.ElapsedMilliseconds)
  return ,$rows
}

# --- battery: the fast file-face of the rough report ---
$junk = Invoke-Cat 'tmpdmp'   'ext:tmp;dmp'
Invoke-Cat 'biglog'   '*.log size:>50mb' | Out-Null
$dumps = Invoke-Cat 'dumps'    '*.dmp size:>10mb'
$big   = Invoke-Cat 'bigfiles' 'size:>500mb'
Invoke-Cat 'setupheap' 'ext:msi;iso size:>50mb' | Out-Null
Invoke-Cat 'nodemod' 'node_modules folder:' -DirsOnly | Out-Null
Invoke-Cat 'venvs'   'wildcard:.venv folder:' -DirsOnly | Out-Null

if ($junk) {
  $junk | Group-Object { $_.Path.Substring(0,2) } |
    ForEach-Object {
      $s = [int64]0; foreach ($r in $_.Group) { $s += $r.Size }
      "  DRIVE {0} tmpdmp_bytes={1}" -f $_.Name, $s
    }
}
if ($big) {
  Write-Output 'TOP bigfiles (size:>500mb):'
  $big | Sort-Object Size -Descending | Select-Object -First 30 |
    ForEach-Object { "  {0,8:N2} GB  {1}" -f ($_.Size/1GB), $_.Path }
}
if ($dumps) {
  Write-Output 'TOP dumps (size:>10mb):'
  $dumps | Sort-Object Size -Descending | Select-Object -First 15 |
    ForEach-Object { "  {0,8:N2} GB  {1}" -f ($_.Size/1GB), $_.Path }
}
Write-Output ("EFU_DIR=" + $OutDir)

# --- restore: only stop what we started; never hang on an elevated engine ---
if (-not $wasRunning -and -not $KeepEverything) {
  $job = Start-Job -ScriptBlock {
    param($esExe)
    & $esExe -exit 2>$null | Out-Null
  } -ArgumentList $es
  Wait-Job $job -Timeout 15 | Out-Null
  Remove-Job $job -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
  if (Get-Process everything -ErrorAction SilentlyContinue) {
    Stop-Process -Name everything -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
  }
  $still = [bool](Get-Process everything -ErrorAction SilentlyContinue)
  if ($still) {
    Write-Output 'EVERYTHING_STILL_RUNNING (engine self-elevated via UAC; non-elevated es/Stop-Process cannot touch it). Close its window manually or rerun this script elevated.'
  } else {
    Write-Output 'EVERYTHING_RESTORED_TO_STOPPED=True'
  }
}
Write-Output 'ESQUICKDONE'
