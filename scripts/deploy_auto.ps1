# Auto-install PuTTY and deploy script
# Usage: .\deploy_auto.ps1 [server] [password]
# Example: .\deploy_auto.ps1 ubuntu@192.168.54.188 123456

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$Password = "123456"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Auto-Deploy Script (Auto-Install PuTTY)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Function to check if PuTTY is installed
function Test-PuttyInstalled {
    $puttyPaths = @(
        "C:\Program Files\PuTTY\plink.exe",
        "C:\Program Files (x86)\PuTTY\plink.exe",
        "$env:USERPROFILE\Downloads\putty\plink.exe"
    )
    
    foreach ($path in $puttyPaths) {
        if (Test-Path $path) {
            $pscpPath = $path -replace "plink.exe", "pscp.exe"
            if (Test-Path $pscpPath) {
                return @{
                    Installed = $true
                    PlinkPath = $path
                    PscpPath = $pscpPath
                }
            }
        }
    }
    
    # Check PATH
    if (Get-Command plink -ErrorAction SilentlyContinue) {
        $plinkPath = (Get-Command plink).Source
        $pscpPath = $plinkPath -replace "plink.exe", "pscp.exe"
        if (Test-Path $pscpPath) {
            return @{
                Installed = $true
                PlinkPath = $plinkPath
                PscpPath = $pscpPath
            }
        }
    }
    
    return @{ Installed = $false }
}

# Check if PuTTY is installed
Write-Host "Checking PuTTY installation..." -ForegroundColor Yellow
$puttyStatus = Test-PuttyInstalled

if (-not $puttyStatus.Installed) {
    Write-Host "PuTTY not found. Starting auto-installation..." -ForegroundColor Yellow
    Write-Host ""
    
    # Create temp directory
    $tempDir = "$env:TEMP\putty_install"
    if (-not (Test-Path $tempDir)) {
        New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    }
    
    $installerPath = Join-Path $tempDir "putty-installer.msi"
    
    # Download PuTTY installer
    Write-Host "Downloading PuTTY installer..." -ForegroundColor Yellow
    $puttyUrl = "https://the.earth.li/~sgtatham/putty/latest/w64/putty-64bit-0.80-installer.msi"
    
    try {
        # Try using Invoke-WebRequest
        Write-Host "Downloading from: $puttyUrl" -ForegroundColor Gray
        Invoke-WebRequest -Uri $puttyUrl -OutFile $installerPath -UseBasicParsing -ErrorAction Stop
        Write-Host "✓ Download completed" -ForegroundColor Green
    } catch {
        Write-Host "✗ Download failed: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please download PuTTY manually:" -ForegroundColor Yellow
        Write-Host "  1. Visit: https://www.putty.org/" -ForegroundColor White
        Write-Host "  2. Download and install PuTTY" -ForegroundColor White
        Write-Host "  3. Then run: .\deploy_putty.ps1 $Server $Password" -ForegroundColor White
        exit 1
    }
    
    Write-Host ""
    Write-Host "Installing PuTTY (this may require admin rights)..." -ForegroundColor Yellow
    
    # Install PuTTY silently
    try {
        $process = Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$installerPath`" /quiet /norestart" -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -eq 0) {
            Write-Host "✓ PuTTY installed successfully" -ForegroundColor Green
        } else {
            Write-Host "✗ Installation failed (exit code: $($process.ExitCode))" -ForegroundColor Red
            Write-Host "  Trying manual installation..." -ForegroundColor Yellow
            
            # Try manual installation
            Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$installerPath`"" -Wait
        }
    } catch {
        Write-Host "✗ Installation error: $_" -ForegroundColor Red
        Write-Host "  Please install PuTTY manually from: $installerPath" -ForegroundColor Yellow
        exit 1
    }
    
    # Clean up installer
    if (Test-Path $installerPath) {
        Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
    }
    
    # Wait a moment for installation to complete
    Start-Sleep -Seconds 2
    
    # Re-check installation
    Write-Host ""
    Write-Host "Verifying installation..." -ForegroundColor Yellow
    $puttyStatus = Test-PuttyInstalled
    
    if (-not $puttyStatus.Installed) {
        Write-Host "✗ PuTTY installation verification failed" -ForegroundColor Red
        Write-Host "  Please restart PowerShell and try again, or install manually" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "✓ PuTTY verified and ready to use" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "✓ PuTTY already installed" -ForegroundColor Green
    Write-Host "  Plink: $($puttyStatus.PlinkPath)" -ForegroundColor Gray
    Write-Host "  Pscp: $($puttyStatus.PscpPath)" -ForegroundColor Gray
    Write-Host ""
}

# Now use deploy_putty.ps1 or call the deployment directly
Write-Host "Starting deployment..." -ForegroundColor Cyan
Write-Host ""

# Check if deploy_putty.ps1 exists
if (Test-Path "deploy_putty.ps1") {
    Write-Host "Using deploy_putty.ps1 script..." -ForegroundColor Green
    & .\deploy_putty.ps1 -Server $Server -Password $Password
} else {
    Write-Host "deploy_putty.ps1 not found, using direct deployment..." -ForegroundColor Yellow
    
    # Direct deployment using PuTTY tools
    $plinkPath = $puttyStatus.PlinkPath
    $pscpPath = $puttyStatus.PscpPath
    
    # Update version first
    Write-Host "Updating version..." -ForegroundColor Yellow
    python update_version.py
    Write-Host ""
    
    # Get files to upload (same logic as deploy_simple.ps1)
    $excludeDirs = @("screenshots", "__pycache__", ".venv", "venv", "env", ".git", ".idea", ".vscode", "hls", "data", "logs", ".pytest_cache", "dist", "build", ".mypy_cache", ".ruff_cache")
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
            "/data/Smart_RTSP_Stream_Manager/$unixPath"
        }
        $dirsString = $dirsToCreate -join " "
        
        $serverOnly = $Server -replace ".*@", ""
        $userOnly = $Server -replace "@.*", ""
        
        & $plinkPath -pw $Password -batch "$userOnly@$serverOnly" "mkdir -p $dirsString" 2>$null
        Write-Host ""
    }
    
    # Upload files
    Write-Host "Uploading files..." -ForegroundColor Yellow
    $uploaded = 0
    $failed = 0
    
    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
        $remotePath = "${Server}:/data/Smart_RTSP_Stream_Manager/$($relativePath -replace '\\', '/')"
        
        Write-Host "Uploading: $relativePath" -ForegroundColor Gray
        
        & $pscpPath -pw $Password -batch "$($file.FullName)" $remotePath 2>$null
        
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
    } else {
        Write-Host "Upload completed with some failures" -ForegroundColor Yellow
        Write-Host "Uploaded: $uploaded files" -ForegroundColor Green
        Write-Host "Failed: $failed files" -ForegroundColor Red
    }
}

Write-Host ""

