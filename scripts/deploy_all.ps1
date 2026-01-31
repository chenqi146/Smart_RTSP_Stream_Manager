# PowerShell 一键部署脚本 - 更新版本号并上传代码
# 使用方法: .\deploy_all.ps1 [服务器地址] [目标路径]
# 示例: .\deploy_all.ps1 ubuntu@192.168.54.188 /data

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$TargetDir = "/data",
    [string]$ProjectName = "Smart_RTSP_Stream_Manager"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "一键部署脚本（更新版本号 + 上传代码）" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 第一步：更新版本号
Write-Host "📝 第一步：更新版本号..." -ForegroundColor Yellow
if (Test-Path "update_version.py") {
    python update_version.py
    if ($LASTEXITCODE -ne 0) {
        python3 update_version.py
    }
} elseif (Test-Path "update_version.sh") {
    bash update_version.sh
} else {
    Write-Host "⚠️  警告: 未找到版本号更新脚本，跳过版本号更新" -ForegroundColor Yellow
}
Write-Host ""

# 第二步：部署代码
Write-Host "🚀 第二步：部署代码到服务器..." -ForegroundColor Yellow
if (Test-Path "deploy.ps1") {
    & .\deploy.ps1 -Server $Server -TargetDir $TargetDir -ProjectName $ProjectName
} elseif (Test-Path "deploy.bat") {
    & .\deploy.bat $Server $TargetDir
} else {
    Write-Host "❌ 错误: 未找到部署脚本" -ForegroundColor Red
    Write-Host "   请手动运行部署命令" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "✅ 部署完成！" -ForegroundColor Green
Write-Host ""
Write-Host "📝 下一步操作：" -ForegroundColor Cyan
Write-Host "   1. SSH 连接到服务器: ssh $Server"
Write-Host "   2. 进入项目目录: cd $TargetDir/$ProjectName"
Write-Host "   3. 运行部署脚本: sudo ./deploy_and_start.sh"
Write-Host ""

