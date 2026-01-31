# Git-based deployment script - only upload changed files
# Usage: .\deploy_git.ps1 [server] [target_path]
# Example: .\deploy_git.ps1 ubuntu@192.168.54.188 /data

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$TargetDir = "/data",
    [string]$ProjectName = "Smart_RTSP_Stream_Manager"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Git-based Deployment (Only Changed Files)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if git is available
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Error: git is not installed" -ForegroundColor Red
    Write-Host "Please install git or use deploy_smart.ps1 instead" -ForegroundColor Yellow
    exit 1
}

# Update version first
Write-Host "Step 1: Updating version..." -ForegroundColor Yellow
python update_version.py
Write-Host ""

# Get list of changed files
Write-Host "Step 2: Detecting changed files..." -ForegroundColor Yellow

# Get modified files (compared to HEAD)
$changedFiles = git diff --name-only HEAD
$untrackedFiles = git ls-files --others --exclude-standard

if ($changedFiles -and $changedFiles.Count -gt 0) {
    Write-Host "Found $($changedFiles.Count) modified files" -ForegroundColor Cyan
} else {
    Write-Host "No modified files detected" -ForegroundColor Yellow
}

if ($untrackedFiles -and $untrackedFiles.Count -gt 0) {
    Write-Host "Found $($untrackedFiles.Count) new files" -ForegroundColor Cyan
}

$allFiles = @()
if ($changedFiles) { $allFiles += $changedFiles }
if ($untrackedFiles) { $allFiles += $untrackedFiles }

# Filter out excluded directories (especially screenshots)
$excludeDirs = @("screenshots", "__pycache__", ".venv", "venv", "env", ".git", ".idea", ".vscode", "hls", "data", "logs", ".pytest_cache", "dist", "build", ".mypy_cache", ".ruff_cache")
$excludeExtensions = @("*.pyc", "*.pyo", "*.pyd", "*.log", "*.log.*", "*.egg-info")

$filteredFiles = $allFiles | Where-Object {
    $file = $_
    $shouldExclude = $false
    foreach ($dir in $excludeDirs) {
        if ($file -like "*\$dir\*" -or $file -like "*/$dir/*") {
            $shouldExclude = $true
            break
        }
    }
    if (-not $shouldExclude) {
        foreach ($ext in $excludeExtensions) {
            if ($file -like $ext) {
                $shouldExclude = $true
                break
            }
        }
    }
    -not $shouldExclude
}

if ($filteredFiles.Count -eq 0) {
    Write-Host ""
    Write-Host "No files to upload (after excluding screenshots and other directories)!" -ForegroundColor Yellow
    Write-Host "All files are up to date." -ForegroundColor Green
    exit 0
}

$allFiles = $filteredFiles
Write-Host "After filtering: $($allFiles.Count) files to upload" -ForegroundColor Cyan
Write-Host ""

Write-Host ""
Write-Host "Step 3: Uploading changed files..." -ForegroundColor Yellow
Write-Host "Target: ${Server}:${TargetDir}/${ProjectName}/" -ForegroundColor Cyan
Write-Host ""

$uploaded = 0
$failed = 0

foreach ($file in $allFiles) {
    if (Test-Path $file) {
        $remotePath = "${Server}:${TargetDir}/${ProjectName}/$file"
        $remotePath = $remotePath -replace '\\', '/'
        
        # Create parent directory on remote
        $remoteDir = Split-Path $remotePath -Parent
        ssh $Server "mkdir -p `"$remoteDir`"" 2>$null
        
        Write-Host "Uploading: $file" -ForegroundColor Gray
        
        scp "$file" $remotePath 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            $uploaded++
        } else {
            Write-Host "Failed: $file" -ForegroundColor Red
            $failed++
        }
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

