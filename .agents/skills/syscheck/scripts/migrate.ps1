# migrate.ps1 - Junction migration C -> D:\cshift farm (cold data only!)
# Usage (elevated NOT required): powershell -NoProfile -ExecutionPolicy Bypass -File migrate.ps1 -src "C:\Users\12696\.foo"
# Flow: robocopy /COPY:DAT -> count verify -> delete source -> create junction -> probe read.
# ASCII only. robocopy /COPYALL needs admin (audit bit); /COPY:DAT is enough for user files.
param([string]$src)
if (-not $src -or -not (Test-Path -LiteralPath $src)) { Write-Output "SRC_NOT_FOUND: $src"; exit 9 }
$item = Get-Item -LiteralPath $src -Force
if ($item.LinkType) { Write-Output "SRC_IS_ALREADY_LINK: $src ($($item.LinkType))"; exit 8 }

$name = Split-Path $src -Leaf
$dst = "D:\cshift\Users\12696\$name"
if (Test-Path -LiteralPath $dst) { Write-Output "DST_EXISTS_ALREADY: $dst"; exit 7 }

Write-Output "MIGRATE $name -> $dst"
robocopy $src $dst /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XJ /NFL /NDL /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Output "COPY_FAILED:$LASTEXITCODE (source intact)"; exit 1 }

$srcCount = @(Get-ChildItem $src -Recurse -File -Force).Count
$dstCount = @(Get-ChildItem $dst -Recurse -File -Force).Count
if ($srcCount -ne $dstCount) { Write-Output "VERIFY_FAILED:$srcCount/$dstCount (both sides intact, manual check)"; exit 2 }

Remove-Item -LiteralPath $src -Recurse -Force
if (Test-Path -LiteralPath $src) { Write-Output "DELETE_FAILED (copy is safe at $dst)"; exit 3 }

New-Item -ItemType Junction -Path $src -Target $dst | Out-Null
$probe = @(Get-ChildItem $src -Force).Count
if ($probe -gt 0) { Write-Output "JUNCTION_OK files=$dstCount"; exit 0 }
Write-Output "JUNCTION_BROKEN (data safe at $dst)"; exit 4
