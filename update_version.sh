#!/bin/bash
# 更新版本号脚本
# 自动更新 index.html 中的 APP_VERSION，使用当前时间戳

HTML_FILE="app/static/index.html"
TIMESTAMP=$(date +"%Y%m%d%H%M")

if [ ! -f "$HTML_FILE" ]; then
    echo "❌ 错误: 找不到文件 $HTML_FILE"
    exit 1
fi

# 检查操作系统类型
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/window\.APP_VERSION = '[^']*'/window.APP_VERSION = '$TIMESTAMP'/" "$HTML_FILE"
elif [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    # Linux 或 Git Bash (Windows)
    sed -i "s/window\.APP_VERSION = '[^']*'/window.APP_VERSION = '$TIMESTAMP'/" "$HTML_FILE"
else
    echo "❌ 错误: 不支持的操作系统: $OSTYPE"
    exit 1
fi

echo "✅ 版本号已更新为: $TIMESTAMP"
echo "   文件: $HTML_FILE"

