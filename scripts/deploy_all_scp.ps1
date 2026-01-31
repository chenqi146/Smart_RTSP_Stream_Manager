# PowerShell 一键部署脚本 - 使用 scp（最简单可靠）
# 使用方法: .\deploy_all_scp.ps1 [服务器地址] [目标路径]
# 示例: .\deploy_all_scp.ps1 ubuntu@192.168.54.188 /data

param(
    [string]$Server = "ubuntu@192.168.54.188",
    [string]$TargetDir = "/data",
    [string]$ProjectName = "Smart_RTSP_Stream_Manager"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "一键部署脚本（更新版本号 + 上传代码）" -ForegroundColor Cyan
Write-Host "使用 SCP 方式（最简单可靠）" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 第一步：更新版本号
Write-Host "第一步：更新版本号..." -ForegroundColor Yellow
if (Test-Path "update_version.py") {
    python update_version.py
    if ($LASTEXITCODE -ne 0) {
        python3 update_version.py
    }
} else {
    Write-Host "警告: 未找到 update_version.py，跳过版本号更新" -ForegroundColor Yellow
}
Write-Host ""

# 第二步：部署代码
Write-Host "第二步：部署代码到服务器..." -ForegroundColor Yellow
if (Test-Path "deploy_scp.ps1") {
    & .\deploy_scp.ps1 -Server $Server -TargetDir $TargetDir -ProjectName $ProjectName
} else {
    # 直接使用 scp 命令
    Write-Host "使用 scp 直接上传..." -ForegroundColor Yellow
    $currentDir = Get-Location
    $sourcePath = $currentDir.Path
    $targetPath = "${Server}:${TargetDir}/"
    
    Write-Host "正在上传: $sourcePath -> $targetPath" -ForegroundColor Cyan
    
    # 上传当前目录的所有文件
    scp -r "$sourcePath\*" "${Server}:${TargetDir}/${ProjectName}/"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "代码同步完成！" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "代码同步失败" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "部署完成！" -ForegroundColor Green
Write-Host ""
Write-Host "下一步操作：" -ForegroundColor Cyan
Write-Host "   1. SSH 连接到服务器: ssh $Server"
Write-Host "   2. 进入项目目录: cd $TargetDir/$ProjectName"
Write-Host "   3. 运行部署脚本: sudo ./deploy_and_start.sh"
Write-Host ""
