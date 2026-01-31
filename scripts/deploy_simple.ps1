# Simple deployment script using scp
# Usage: .\deploy_simple.ps1 [server]
# Example: .\deploy_simple.ps1 ubuntu@192.168.54.188
# Password is hardcoded in the script (line 9)
# 
# For auto-installation of PuTTY, use: .\deploy_auto.ps1

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$Password = "123456"  # 默认密码
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Simple Deployment Script" -ForegroundColor Cyan
Write-Host "Excluding: screenshots, __pycache__, logs, etc." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Get password from parameter or use default
if ([string]::IsNullOrEmpty($Password)) {
    $Password = "123456"  # 默认密码
}
Write-Host "Using password authentication" -ForegroundColor Gray
Write-Host ""

# Check if sshpass or PuTTY tools are available
$useSshpass = $false
$usePutty = $false
$plinkPath = $null
$pscpPath = $null

# Check for sshpass
if (Get-Command sshpass -ErrorAction SilentlyContinue) {
    $useSshpass = $true
    Write-Host "Using sshpass for password authentication" -ForegroundColor Green
} elseif (Get-Command wsl -ErrorAction SilentlyContinue) {
    $wslCheck = wsl which sshpass 2>$null
    if ($wslCheck) {
        $useSshpass = $true
        Write-Host "Using sshpass via WSL" -ForegroundColor Green
    }
}

# Check for PuTTY tools (plink/pscp) - they support password in command line
if (-not $useSshpass) {
    $puttyPaths = @(
        "C:\Program Files\PuTTY\plink.exe",
        "C:\Program Files (x86)\PuTTY\plink.exe",
        "$env:USERPROFILE\Downloads\putty\plink.exe",
        "plink.exe"
    )
    
    foreach ($path in $puttyPaths) {
        if (Test-Path $path) {
            $plinkPath = $path
            $pscpPath = $path -replace "plink.exe", "pscp.exe"
            if (Test-Path $pscpPath) {
                $usePutty = $true
                Write-Host "Using PuTTY tools (plink/pscp) for password authentication" -ForegroundColor Green
                break
            }
        }
    }
}

if (-not $useSshpass -and -not $usePutty) {
    Write-Host "Warning: sshpass and PuTTY tools not found!" -ForegroundColor Yellow
    Write-Host "You will need to enter password for each file." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To fix this, choose one:" -ForegroundColor Cyan
    Write-Host "  1. Install PuTTY (recommended for Windows):" -ForegroundColor White
    Write-Host "     Download from: https://www.putty.org/" -ForegroundColor Gray
    Write-Host "     Then use: .\deploy_putty.ps1" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  2. Install sshpass via WSL:" -ForegroundColor White
    Write-Host "     wsl sudo apt-get install sshpass" -ForegroundColor Gray
    Write-Host ""
}

# Update version
Write-Host "Updating version..." -ForegroundColor Yellow
python update_version.py
Write-Host ""

# Deploy code (excluding screenshots and other unnecessary files)
Write-Host "Uploading code to server..." -ForegroundColor Yellow
Write-Host "Server: $Server" -ForegroundColor Cyan
Write-Host "Target: /data/Smart_RTSP_Stream_Manager/" -ForegroundColor Cyan
Write-Host "Excluding: screenshots, __pycache__, .venv, logs, hls, data" -ForegroundColor Gray
Write-Host ""

# Exclude directories
$excludeDirs = @("screenshots", "__pycache__", ".venv", "venv", "env", ".git", ".idea", ".vscode", "hls", "data", "logs", ".pytest_cache", "dist", "build", ".mypy_cache", ".ruff_cache")
$excludeExtensions = @("*.pyc", "*.pyo", "*.pyd", "*.log", "*.log.*", "*.egg-info")

# Get files to upload (excluding screenshots and other directories)
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

# Collect all unique directories that need to be created
$directories = @()
foreach ($file in $files) {
    $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
    $dir = Split-Path $relativePath -Parent
    if ($dir -and $dir -ne "" -and $directories -notcontains $dir) {
        $directories += $dir
    }
}

# Create all directories at once using password
if ($directories.Count -gt 0) {
    Write-Host "Creating directories on server..." -ForegroundColor Yellow
    $dirsToCreate = $directories | ForEach-Object { 
        $unixPath = $_ -replace '\\', '/'
        "/data/Smart_RTSP_Stream_Manager/$unixPath"
    }
    
    # Create directories in one SSH command
    $dirsString = $dirsToCreate -join " "
    
    if ($useSshpass) {
        if (Get-Command sshpass -ErrorAction SilentlyContinue) {
            sshpass -p $Password ssh -o StrictHostKeyChecking=no $Server "mkdir -p $dirsString" 2>$null
        } else {
            wsl sshpass -p $Password ssh -o StrictHostKeyChecking=no $Server "mkdir -p $dirsString" 2>$null
        }
    } elseif ($usePutty) {
        $serverOnly = $Server -replace ".*@", ""
        $userOnly = $Server -replace "@.*", ""
        & $plinkPath -pw $Password -batch "$userOnly@$serverOnly" "mkdir -p $dirsString" 2>$null
    } else {
        ssh -o StrictHostKeyChecking=no $Server "mkdir -p $dirsString" 2>$null
    }
    Write-Host ""
}

$target = "${Server}:/data/Smart_RTSP_Stream_Manager/"
$uploaded = 0
$failed = 0

Write-Host "Uploading files..." -ForegroundColor Yellow
if ($useSshpass -or $usePutty) {
    Write-Host "Using password authentication (no prompts needed)" -ForegroundColor Green
} else {
    Write-Host "Warning: Will prompt for password for each file" -ForegroundColor Yellow
    Write-Host "Consider installing PuTTY or sshpass to avoid this" -ForegroundColor Yellow
}
Write-Host ""

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
    } elseif ($usePutty) {
        & $pscpPath -pw $Password -batch "$($file.FullName)" $remotePath 2>$null
    } else {
        scp "$($file.FullName)" $remotePath 2>$null
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
    Write-Host "   2. Go to project: cd /data/Smart_RTSP_Stream_Manager"
    Write-Host "   3. Run restart: sudo ./deploy_and_start.sh"
    Write-Host ""
} else {
    Write-Host "Upload completed with some failures" -ForegroundColor Yellow
    Write-Host "Uploaded: $uploaded files" -ForegroundColor Green
    Write-Host "Failed: $failed files" -ForegroundColor Red
    Write-Host "Please check the failed files above" -ForegroundColor Yellow
}
