#!/bin/bash
# Smart RTSP Stream Manager - Docker 一键部署脚本（Linux / macOS）
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  Smart RTSP Stream Manager - Docker 部署"
echo "=========================================="
echo ""

# 检查 Docker
if ! command -v docker &>/dev/null; then
    echo "❌ 未检测到 Docker，请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 支持 docker-compose 或 docker compose
COMPOSE_CMD=""
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ 未检测到 docker-compose，请安装 Docker Compose"
    exit 1
fi

echo "✅ 使用: $COMPOSE_CMD"
echo ""

# 若不存在 .env，从示例复制
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "📄 已从 .env.example 创建 .env，请修改 APP_PORT 等后重新运行"
    fi
fi

# 从 .env 读取 APP_PORT（必填，用于端口映射）
if [ -f .env ]; then
    APP_PORT=$(grep -E '^APP_PORT=' .env 2>/dev/null | cut -d= -f2-)
fi
if [ -z "$APP_PORT" ]; then
    echo "❌ 请在 .env 中设置 APP_PORT（本机端口，避免与其它项目冲突）"
    exit 1
fi

echo "🔨 构建镜像并启动容器（对外端口: $APP_PORT）..."
$COMPOSE_CMD up -d --build

echo ""
echo "⏳ 等待应用就绪（约 30 秒）..."
sleep 30

# 健康检查
if curl -sf "http://localhost:${APP_PORT}/healthz" >/dev/null 2>&1; then
    echo ""
    echo "=========================================="
    echo "🎉 部署完成"
    echo "=========================================="
    echo "  - Web 界面: http://localhost:${APP_PORT}"
    echo "  - API 文档: http://localhost:${APP_PORT}/docs"
    echo "  - 健康检查: http://localhost:${APP_PORT}/healthz"
    echo "=========================================="
    echo ""
    echo "常用命令:"
    echo "  查看日志: $COMPOSE_CMD logs -f app"
    echo "  停止服务: $COMPOSE_CMD down"
    echo "  重启应用: $COMPOSE_CMD restart app"
else
    echo "⚠️  应用可能仍在启动中，请稍后访问: http://localhost:${APP_PORT}"
    echo "   查看日志: $COMPOSE_CMD logs -f app"
fi
