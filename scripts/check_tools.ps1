# Check for password automation tools
# Usage: .\check_tools.ps1

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Checking Password Automation Tools" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$foundTools = @()

# Check sshpass
Write-Host "Checking sshpass..." -ForegroundColor Yellow
if (Get-Command sshpass -ErrorAction SilentlyContinue) {
    $sshpassPath = (Get-Command sshpass).Source
    Write-Host "  ✓ Found: $sshpassPath" -ForegroundColor Green
    $foundTools += "sshpass"
} elseif (Get-Command wsl -ErrorAction SilentlyContinue) {
    $wslCheck = wsl which sshpass 2>$null
    if ($wslCheck) {
        Write-Host "  ✓ Found: sshpass via WSL" -ForegroundColor Green
        $foundTools += "sshpass (WSL)"
    } else {
        Write-Host "  ✗ Not found" -ForegroundColor Red
    }
} else {
    Write-Host "  ✗ Not found" -ForegroundColor Red
}
Write-Host ""

# Check PuTTY tools
Write-Host "Checking PuTTY tools (plink/pscp)..." -ForegroundColor Yellow
$puttyPaths = @(
    "C:\Program Files\PuTTY\plink.exe",
    "C:\Program Files (x86)\PuTTY\plink.exe",
    "$env:USERPROFILE\Downloads\putty\plink.exe",
    "plink.exe"
)

$plinkFound = $false
$pscpFound = $false
$plinkPath = $null
$pscpPath = $null

foreach ($path in $puttyPaths) {
    if (Test-Path $path) {
        $plinkPath = $path
        $pscpPath = $path -replace "plink.exe", "pscp.exe"
        if (Test-Path $pscpPath) {
            Write-Host "  ✓ Found plink: $plinkPath" -ForegroundColor Green
            Write-Host "  ✓ Found pscp: $pscpPath" -ForegroundColor Green
            $plinkFound = $true
            $pscpFound = $true
            $foundTools += "PuTTY"
            break
        }
    }
}

# Also check if plink/pscp are in PATH
if (-not $plinkFound) {
    if (Get-Command plink -ErrorAction SilentlyContinue) {
        $plinkPath = (Get-Command plink).Source
        Write-Host "  ✓ Found plink in PATH: $plinkPath" -ForegroundColor Green
        $plinkFound = $true
    }
    if (Get-Command pscp -ErrorAction SilentlyContinue) {
        $pscpPath = (Get-Command pscp).Source
        Write-Host "  ✓ Found pscp in PATH: $pscpPath" -ForegroundColor Green
        $pscpFound = $true
    }
    if ($plinkFound -and $pscpFound) {
        $foundTools += "PuTTY"
    }
}

if (-not ($plinkFound -and $pscpFound)) {
    Write-Host "  ✗ Not found" -ForegroundColor Red
}
Write-Host ""

# Summary
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

if ($foundTools.Count -gt 0) {
    Write-Host "✓ Found tools: $($foundTools -join ', ')" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can use:" -ForegroundColor Cyan
    if ($foundTools -contains "PuTTY") {
        Write-Host "  .\deploy_putty.ps1 ubuntu@192.168.54.188 123456" -ForegroundColor Green
    }
    if ($foundTools -contains "sshpass" -or $foundTools -contains "sshpass (WSL)") {
        Write-Host "  .\deploy_simple.ps1 ubuntu@192.168.54.188" -ForegroundColor Green
    }
} else {
    Write-Host "✗ No password automation tools found" -ForegroundColor Red
    Write-Host ""
    Write-Host "To install:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Option 1: Install PuTTY (Recommended)" -ForegroundColor Cyan
    Write-Host "  1. Download: https://www.putty.org/" -ForegroundColor White
    Write-Host "  2. Install PuTTY" -ForegroundColor White
    Write-Host "  3. Then use: .\deploy_putty.ps1" -ForegroundColor Green
    Write-Host ""
    Write-Host "Option 2: Install sshpass via WSL" -ForegroundColor Cyan
    Write-Host "  1. Open WSL: wsl" -ForegroundColor White
    Write-Host "  2. Run: sudo apt-get install sshpass" -ForegroundColor White
    Write-Host "  3. Then use: .\deploy_simple.ps1" -ForegroundColor Green
    Write-Host ""
}

Write-Host ""

