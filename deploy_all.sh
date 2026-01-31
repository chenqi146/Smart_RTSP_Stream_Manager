# 一键部署脚本 - 更新版本号并上传代码
# 使用方法: ./deploy_all.sh [服务器地址] [目标路径]
# 示例: ./deploy_all.sh ubuntu@192.168.54.188 /data

SERVER=${1:-ubuntu@192.168.54.188}
TARGET_DIR=${2:-/data}
PROJECT_NAME="Smart_RTSP_Stream_Manager"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "一键部署脚本（更新版本号 + 上传代码）"
echo "=========================================="
echo ""

# 第一步：更新版本号
echo "📝 第一步：更新版本号..."
if [ -f "update_version.py" ]; then
    python3 update_version.py || python update_version.py
elif [ -f "update_version.sh" ]; then
    bash update_version.sh
else
    echo "⚠️  警告: 未找到版本号更新脚本，跳过版本号更新"
fi
echo ""

# 第二步：部署代码
echo "🚀 第二步：部署代码到服务器..."
if [ -f "deploy.sh" ]; then
    bash deploy.sh "$SERVER" "$TARGET_DIR"
else
    echo "❌ 错误: 未找到 deploy.sh 脚本"
    echo "   请手动运行: ./deploy.sh $SERVER $TARGET_DIR"
    exit 1
fi

echo ""
echo "✅ 部署完成！"
echo ""
echo "📝 下一步操作："
echo "   1. SSH 连接到服务器: ssh $SERVER"
echo "   2. 进入项目目录: cd $TARGET_DIR/$PROJECT_NAME"
echo "   3. 运行部署脚本: sudo ./deploy_and_start.sh"
echo ""

