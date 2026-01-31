# File timestamp-based deployment - only upload recently modified files
# Usage: .\deploy_timestamp.ps1 [server] [target_path] [hours]
# Example: .\deploy_timestamp.ps1 ubuntu@192.168.54.188 /data 24
#          (uploads files modified in last 24 hours)

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$TargetDir = "/data",
    [string]$ProjectName = "Smart_RTSP_Stream_Manager",
    [int]$Hours = 24  # Only upload files modified in last N hours
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Timestamp-based Deployment" -ForegroundColor Cyan
Write-Host "Only files modified in last $Hours hours" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Update version first
Write-Host "Step 1: Updating version..." -ForegroundColor Yellow
python update_version.py
Write-Host ""

# Calculate cutoff time
$cutoffTime = (Get-Date).AddHours(-$Hours)

Write-Host "Step 2: Finding files modified since $cutoffTime..." -ForegroundColor Yellow

# Exclude patterns
$excludeDirs = @("__pycache__", ".venv", "venv", "env", ".git", ".idea", ".vscode", "hls", "screenshots", "data", "logs", ".pytest_cache", "dist", "build", ".mypy_cache", ".ruff_cache")
$excludeExtensions = @("*.pyc", "*.pyo", "*.pyd", "*.log", "*.log.*", "*.egg-info")

# Find modified files
$modifiedFiles = Get-ChildItem -Recurse -File | Where-Object {
    # Check if file is modified recently
    $isRecent = $_.LastWriteTime -gt $cutoffTime
    
    # Check if file should be excluded
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
    
    $isRecent -and -not $shouldExclude
}

if ($modifiedFiles.Count -eq 0) {
    Write-Host ""
    Write-Host "No files modified in the last $Hours hours!" -ForegroundColor Yellow
    Write-Host "Use a larger time window or upload all files manually." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($modifiedFiles.Count) files to upload" -ForegroundColor Cyan
Write-Host ""

# Show files to be uploaded
Write-Host "Files to upload:" -ForegroundColor Cyan
foreach ($file in $modifiedFiles) {
    $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
    Write-Host "  - $relativePath" -ForegroundColor Gray
}
Write-Host ""

# Confirm
$confirm = Read-Host "Continue with upload? (Y/N)"
if ($confirm -ne "Y" -and $confirm -ne "y") {
    Write-Host "Upload cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Step 3: Uploading files..." -ForegroundColor Yellow

$uploaded = 0
$failed = 0

foreach ($file in $modifiedFiles) {
    $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
    $remotePath = "${Server}:${TargetDir}/${ProjectName}/$($relativePath -replace '\\', '/')"
    
    # Create parent directory on remote
    $remoteDir = Split-Path $remotePath -Parent
    ssh $Server "mkdir -p `"$remoteDir`"" 2>$null
    
    Write-Host "Uploading: $relativePath" -ForegroundColor Gray
    
    scp "$($file.FullName)" $remotePath 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        $uploaded++
    } else {
        Write-Host "Failed: $relativePath" -ForegroundColor Red
        $failed++
    }
}

Write-Host ""
Write-Host "Upload completed!" -ForegroundColor Green
Write-Host "  Uploaded: $uploaded files" -ForegroundColor Green
if ($failed -gt 0) {
    Write-Host "  Failed: $failed files" -ForegroundColor Red
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "   1. SSH to server: ssh $Server"
Write-Host "   2. Go to project: cd ${TargetDir}/${ProjectName}"
Write-Host "   3. Run restart: sudo ./deploy_and_start.sh"
Write-Host ""

