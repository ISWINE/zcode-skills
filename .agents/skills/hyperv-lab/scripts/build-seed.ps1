# Build a cloud-init NoCloud seed ISO with built-in IMAPI2 (no third-party tools).
#   .\build-seed.ps1                       -> <LabRoot>\seed\cidata.iso  (default)
#   .\build-seed.ps1 D:\some\seed-dir      -> that dir's cidata.iso
# All files in the seed dir (except *.iso) go into the ISO root. Volume label = CIDATA.
# After editing seed files, re-run this, then re-run 20-create-vm.ps1 on a fresh disk.
param(
    [string] $SeedDirectory = ''
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'config.ps1')
if (-not $SeedDirectory) { $SeedDirectory = $SeedDir }
$IsoPath = Join-Path $SeedDirectory 'cidata.iso'

$files = Get-ChildItem -Path $SeedDirectory -File | Where-Object { $_.Extension -ne '.iso' }
if (-not $files) { throw "no seed files found in $SeedDirectory" }

$src = @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
public static class IsoWriter {
    public static void WriteIso(object imageStream, string path) {
        IStream stream = (IStream)imageStream;
        using (FileStream fs = new FileStream(path, FileMode.Create, FileAccess.Write)) {
            byte[] buf = new byte[32768];
            IntPtr pcbRead = Marshal.AllocHGlobal(sizeof(int));
            try {
                while (true) {
                    stream.Read(buf, buf.Length, pcbRead);
                    int read = Marshal.ReadInt32(pcbRead);
                    if (read <= 0) break;
                    fs.Write(buf, 0, read);
                }
            } finally { Marshal.FreeHGlobal(pcbRead); }
        }
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$stage = Join-Path $SeedDirectory '.iso-root'
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
$null = New-Item -ItemType Directory -Path $stage
$files | ForEach-Object { Copy-Item $_.FullName $stage }

if (Test-Path $IsoPath) { Remove-Item $IsoPath -Force }
$fsi = New-Object -ComObject IMAPI2FS.MsftFileSystemImage
$fsi.VolumeName = 'CIDATA'
$fsi.FileSystemsToCreate = 3
$fsi.FreeMediaBlocks = 100000
$fsi.Root.AddTree($stage, $false)
$image = $fsi.CreateResultImage()
[IsoWriter]::WriteIso($image.ImageStream, $IsoPath)
Remove-Item $stage -Recurse -Force

Write-Output ("OK {0} bytes -> {1} (files: {2})" -f (Get-Item $IsoPath).Length, $IsoPath, (($files | ForEach-Object Name) -join ', '))
