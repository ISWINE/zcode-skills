# migrate.ps1 - Junction migration to data-drive farm (cold data only!)
# Usage (elevated NOT required): powershell -NoProfile -ExecutionPolicy Bypass -File migrate.ps1 -src "C:\Users\<u>\.foo" [-dst "E:\farm\<name>"]
# Flow: robocopy /COPY:DAT -> count verify -> delete source -> create junction -> probe read.
# ASCII only. robocopy /COPYALL needs admin (audit bit); /COPY:DAT is enough for user files.
# dst default: largest non-system fixed NTFS volume \cshift\Users\<current user>\<name> (portable).
param([string]$src, [string]$dst)
if (-not $src -or -not (Test-Path -LiteralPath $src)) { Write-Output "SRC_NOT_FOUND: $src"; exit 9 }
$item = Get-Item -LiteralPath $src -Force
if ($item.LinkType) { Write-Output "SRC_IS_ALREADY_LINK: $src ($($item.LinkType))"; exit 8 }

$name = Split-Path $src -Leaf
if (-not $dst) {
  $vol = Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' |
         Where-Object { $_.DeviceID -ne $env:SystemDrive -and $_.FileSystem -eq 'NTFS' } |
         Sort-Object Size -Descending | Select-Object -First 1
  if (-not $vol) { Write-Output 'NO_NTFS_DATA_DRIVE (pass -dst explicitly)'; exit 6 }
  $dst = "{0}\cshift\Users\{1}\{2}" -f $vol.DeviceID, $env:USERNAME, $name
}
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
