# Smart RTSP Stream Manager - Docker 一键部署脚本（Windows PowerShell）
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=========================================="
Write-Host "  Smart RTSP Stream Manager - Docker 部署"
Write-Host "=========================================="
Write-Host ""

# 检查 Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "未检测到 Docker，请先安装 Docker Desktop: https://docs.docker.com/desktop/install-windows-install/" -ForegroundColor Red
    exit 1
}

# 支持 docker compose 或 docker-compose
$ComposeCmd = $null
if (docker compose version 2>$null) { $ComposeCmd = "docker compose" }
elseif (Get-Command docker-compose -ErrorAction SilentlyContinue) { $ComposeCmd = "docker-compose" }
else {
    Write-Host "未检测到 docker-compose，请安装 Docker Desktop（已包含 Compose）" -ForegroundColor Red
    exit 1
}

Write-Host "使用: $ComposeCmd" -ForegroundColor Green
Write-Host ""

# 若不存在 .env，从示例复制
if (-not (Test-Path .env)) {
    if (Test-Path .env.example) {
        Copy-Item .env.example .env
        Write-Host "已从 .env.example 创建 .env，请修改 APP_PORT 等后重新运行"
    }
}

# 从 .env 读取 APP_PORT（必填，用于端口映射）
$AppPort = $env:APP_PORT
if (-not $AppPort -and (Test-Path .env)) {
    $line = Get-Content .env | Where-Object { $_ -match '^\s*APP_PORT\s*=' } | Select-Object -First 1
    if ($line) { $AppPort = ($line -replace '^[^=]+=', '').Trim() }
}
if (-not $AppPort) {
    Write-Host "请在 .env 中设置 APP_PORT（本机端口，避免与其它项目冲突）" -ForegroundColor Red
    exit 1
}

Write-Host "构建镜像并启动容器（对外端口: $AppPort）..."
Invoke-Expression "$ComposeCmd up -d --build"

Write-Host ""
Write-Host "等待应用就绪（约 30 秒）..."
Start-Sleep -Seconds 30
try {
    $r = Invoke-WebRequest -Uri "http://localhost:$AppPort/healthz" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    if ($r.StatusCode -eq 200) {
        Write-Host ""
        Write-Host "=========================================="
        Write-Host "部署完成" -ForegroundColor Green
        Write-Host "=========================================="
        Write-Host "  - Web 界面: http://localhost:$AppPort"
        Write-Host "  - API 文档: http://localhost:$AppPort/docs"
        Write-Host "  - 健康检查: http://localhost:$AppPort/healthz"
        Write-Host "=========================================="
        Write-Host ""
        Write-Host "常用命令:"
        Write-Host "  查看日志: $ComposeCmd logs -f app"
        Write-Host "  停止服务: $ComposeCmd down"
        Write-Host "  重启应用: $ComposeCmd restart app"
    }
} catch {
    Write-Host "应用可能仍在启动中，请稍后访问: http://localhost:$AppPort" -ForegroundColor Yellow
    Write-Host "查看日志: $ComposeCmd logs -f app"
}
