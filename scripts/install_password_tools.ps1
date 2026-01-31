# Quick install guide for password automation tools

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Password Automation Tools Installation" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Option 1: Install PuTTY (Recommended for Windows)" -ForegroundColor Yellow
Write-Host "  1. Download from: https://www.putty.org/" -ForegroundColor White
Write-Host "  2. Install PuTTY (includes plink.exe and pscp.exe)" -ForegroundColor White
Write-Host "  3. Add to PATH or use full path in script" -ForegroundColor White
Write-Host "  4. Then use: .\deploy_putty.ps1" -ForegroundColor Green
Write-Host ""

Write-Host "Option 2: Install sshpass via WSL" -ForegroundColor Yellow
Write-Host "  1. Open WSL (Windows Subsystem for Linux)" -ForegroundColor White
Write-Host "  2. Run: sudo apt-get update" -ForegroundColor White
Write-Host "  3. Run: sudo apt-get install sshpass" -ForegroundColor White
Write-Host "  4. Then deploy_simple.ps1 will auto-detect it" -ForegroundColor Green
Write-Host ""

Write-Host "Option 3: Install sshpass via Git Bash" -ForegroundColor Yellow
Write-Host "  1. Open Git Bash" -ForegroundColor White
Write-Host "  2. Download sshpass for Windows" -ForegroundColor White
Write-Host "  3. Or use: pacman -S sshpass (if using MSYS2)" -ForegroundColor White
Write-Host ""

Write-Host "Option 4: Use deploy_putty.ps1 (if PuTTY installed)" -ForegroundColor Yellow
Write-Host "  .\deploy_putty.ps1 ubuntu@192.168.54.188 123456" -ForegroundColor Green
Write-Host ""

Write-Host "After installation, deploy scripts will use password automatically!" -ForegroundColor Green
Write-Host ""

