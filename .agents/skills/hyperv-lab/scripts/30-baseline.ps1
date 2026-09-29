# ============================================================
#  30-baseline : pristine checkpoint (base image) + full system
#  report. Run elevated via 30-baseline.bat. Safe to re-run.
#    1. guest report over ssh (if VM running)
#    2. host-side Hyper-V + network config dump
#    3. clean shutdown -> repoint seed DVD -> remove stale dirs
#    4. offline checkpoint baseline-clean-<stamp>
#    5. write <LabRoot>\reports\lab-report-<stamp>.md + receipt
#  Log: <LabRoot>\logs\30-baseline.log
# ============================================================
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'config.ps1')
New-Item -ItemType Directory -Path $LogDir, $ReportDir -Force | Out-Null
Start-Transcript -Path (Join-Path $LogDir '30-baseline.log') -Append
$stamp = Get-Date -Format 'yyyyMMdd-HHmm'

try {
    if (-not (Get-Command Get-VM -ErrorAction SilentlyContinue)) { throw 'Hyper-V module not available' }
    $vmObj = Get-VM -Name $VmName -ErrorAction SilentlyContinue
    if (-not $vmObj) { throw "VM '$VmName' not found. Run 20 first." }

    $L = New-Object System.Collections.Generic.List[string]
    $L.Add("# lab system report - $stamp")
    $L.Add('')

    # ---- 1. guest report (needs VM running) ----
    $L.Add('## guest (Ubuntu, read-only facts)')
    $L.Add('```')
    if ($vmObj.State -eq 'Running') {
        # native stderr isolated via cmd /c (PS 5.1 + EAP=Stop pitfall)
        $guest = $null
        foreach ($try in 1..3) {
            $guest = cmd /c "ssh -o BatchMode=yes -o ConnectTimeout=8 $GuestUser bash /home/$GuestUser/guest-report.sh 2>nul"
            if ($guest) { break }
            Start-Sleep -Seconds 5
        }
        if ($guest) { $guest | ForEach-Object { $L.Add($_) } }
        else { $L.Add('(ssh not reachable - guest section skipped)') }
    } else { $L.Add('(VM was off - guest section skipped; start VM and re-run for live data)') }
    $L.Add('```')
    $L.Add('')

    # ---- 2. host config dump ----
    $L.Add('## host (Hyper-V + network)')
    $L.Add('```')
    $L.Add(("vm name       : {0} (Gen{1}, state {2})" -f $vmObj.Name, $vmObj.Generation, $vmObj.State))
    $L.Add(("cpu           : {0} vCPU (nested virt exposed)" -f $vmObj.ProcessorCount))
    $mem = Get-VMMemory -VMName $VmName
    # object properties are Minimum/Startup/Maximum (bytes) - verified against the
    # module's own Hyper-V.Format.ps1xml; only the Set-VMMemory PARAMETERS carry the Bytes suffix
    $L.Add(("memory        : dynamic {0}-{1} MB, startup {2} MB (dynamicEnabled={3})" -f [int]($mem.Minimum/1MB), [int]($mem.Maximum/1MB), [int]($mem.Startup/1MB), $mem.DynamicMemoryEnabled))
    $L.Add(("autostart     : {0} (never starts with Windows)" -f $vmObj.AutomaticStartAction))
    $nic = Get-VMNetworkAdapter -VMName $VmName
    $L.Add(("nic           : switch {0}, mac {1}, ip {2}" -f $nic.SwitchName, $nic.MacAddress, ($nic.IPAddresses -join ' ')))
    $sw = Get-VMSwitch -Name $SwitchName -ErrorAction SilentlyContinue
    if ($sw) { $L.Add(("switch        : {0} ({1})" -f $sw.Name, $sw.SwitchType)) }
    $nat = Get-NetNat -Name $SwitchName -ErrorAction SilentlyContinue
    if ($nat) { $L.Add(("nat           : {0} (outbound internet, inbound blocked)" -f $nat.InternalIPInterfaceAddressPrefix)) }
    if (Test-Path $VhdPath) { $L.Add(("vhd           : {0:N2} GB used / {1} GB cap (dynamic)" -f ((Get-Item $VhdPath).Length/1GB), $VhdCapGB)) }
    $L.Add(("golden source : {0}" -f $GoldenVhd))
    $existingCk = Get-VMSnapshot -VMName $VmName -ErrorAction SilentlyContinue
    if ($existingCk) { $existingCk | ForEach-Object { $L.Add(("checkpoint     : {0}  ({1})" -f $_.Name, $_.CreationTime)) } }
    else { $L.Add('checkpoint     : none yet') }
    $L.Add('```')
    $L.Add('')
    $L.Add('## interop')
    $L.Add('```')
    $L.Add("ssh alias     : ssh $GuestUser  (key $SshKeyPath)")
    $hostsLine = Select-String -Path "$env:windir\System32\drivers\etc\hosts" -Pattern "$VmIP\s+lab"
    $L.Add(("hosts entry   : {0}" -f $(if ($hostsLine) { $hostsLine.Line.Trim() } else { 'MISSING' })))
    $L.Add('file copy     : lab.ps1 push <file>   (Hyper-V Guest Service)')
    $L.Add('```')
    $L.Add('')

    # ---- 3. clean shutdown (offline checkpoint = compact, no memory state) ----
    if ($vmObj.State -eq 'Running') {
        Write-Output 'Stopping VM for an offline baseline checkpoint ...'
        Stop-VM -Name $VmName
        $deadline = (Get-Date).AddSeconds(120)
        while (((Get-VM -Name $VmName).State -ne 'Off') -and ((Get-Date) -lt $deadline)) { Start-Sleep -Seconds 3 }
    }
    if ((Get-VM -Name $VmName).State -ne 'Off') { throw 'VM did not stop within 120s' }
    Write-Output '[OK] VM is off'

    # repoint seed DVD to config path (also releases locks on old paths)
    foreach ($d in (Get-VMDvdDrive -VMName $VmName)) {
        if ($d.Path -and $d.Path -ne $SeedIso) {
            Set-VMDvdDrive -VMName $VmName -ControllerNumber $d.ControllerNumber -ControllerLocation $d.ControllerLocation -Path $SeedIso
            Write-Output "[OK] seed DVD repointed to $SeedIso"
        }
    }
    $oldSeed = Join-Path $LabRoot 'seed-cloud'
    if (Test-Path $oldSeed) {
        Remove-Item $oldSeed -Recurse -Force -ErrorAction SilentlyContinue
        if (-not (Test-Path $oldSeed)) { Write-Output '[OK] stale folder removed: seed-cloud' }
        else { Write-Output '[WARN] could not remove stale seed-cloud (locked?), remove later' }
    }

    # ---- 4. the baseline checkpoint ----
    $ckName = "baseline-clean-$stamp"
    Checkpoint-VM -Name $VmName -SnapshotName $ckName
    Write-Output "[OK] baseline checkpoint: $ckName (VM left OFF - start with lab.ps1 start)"

    # ---- 5. finish report ----
    $L.Add('## baseline')
    $L.Add('')
    $L.Add("- checkpoint : **$ckName** (offline, taken $stamp)")
    $L.Add("- restore    : powershell -File $LabRoot\lab.ps1 restore $ckName")
    $reportPath = Join-Path $ReportDir ("lab-report-$stamp.md")
    $L | Set-Content -Path $reportPath -Encoding ASCII
    Write-Output "[OK] report: $reportPath"
    Write-Output ''
    Write-Output '================ DONE ================'
    Write-Output (" baseline : " + $ckName)
    Write-Output (" report   : " + $reportPath)
    Write-Output '======================================'
    Read-Host 'Press Enter to close this window'
}
catch {
    Write-Output "FAILED: $_"
    Write-Output "Full log: $LogDir\30-baseline.log"
    Read-Host 'Press Enter to close this window'
    exit 1
}
finally { Stop-Transcript | Out-Null }
