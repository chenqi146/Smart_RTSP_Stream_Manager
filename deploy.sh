#!/bin/bash
# 代码部署脚本 - 使用 rsync 高效同步代码到服务器
# 使用方法: ./deploy.sh [服务器地址] [目标路径]
# 示例: ./deploy.sh ubuntu@192.168.54.188 /data

SERVER=${1:-ubuntu@192.168.54.188}
TARGET_DIR=${2:-/data}
PROJECT_NAME="Smart_RTSP_Stream_Manager"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "代码部署脚本"
echo "=========================================="
echo "服务器: $SERVER"
echo "目标目录: $TARGET_DIR"
echo "项目名称: $PROJECT_NAME"
echo "本地目录: $LOCAL_DIR"
echo ""

# 检查 rsync 是否可用
if ! command -v rsync >/dev/null 2>&1; then
    echo "❌ 错误: 未找到 rsync 命令"
    echo "   请安装 rsync:"
    echo "   Windows: 安装 Git Bash 或 WSL"
    echo "   Linux/Mac: sudo apt-get install rsync 或 brew install rsync"
    exit 1
fi

# 排除的文件和目录列表
EXCLUDE_LIST=(
    "__pycache__"
    "*.pyc"
    "*.pyo"
    "*.pyd"
    ".venv"
    "venv"
    "env"
    ".git"
    ".gitignore"
    ".idea"
    ".vscode"
    "*.log"
    "*.log.*"
    "hls"
    "screenshots"
    "data"
    "logs"
    ".pytest_cache"
    "*.egg-info"
    "dist"
    "build"
    ".mypy_cache"
    ".ruff_cache"
)

# 构建 rsync exclude 参数
EXCLUDE_ARGS=()
for item in "${EXCLUDE_LIST[@]}"; do
    EXCLUDE_ARGS+=("--exclude=$item")
done

echo "🔄 开始同步代码..."
echo ""

# 使用 rsync 同步文件
rsync -avz \
    --delete \
    --progress \
    "${EXCLUDE_ARGS[@]}" \
    "$LOCAL_DIR/" \
    "$SERVER:$TARGET_DIR/$PROJECT_NAME/"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 代码同步完成！"
    echo ""
    echo "📝 下一步操作："
    echo "   1. SSH 连接到服务器: ssh $SERVER"
    echo "   2. 进入项目目录: cd $TARGET_DIR/$PROJECT_NAME"
    echo "   3. 运行部署脚本: sudo ./deploy_and_start.sh"
    echo ""
else
    echo ""
    echo "❌ 代码同步失败，请检查网络连接和服务器权限"
    exit 1
fi

