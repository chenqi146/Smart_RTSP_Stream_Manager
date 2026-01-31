# SSH Key Setup Guide for Windows PowerShell
# This will help you avoid entering password for each file upload

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "SSH Key Setup Guide" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 1: Generate SSH key (if you don't have one)" -ForegroundColor Yellow
Write-Host "Run this command:" -ForegroundColor Cyan
Write-Host "  ssh-keygen -t rsa -b 4096 -C `"your_email@example.com`"" -ForegroundColor White
Write-Host "  (Press Enter to accept default location, set passphrase if desired)" -ForegroundColor Gray
Write-Host ""

Write-Host "Step 2: Copy your public key to the server" -ForegroundColor Yellow
Write-Host "Run this command (replace SERVER with your server address):" -ForegroundColor Cyan
Write-Host "  type $env:USERPROFILE\.ssh\id_rsa.pub | ssh SERVER `"mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys`"" -ForegroundColor White
Write-Host ""
Write-Host "Or use ssh-copy-id (if available):" -ForegroundColor Cyan
Write-Host "  ssh-copy-id SERVER" -ForegroundColor White
Write-Host ""

Write-Host "Step 3: Test SSH connection" -ForegroundColor Yellow
Write-Host "Run this command:" -ForegroundColor Cyan
Write-Host "  ssh SERVER" -ForegroundColor White
Write-Host "  (You should be able to connect without password)" -ForegroundColor Gray
Write-Host ""

Write-Host "After setup, deploy scripts will not ask for password!" -ForegroundColor Green
Write-Host ""

