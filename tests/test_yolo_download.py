"""测试 YOLO 模型下载功能

运行此脚本可以测试模型是否能够正常下载到项目目录。
"""

import sys
from pathlib import Path

# 添加项目路径
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.yolo_detector import preload_model

if __name__ == "__main__":
    print("=" * 60)
    print("YOLO 模型下载测试")
    print("=" * 60)
    print()
    
    print("正在预加载模型（如果模型不存在会自动下载）...")
    print()
    
    if preload_model():
        print()
        print("=" * 60)
        print("✓ 模型加载成功！")
        print("=" * 60)
        print()
        print("模型文件位置: <项目目录>/models/yolov8n.pt")
        print("现在可以启动 Worker 了：")
        print("  python -m app.background.parking_change_worker")
    else:
        print()
        print("=" * 60)
        print("✗ 模型加载失败")
        print("=" * 60)
        print()
        print("请检查：")
        print("1. 是否已安装 ultralytics: pip install ultralytics")
        print("2. 网络连接是否正常（首次下载需要网络）")
        print("3. 查看上方的错误信息")
        sys.exit(1)
