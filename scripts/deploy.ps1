# PowerShell 部署脚本 - Windows 使用
# 使用方法: .\deploy.ps1 [服务器地址] [目标路径]
# 示例: .\deploy.ps1 ubuntu@192.168.54.188 /data

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$TargetDir = "/data",
    [string]$ProjectName = "Smart_RTSP_Stream_Manager"
)

$LocalDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "代码部署脚本 (PowerShell)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "服务器: $Server"
Write-Host "目标目录: $TargetDir"
Write-Host "项目名称: $ProjectName"
Write-Host "本地目录: $LocalDir"
Write-Host ""

# 检查 rsync 是否可用（通过 Git Bash 或 WSL）
$rsyncCmd = $null
if (Get-Command rsync -ErrorAction SilentlyContinue) {
    $rsyncCmd = "rsync"
} elseif (Get-Command wsl -ErrorAction SilentlyContinue) {
    $rsyncCmd = "wsl rsync"
} elseif (Test-Path "C:\Program Files\Git\usr\bin\rsync.exe") {
    $rsyncCmd = "C:\Program Files\Git\usr\bin\rsync.exe"
} else {
    Write-Host "❌ 错误: 未找到 rsync 命令" -ForegroundColor Red
    Write-Host "   请安装以下之一:" -ForegroundColor Yellow
    Write-Host "   1. Git for Windows (包含 rsync)"
    Write-Host "   2. WSL (Windows Subsystem for Linux)"
    Write-Host ""
    Write-Host "   或者使用 scp 命令（较慢）:" -ForegroundColor Yellow
    Write-Host "   scp -r .\Smart_RTSP_Stream_Manager\ $Server`:$TargetDir/"
    exit 1
}

Write-Host "🔄 开始同步代码..." -ForegroundColor Yellow
Write-Host ""

# 排除的文件和目录列表
$excludeList = @(
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

# 构建 rsync exclude 参数
$excludeArgs = $excludeList | ForEach-Object { "--exclude=$_" }

# 使用 rsync 同步文件
$rsyncArgs = @(
    "-avz",
    "--delete",
    "--progress"
) + $excludeArgs + @(
    "$LocalDir/",
    "${Server}:${TargetDir}/${ProjectName}/"
)

& $rsyncCmd.Split(' ') $rsyncArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ 代码同步完成！" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 下一步操作：" -ForegroundColor Cyan
    Write-Host "   1. SSH 连接到服务器: ssh $Server"
    Write-Host "   2. 进入项目目录: cd $TargetDir/$ProjectName"
    Write-Host "   3. 运行部署脚本: sudo ./deploy_and_start.sh"
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "❌ 代码同步失败，请检查网络连接和服务器权限" -ForegroundColor Red
    exit 1
}

