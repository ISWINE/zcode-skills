# ============================================================
#  Deploy step 2/2 : network + VM + silent golden-image deploy
#  Run elevated (20-run.bat handles UAC). Idempotent: safe to re-run.
#  All paths/names come from config.ps1 (single source of truth).
#  Log: <LabRoot>\logs\20-create-vm.log
#
#  What this does (enterprise-style, no installer ever runs):
#    golden cloud image -> dynamic VHDX -> cloud-init seed ->
#    boot -> poll SSH -> verified receipt (VERIFIED)
# ============================================================
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'config.ps1')
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
Start-Transcript -Path (Join-Path $LogDir '20-create-vm.log') -Append

try {
    # ---- 0. prechecks ----
    if (-not (Get-Command New-VM -ErrorAction SilentlyContinue)) {
        throw 'Hyper-V module not found. Run 10-enable-hyperv.bat first, then REBOOT, then run this again.'
    }
    if (-not (Test-Path $GoldenVhd)) {
        throw "Golden image not found: $GoldenVhd (rebuild: qemu-img convert -f qcow2 -O vpc $GoldenQcow -> see skill docs)"
    }
    if (-not (Test-Path $SeedIso)) { throw "Cloud seed not found: $SeedIso (run build-seed.ps1)" }
    $vmState = (Get-VM -Name $VmName -ErrorAction SilentlyContinue).State
    if ($vmState -eq 'Running') { throw "VM is running. Stop it first:  powershell -File $LabRoot\lab.ps1 stop" }

    $clash = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
             Where-Object { $_.IPAddress -like '192.168.100.*' -and $_.InterfaceAlias -notlike "*$SwitchName*" }
    if ($clash) { throw "Subnet conflict: adapter '$($clash[0].InterfaceAlias)' already uses 192.168.100.x. Change `$Subnet in config.ps1." }

    # ---- 1. current user -> Hyper-V Administrators (so lab.ps1 works without admin) ----
    try {
        $grp = Get-LocalGroup -Name 'Hyper-V Administrators' -ErrorAction Stop
        $me  = "$env:USERDOMAIN\$env:USERNAME"
        if (-not ($grp.Members -contains $me)) {
            Add-LocalGroupMember -Group 'Hyper-V Administrators' -Member $env:USERNAME
            Write-Output "[OK] '$env:USERNAME' added to Hyper-V Administrators (effective after next sign-out/sign-in)"
        } else { Write-Output '[SKIP] already member of Hyper-V Administrators' }
    } catch { Write-Output "[WARN] group step skipped: $_" }

    # ---- 2. internal switch + host IP + NAT (isolated from home LAN, outbound via NAT) ----
    if (-not (Get-VMSwitch -Name $SwitchName -ErrorAction SilentlyContinue)) {
        New-VMSwitch -Name $SwitchName -SwitchType Internal | Out-Null
        Write-Output "[OK] internal switch '$SwitchName' created"
    } else { Write-Output '[SKIP] switch exists' }

    $vnic = Get-NetAdapter -Name "vEthernet ($SwitchName)" -ErrorAction SilentlyContinue
    if (-not $vnic) { throw 'vEthernet adapter not found after switch creation' }
    if (-not (Get-NetIPAddress -InterfaceIndex $vnic.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue)) {
        New-NetIPAddress -IPAddress $HostIP -PrefixLength 24 -InterfaceIndex $vnic.ifIndex | Out-Null
        Write-Output "[OK] host IP $HostIP/24 set"
    } else { Write-Output '[SKIP] host IP exists' }

    if (-not (Get-NetNat -Name $SwitchName -ErrorAction SilentlyContinue)) {
        New-NetNat -Name $SwitchName -InternalIPInterfaceAddressPrefix $Subnet | Out-Null
        Write-Output "[OK] NAT created for $Subnet (VM reaches internet, nobody outside reaches the VM)"
    } else { Write-Output '[SKIP] NAT exists' }

    # ---- 3. disk: golden image -> dynamic VHDX (cloud-init grows root fs on first boot) ----
    if (-not (Test-Path $VhdPath)) {
        Convert-VHD -Path $GoldenVhd -DestinationPath $VhdPath -VHDType Dynamic
        Resize-VHD -Path $VhdPath -SizeBytes ($VhdCapGB.ToString() + 'GB')
        Write-Output "[OK] golden image -> dynamic VHDX (${VhdCapGB}GB cap, grows only as used)"
    } else { Write-Output '[SKIP] VHDX exists (delete it for a fresh redeploy)' }

    # ---- 4. VM ----
    if (-not (Get-VM -Name $VmName -ErrorAction SilentlyContinue)) {
        New-VM -Name $VmName -Generation 2 -Path (Join-Path $LabRoot 'vm') -MemoryStartupBytes 1GB -VHDPath $VhdPath -SwitchName $SwitchName | Out-Null
        Write-Output '[OK] Gen2 VM created'
    } else { Write-Output '[SKIP] VM exists' }

    # ---- 4b. settings (param names verified on this module build:
    #      Set-VM uses -MemoryMinimumBytes/-MemoryMaximumBytes,
    #      Set-VMNetworkAdapter uses -StaticMacAddress) ----
    try {
        Set-VM -Name $VmName -DynamicMemory -MemoryMinimumBytes 512MB -MemoryMaximumBytes 4096MB -MemoryStartupBytes 1024MB
        Set-VM -Name $VmName -ProcessorCount 2
        Set-VM -Name $VmName -AutomaticStartAction Nothing -AutomaticStopAction ShutDown
        Set-VM -Name $VmName -AutomaticCheckpointsEnabled $false -CheckpointType Standard
        Set-VMProcessor -VMName $VmName -ExposeVirtualizationExtensions $true
        Write-Output '[OK] 2 vCPU / dynamic memory 0.5-4GB / autostart=NEVER / shutdown=clean'
    } catch { Write-Output "[WARN] cosmetic VM settings skipped: $_" }

    # ---- 5. NIC static MAC (must match seed network-config) + guest file copy ----
    Set-VMNetworkAdapter -VMName $VmName -StaticMacAddress $VmMac
    Enable-VMIntegrationService -VMName $VmName -Name 'Guest Service Interface' -ErrorAction SilentlyContinue
    Write-Output "[OK] NIC MAC $VmMac + guest file-copy service"

    # ---- 6. cloud-init seed DVD ----
    Get-VMDvdDrive -VMName $VmName | Remove-VMDvdDrive
    Add-VMDvdDrive -VMName $VmName -Path $SeedIso
    Write-Output '[OK] cloud-init seed attached (CIDATA)'

    # ---- 7. boot order disk->DVD, secure boot on (Ubuntu shim is signed) ----
    $hd = Get-VMHardDiskDrive -VMName $VmName
    Set-VMFirmware -VMName $VmName -FirstBootDevice $hd
    Set-VMFirmware -VMName $VmName -EnableSecureBoot On -SecureBootTemplate 'MicrosoftUEFICertificateAuthority'
    Write-Output '[OK] boot order disk->DVD, secure boot ON (UEFI CA template)'

    # ---- 8. hosts entry so 'lab' resolves everywhere ----
    $hostsFile = "$env:windir\System32\drivers\etc\hosts"
    if (-not (Select-String -Path $hostsFile -Pattern ("\s" + $VmIP + "\s+lab\s") -Quiet)) {
        Add-Content -Path $hostsFile -Value "`r`n$VmIP    lab    # D:\lab VM"
        Write-Output "[OK] hosts entry added: $VmIP  lab"
    } else { Write-Output '[SKIP] hosts entry exists' }

    # ---- 9. boot + verify ----
    Start-VM -Name $VmName
    Write-Output '[OK] VM started - silent deploy: first boot applies cloud-init config (2-5 min)'

    # PS 5.1 + $ErrorActionPreference='Stop' turns ANY native stderr line into a
    # terminating error (e.g. the harmless "Warning: Permanently added ...").
    # So: purge stale host key, pre-seed known_hosts, and run ssh via cmd /c.
    cmd /c "ssh-keygen -R $VmIP 2>nul" | Out-Null
    $ks = cmd /c "ssh-keyscan -T 5 $VmIP 2>nul"
    if ($ks) { Add-Content -Path "$env:USERPROFILE\.ssh\known_hosts" -Value $ks }

    $up = $false
    $deadline = (Get-Date).AddMinutes(8)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 5
        $c = New-Object System.Net.Sockets.TcpClient
        try { if ($c.ConnectAsync($VmIP, 22).Wait(1500) -and $c.Connected) { $up = $true } } catch {}
        finally { $c.Dispose() }
        Write-Host -NoNewline '.'
        if ($up) { break }
    }
    Write-Host ''
    if (-not $up) {
        Write-Output "WARN: SSH not reachable within 8 min. Open console:  vmconnect . $VmName   and check."
        Read-Host 'Press Enter to close this window'
        return
    }
    Write-Output "[OK] SSH port up on $VmIP - waiting for cloud-init to finish user setup ..."
    $sshOk = $false
    $deadline2 = (Get-Date).AddMinutes(5)
    while ((Get-Date) -lt $deadline2) {
        $r = cmd /c "ssh -o BatchMode=yes -o ConnectTimeout=5 $GuestUser echo CLOUD_INIT_DONE 2>nul"
        if ($r -match 'CLOUD_INIT_DONE') { $sshOk = $true; break }
        Start-Sleep -Seconds 10
    }
    if ($sshOk) {
        Write-Output ''
        Write-Output '============================================================'
        Write-Output ' VERIFIED: deploy complete, key-based SSH works.'
        Write-Output " From any terminal:    ssh $GuestUser"
        Write-Output " Baseline+report:      $LabRoot\30-baseline.bat   (one UAC click)"
        Write-Output " Daily control:        powershell -File $LabRoot\lab.ps1 status"
        Write-Output " VM console (rarely needed):  vmconnect . $VmName"
        Write-Output '============================================================'
    } else {
        Write-Output 'WARN: SSH port up but login not ready after 5 min. Wait 2-3 min then:  ssh lab'
    }
    Read-Host 'Press Enter to close this window'
}
catch {
    Write-Output ''
    Write-Output "FAILED: $_"
    Write-Output "Full log: $LogDir\20-create-vm.log"
    Read-Host 'Press Enter to close this window'
    exit 1
}
finally { Stop-Transcript | Out-Null }
