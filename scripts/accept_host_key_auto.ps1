# Pre-accept host key script (automated version)
# This version uses registry to accept host key automatically
# Usage: .\accept_host_key_auto.ps1 [server] [password]

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$Password = "123456"
)

Write-Host "Accepting host key for $Server..." -ForegroundColor Yellow
Write-Host ""

$serverOnly = $Server -replace ".*@", ""
$userOnly = $Server -replace "@.*", ""

# Use plink with -hostkey to accept automatically
# The host key fingerprint from the error message
$hostKey = "ssh-ed25519 255 SHA256:96XH0hTWHcLyO+9n6CWRX93wxxEB6BbRzJSws0cuY3c"

Write-Host "Adding host key to PuTTY cache..." -ForegroundColor Cyan

# Use plink with -hostkey parameter to accept the key
& "C:\Program Files\PuTTY\plink.exe" -pw $Password -hostkey $hostKey "$userOnly@$serverOnly" "echo 'Host key accepted'" 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Host key accepted and cached!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Now you can use deploy scripts without prompts:" -ForegroundColor Cyan
    Write-Host "  .\deploy_putty.ps1 ubuntu@192.168.54.188 123456" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to accept host key automatically" -ForegroundColor Red
    Write-Host "Please run the interactive version:" -ForegroundColor Yellow
    Write-Host "  .\accept_host_key.ps1 ubuntu@192.168.54.188 123456" -ForegroundColor White
    Write-Host "Then type 'y' when prompted" -ForegroundColor White
}

Write-Host ""

