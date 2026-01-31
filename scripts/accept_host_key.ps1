# Pre-accept host key script
# Run this once to accept the server's host key
# Usage: .\accept_host_key.ps1 [server] [password]

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$Password = "123456"
)

Write-Host "Accepting host key for $Server..." -ForegroundColor Yellow
Write-Host "You may need to type 'y' to accept the host key" -ForegroundColor Gray
Write-Host ""

$serverOnly = $Server -replace ".*@", ""
$userOnly = $Server -replace "@.*", ""

# Use plink to accept host key (interactive)
& "C:\Program Files\PuTTY\plink.exe" -pw $Password "$userOnly@$serverOnly" "echo 'Host key accepted'"

Write-Host ""
Write-Host "Host key accepted! Now you can use deploy scripts." -ForegroundColor Green

