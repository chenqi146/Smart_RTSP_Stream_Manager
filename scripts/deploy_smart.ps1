# Smart deployment script - only upload changed files
# Usage: .\deploy_smart.ps1 [server] [target_path]
# Example: .\deploy_smart.ps1 ubuntu@192.168.54.188 /data

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$TargetDir = "/data",
    [string]$ProjectName = "Smart_RTSP_Stream_Manager"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Smart Deployment (Only Changed Files)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Update version first
Write-Host "Step 1: Updating version..." -ForegroundColor Yellow
python update_version.py
Write-Host ""

# Check if rsync is available (best option)
$useRsync = $false
if (Get-Command rsync -ErrorAction SilentlyContinue) {
    $useRsync = $true
    Write-Host "Using rsync (fastest, only syncs changed files)" -ForegroundColor Green
} elseif (Get-Command wsl -ErrorAction SilentlyContinue) {
    $useRsync = $true
    Write-Host "Using rsync via WSL" -ForegroundColor Green
} elseif (Test-Path "C:\Program Files\Git\usr\bin\rsync.exe") {
    $useRsync = $true
    Write-Host "Using rsync from Git for Windows" -ForegroundColor Green
} else {
    Write-Host "rsync not found, will use file comparison method" -ForegroundColor Yellow
}

$targetPath = "${Server}:${TargetDir}/${ProjectName}/"

if ($useRsync) {
    Write-Host ""
    Write-Host "Step 2: Syncing files with rsync..." -ForegroundColor Yellow
    Write-Host "Target: $targetPath" -ForegroundColor Cyan
    Write-Host ""
    
    # Exclude patterns
    $excludePatterns = @(
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".venv",
        "venv",
        "env",
        ".git",
        ".gitignore",
        ".idea",
        ".vscode",
        "*.log",
        "*.log.*",
        "hls",
        "screenshots",
        "data",
        "logs",
        ".pytest_cache",
        "*.egg-info",
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache"
    )
    
    $excludeArgs = $excludePatterns | ForEach-Object { "--exclude=$_" }
    
    # Build rsync command
    $rsyncArgs = @(
        "-avz",
        "--delete",
        "--progress",
        "--human-readable"
    ) + $excludeArgs + @(
        "./",
        $targetPath
    )
    
    # Execute rsync
    if (Get-Command rsync -ErrorAction SilentlyContinue) {
        & rsync $rsyncArgs
    } elseif (Get-Command wsl -ErrorAction SilentlyContinue) {
        & wsl rsync $rsyncArgs
    } else {
        & "C:\Program Files\Git\usr\bin\rsync.exe" $rsyncArgs
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Deployment completed successfully!" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "Deployment failed!" -ForegroundColor Red
        exit 1
    }
} else {
    # Fallback: Use file comparison method
    Write-Host ""
    Write-Host "Step 2: Comparing files and uploading changes..." -ForegroundColor Yellow
    Write-Host "Target: $targetPath" -ForegroundColor Cyan
    Write-Host ""
    
    # Get list of files to check (exclude common ignored files)
    $excludeDirs = @("__pycache__", ".venv", "venv", "env", ".git", ".idea", ".vscode", "hls", "screenshots", "data", "logs", ".pytest_cache", "dist", "build", ".mypy_cache", ".ruff_cache")
    $excludeExtensions = @("*.pyc", "*.pyo", "*.pyd", "*.log", "*.log.*", "*.egg-info")
    
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
    
    Write-Host "Found $($files.Count) files to check" -ForegroundColor Cyan
    Write-Host ""
    
    # Upload files one by one (or in batches)
    $uploaded = 0
    $skipped = 0
    
    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
        $remotePath = "${Server}:${TargetDir}/${ProjectName}/$relativePath"
        
        # Create directory structure on remote if needed
        $remoteDir = Split-Path $remotePath -Parent
        $remoteDirUnix = $remoteDir -replace '\\', '/'
        
        # Upload file
        Write-Host "Uploading: $relativePath" -ForegroundColor Gray
        
        # Use scp to upload
        $scpTarget = "${Server}:${TargetDir}/${ProjectName}/$(Split-Path $relativePath -Parent)"
        $scpTarget = $scpTarget -replace '\\', '/'
        
        # Create parent directory first
        ssh $Server "mkdir -p ${TargetDir}/${ProjectName}/$(Split-Path $relativePath -Parent | ForEach-Object { $_ -replace '\\', '/' })" 2>$null
        
        scp "$($file.FullName)" "${Server}:${TargetDir}/${ProjectName}/$($relativePath -replace '\\', '/')" 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            $uploaded++
        } else {
            $skipped++
        }
    }
    
    Write-Host ""
    Write-Host "Uploaded: $uploaded files" -ForegroundColor Green
    if ($skipped -gt 0) {
        Write-Host "Skipped: $skipped files" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "   1. SSH to server: ssh $Server"
Write-Host "   2. Go to project: cd ${TargetDir}/${ProjectName}"
Write-Host "   3. Run restart: sudo ./deploy_and_start.sh"
Write-Host ""

