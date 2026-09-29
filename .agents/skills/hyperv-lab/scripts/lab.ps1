# ============================================================
#  Lab VM daily control.  No admin needed (after one
#  sign-out/sign-in following setup step 2).
#  Usage:  powershell -File D:\lab\lab.ps1 <command> [arg]
#    status          VM state, memory, IP, real disk usage
#    start / stop    boot / clean shutdown (NEVER auto-starts)
#    ssh             log into the VM as user 'lab' (key auth)
#    push <file>     copy a host file into /home/lab/ of the VM
#    ck <name>       save checkpoint (snapshot) before risky tests
#    lsck            list checkpoints
#    restore <name>  roll the VM back to a checkpoint
#    rmck <name>     delete a checkpoint
#    report          run the guest system report inside the VM
# ============================================================
param(
    [Parameter(Position=0)] [string] $cmd = 'status',
    [Parameter(Position=1)] [string] $arg1
)
. (Join-Path $PSScriptRoot 'config.ps1')

switch ($cmd.ToLower()) {

    'start'   { Start-VM -Name $VmName; 'VM starting... (first boot ~30s; then: ssh lab)' }

    'stop'    { Stop-VM -Name $VmName; 'VM stopped. (memory freed instantly, nothing runs in background)' }

    'status'  {
        Get-VM -Name $VmName | Format-Table Name, State, Uptime, CPUUsage,
            @{n='MemMB';e={[int]($_.MemoryAssigned/1MB)}} -AutoSize
        $ips = (Get-VMNetworkAdapter -VMName $VmName).IPAddresses
        'IP        : ' + ($(if ($ips) { $ips -join ', ' } else { '(booting or off)' }))
        'VHDX used : ' + [math]::Round((Get-Item $VhdPath).Length/1GB,2) + " GB of $VhdCapGB GB cap (grows only as used)"
    }

    'ip'      { (Get-VMNetworkAdapter -VMName $VmName).IPAddresses }

    'ssh'     { ssh $GuestUser }

    'push'    {
        if ($arg1) {
            Copy-VMFile -VMName $VmName -SourcePath $arg1 -DestinationPath "/home/$GuestUser/" -FileSource Host -CreateFullDirectoryPath $true
            "copied into VM /home/$GuestUser/ (make executable there first: chmod +x)"
        } else { 'usage: lab.ps1 push <local-file>' }
    }

    'report'  { ssh $GuestUser "bash /home/$GuestUser/guest-report.sh" }

    'ck'      {
        if ($arg1) { Checkpoint-VM -Name $VmName -SnapshotName $arg1; "checkpoint saved: $arg1" }
        else { 'usage: lab.ps1 ck <name>   (save BEFORE risky experiments)' }
    }

    'lsck'    { Get-VMSnapshot -VMName $VmName | Format-Table Name, SnapshotType, CreationTime -AutoSize }

    'restore' {
        if ($arg1) { Restore-VMCheckpoint -Name $arg1 -VMName $VmName; "VM rolled back to: $arg1" }
        else { 'usage: lab.ps1 restore <name>' }
    }

    'rmck'    {
        if ($arg1) { Remove-VMSnapshot -Name $arg1 -VMName $VmName; "checkpoint deleted: $arg1" }
        else { 'usage: lab.ps1 rmck <name>' }
    }

    default   { "unknown command '$cmd'. available: status start stop ssh push report ck lsck restore rmck" }
}
