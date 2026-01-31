# Deployment script with password support
# Usage: .\deploy_with_password.ps1 [server] [password]
# Example: .\deploy_with_password.ps1 ubuntu@192.168.54.188 123456
# Or set environment variable: $env:DEPLOY_PASSWORD = "123456"

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$Password = "",
    [string]$TargetDir = "/data",
    [string]$ProjectName = "Smart_RTSP_Stream_Manager"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment Script (With Password Support)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Get password from parameter, environment variable, or prompt once
if ([string]::IsNullOrEmpty($Password)) {
    if ($env:DEPLOY_PASSWORD) {
        $Password = $env:DEPLOY_PASSWORD
        Write-Host "Using password from environment variable" -ForegroundColor Gray
    } else {
        $securePassword = Read-Host "Enter server password" -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
        $Password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
        Write-Host ""
    }
}

# Update version
Write-Host "Updating version..." -ForegroundColor Yellow
python update_version.py
Write-Host ""

# Exclude directories
$excludeDirs = @("screenshots", "__pycache__", ".venv", "venv", "env", ".git", ".idea", ".vscode", "hls", "data", "logs", ".pytest_cache", "dist", "build", ".mypy_cache", ".ruff_cache")
$excludeExtensions = @("*.pyc", "*.pyo", "*.pyd", "*.log", "*.log.*", "*.egg-info")

# Get files to upload
$files = Get-ChildItem -Recurse -File | Where-Object {
    $shouldExclude = $false
    foreach ($dir in $excludeDirs) {
        if ($_.FullName -like "*\$dir\*") {
            $shouldExclude = $true
            break
        }
    }
    if (-not $shouldExclude) {
        foreach ($ext in $excludeExtensions) {
            if ($_.Name -like $ext) {
                $shouldExclude = $true
                break
            }
        }
    }
    -not $shouldExclude
}

Write-Host "Found $($files.Count) files to upload" -ForegroundColor Cyan
Write-Host ""

# Collect all unique directories
$directories = @()
foreach ($file in $files) {
    $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
    $dir = Split-Path $relativePath -Parent
    if ($dir -and $dir -ne "" -and $directories -notcontains $dir) {
        $directories += $dir
    }
}

# Create directories using sshpass or expect
Write-Host "Creating directories on server..." -ForegroundColor Yellow

# Check if sshpass is available (Linux/WSL/Git Bash)
$useSshpass = $false
if (Get-Command sshpass -ErrorAction SilentlyContinue) {
    $useSshpass = $true
} elseif (Get-Command wsl -ErrorAction SilentlyContinue) {
    # Try WSL sshpass
    $wslCheck = wsl which sshpass 2>$null
    if ($wslCheck) {
        $useSshpass = $true
    }
}

if ($directories.Count -gt 0) {
    $dirsToCreate = $directories | ForEach-Object { 
        $unixPath = $_ -replace '\\', '/'
        "${TargetDir}/${ProjectName}/$unixPath"
    }
    $dirsString = $dirsToCreate -join " "
    
    if ($useSshpass) {
        if (Get-Command sshpass -ErrorAction SilentlyContinue) {
            sshpass -p $Password ssh -o StrictHostKeyChecking=no $Server "mkdir -p $dirsString" 2>$null
        } else {
            wsl sshpass -p $Password ssh -o StrictHostKeyChecking=no $Server "mkdir -p $dirsString" 2>$null
        }
    } else {
        # Use expect-like approach with PowerShell
        $expectScript = @"
spawn ssh -o StrictHostKeyChecking=no $Server "mkdir -p $dirsString"
expect "password:"
send "$Password\r"
expect eof
"@
        # Note: PowerShell doesn't have expect, so we'll use plink or manual
        Write-Host "Note: Creating directories manually (you may need to enter password)" -ForegroundColor Yellow
        ssh -o StrictHostKeyChecking=no $Server "mkdir -p $dirsString" 2>$null
    }
    Write-Host ""
}

# Upload files
Write-Host "Uploading files..." -ForegroundColor Yellow
$target = "${Server}:${TargetDir}/${ProjectName}/"
$uploaded = 0
$failed = 0

foreach ($file in $files) {
    $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
    $remotePath = "${target}$($relativePath -replace '\\', '/')"
    
    Write-Host "Uploading: $relativePath" -ForegroundColor Gray
    
    if ($useSshpass) {
        if (Get-Command sshpass -ErrorAction SilentlyContinue) {
            sshpass -p $Password scp -o StrictHostKeyChecking=no "$($file.FullName)" $remotePath 2>$null
        } else {
            wsl sshpass -p $Password scp -o StrictHostKeyChecking=no "$($file.FullName)" $remotePath 2>$null
        }
    } else {
        # Use plink if available (PuTTY)
        if (Get-Command plink -ErrorAction SilentlyContinue) {
            $plinkCmd = "plink -pw $Password -batch $Server"
            $pscpCmd = "pscp -pw $Password -batch `"$($file.FullName)`" $remotePath"
            Invoke-Expression $pscpCmd 2>$null
        } else {
            # Fallback: regular scp (will prompt for password)
            scp "$($file.FullName)" $remotePath 2>$null
        }
    }
    
    if ($LASTEXITCODE -eq 0) {
        $uploaded++
    } else {
        Write-Host "Failed: $relativePath" -ForegroundColor Red
        $failed++
    }
}

Write-Host ""
if ($failed -eq 0) {
    Write-Host "Deployment completed!" -ForegroundColor Green
    Write-Host "Uploaded: $uploaded files" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "   1. SSH to server: ssh $Server"
    Write-Host "   2. Go to project: cd ${TargetDir}/${ProjectName}"
    Write-Host "   3. Run restart: sudo ./deploy_and_start.sh"
} else {
    Write-Host "Upload completed with some failures" -ForegroundColor Yellow
    Write-Host "Uploaded: $uploaded files" -ForegroundColor Green
    Write-Host "Failed: $failed files" -ForegroundColor Red
}

# Clear password from memory
$Password = $null
$securePassword = $null

