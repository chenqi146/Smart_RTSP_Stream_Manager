# PowerShell 部署脚本 - 使用 scp（兼容性最好）
# 使用方法: .\deploy_scp.ps1 [服务器地址] [目标路径]
# 示例: .\deploy_scp.ps1 ubuntu@192.168.54.188 /data

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$TargetDir = "/data",
    [string]$ProjectName = "Smart_RTSP_Stream_Manager"
)

$LocalDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "代码部署脚本 (使用 SCP)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "服务器: $Server"
Write-Host "目标目录: $TargetDir"
Write-Host "项目名称: $ProjectName"
Write-Host "本地目录: $LocalDir"
Write-Host ""

# 检查 scp 是否可用
if (-not (Get-Command scp -ErrorAction SilentlyContinue)) {
    Write-Host "错误: 未找到 scp 命令" -ForegroundColor Red
    Write-Host "请确保已安装 OpenSSH 客户端" -ForegroundColor Yellow
    Write-Host "Windows 10/11 通常已内置，如果没有请安装 OpenSSH" -ForegroundColor Yellow
    exit 1
}

Write-Host "开始同步代码（使用 scp）..." -ForegroundColor Yellow
Write-Host "排除目录: screenshots, __pycache__, .venv, logs, hls, data" -ForegroundColor Yellow
Write-Host ""

# 排除目录列表
$excludeDirs = @("screenshots", "__pycache__", ".venv", "venv", "env", ".git", ".idea", ".vscode", "hls", "data", "logs", ".pytest_cache", "dist", "build", ".mypy_cache", ".ruff_cache")
$excludeExtensions = @("*.pyc", "*.pyo", "*.pyd", "*.log", "*.log.*", "*.egg-info")

# 获取需要上传的文件（排除 screenshots 等目录）
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

Write-Host "找到 $($files.Count) 个文件需要上传" -ForegroundColor Cyan
Write-Host ""

$targetPath = "${Server}:${TargetDir}/${ProjectName}/"
$uploaded = 0
$failed = 0

foreach ($file in $files) {
    $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
    $remotePath = "${targetPath}$($relativePath -replace '\\', '/')"
    
    # 创建远程父目录
    $remoteDir = Split-Path $remotePath -Parent
    ssh $Server "mkdir -p `"$remoteDir`"" 2>$null
    
    Write-Host "上传: $relativePath" -ForegroundColor Gray
    
    scp "$($file.FullName)" $remotePath 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        $uploaded++
    } else {
        Write-Host "失败: $relativePath" -ForegroundColor Red
        $failed++
    }
}

Write-Host ""
if ($failed -eq 0) {
    Write-Host "代码同步完成！" -ForegroundColor Green
    Write-Host ""
    Write-Host "下一步操作：" -ForegroundColor Cyan
    Write-Host "   1. SSH 连接到服务器: ssh $Server"
    Write-Host "   2. 进入项目目录: cd $TargetDir/$ProjectName"
    Write-Host "   3. 运行部署脚本: sudo ./deploy_and_start.sh"
    Write-Host ""
} else {
    Write-Host "代码同步完成，但有部分文件失败" -ForegroundColor Yellow
    Write-Host "请检查失败的文件" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "常见问题：" -ForegroundColor Yellow
    Write-Host "   1. 服务器权限不足，尝试使用 root 用户" -ForegroundColor Yellow
    Write-Host "   2. 网络连接问题，检查服务器地址和端口" -ForegroundColor Yellow
    Write-Host "   3. SSH 密钥未配置，可能需要输入密码" -ForegroundColor Yellow
}
