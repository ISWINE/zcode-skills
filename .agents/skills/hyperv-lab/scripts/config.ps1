# ============================================================
#  lab environment - single source of truth
#  All scripts read paths/names here. To move or clone the lab,
#  edit this file only. Keep this file pure ASCII (PS 5.1 rule).
# ============================================================
$LabRoot    = 'D:\lab'
$VmName     = 'lab'
$GuestUser  = 'lab'
$SwitchName = 'LabNAT'
$Subnet     = '192.168.100.0/24'
$HostIP     = '192.168.100.1'
$VmIP       = '192.168.100.10'
$VmMac      = '00155D101000'    # MUST match seed/network-config macaddress
$VhdCapGB   = 40
$VhdPath    = Join-Path $LabRoot 'vm\lab.vhdx'
$GoldenVhd  = Join-Path $LabRoot 'images\lab-golden.vhd'
$GoldenQcow = Join-Path $LabRoot 'images\noble-server-cloudimg-amd64.qcow2'
$SeedIso    = Join-Path $LabRoot 'seed\cidata.iso'
$SeedDir    = Join-Path $LabRoot 'seed'
$SshKeyPath = Join-Path $LabRoot 'ssh\lab_key'
$LogDir     = Join-Path $LabRoot 'logs'
$ReportDir  = Join-Path $LabRoot 'reports'
