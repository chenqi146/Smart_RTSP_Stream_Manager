# Simple deployment with password (using plink/pscp from PuTTY)
# This version uses PuTTY tools which support password in command line
# Download PuTTY: https://www.putty.org/

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$Password = "123456",
    [string]$TargetDir = "/data",
    [string]$ProjectName = "Smart_RTSP_Stream_Manager"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment Script (PuTTY Version)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if plink/pscp are available
$plinkPath = $null
$pscpPath = $null

# Check common locations
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
            break
        }
    }
}

if (-not $plinkPath -or -not (Test-Path $pscpPath)) {
    Write-Host "Error: PuTTY tools (plink/pscp) not found!" -ForegroundColor Red
    Write-Host "Please download PuTTY from: https://www.putty.org/" -ForegroundColor Yellow
    Write-Host "Or add PuTTY to your PATH" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Alternative: Use deploy_with_password.ps1 with sshpass" -ForegroundColor Yellow
    exit 1
}

Write-Host "Using PuTTY tools: $plinkPath" -ForegroundColor Green
Write-Host ""

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

# Collect directories
$directories = @()
foreach ($file in $files) {
    $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
    $dir = Split-Path $relativePath -Parent
    if ($dir -and $dir -ne "" -and $directories -notcontains $dir) {
        $directories += $dir
    }
}

# Create directories
if ($directories.Count -gt 0) {
    Write-Host "Creating directories..." -ForegroundColor Yellow
    $dirsToCreate = $directories | ForEach-Object { 
        $unixPath = $_ -replace '\\', '/'
        "${TargetDir}/${ProjectName}/$unixPath"
    }
    $dirsString = $dirsToCreate -join " "
    
    # Extract server and path
    $serverOnly = $Server -replace ".*@", ""
    $userOnly = $Server -replace "@.*", ""
    
    # First, accept host key by connecting once (this will cache the key)
    Write-Host "Accepting host key (first time only)..." -ForegroundColor Gray
    $null = & $plinkPath -pw $Password "$userOnly@$serverOnly" "echo 'Host key accepted'" 2>&1
    
    & $plinkPath -pw $Password -batch "$userOnly@$serverOnly" "mkdir -p $dirsString" 2>$null
    Write-Host ""
}

# Upload files
Write-Host "Uploading files..." -ForegroundColor Yellow
$uploaded = 0
$failed = 0

foreach ($file in $files) {
    $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
    $remotePath = "${TargetDir}/${ProjectName}/$($relativePath -replace '\\', '/')"
    
    Write-Host "Uploading: $relativePath" -ForegroundColor Gray
    
    # pscp syntax: pscp -pw password -batch -unsafe source destination
    # Extract server info
    $serverOnly = $Server -replace ".*@", ""
    $userOnly = $Server -replace "@.*", ""
    $fullRemotePath = "$userOnly@$serverOnly`:$remotePath"
    
    # Build command arguments properly
    $localFile = $file.FullName
    
    # Execute pscp - need to handle paths with spaces
    $result = & $pscpPath -pw $Password -batch -unsafe $localFile $fullRemotePath 2>&1
    
    # Check exit code
    if ($LASTEXITCODE -eq 0) {
        $uploaded++
    } else {
        Write-Host "Failed: $relativePath (Error: $result)" -ForegroundColor Red
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

