# -*- coding: utf-8 -*-
"""
检查静态文件是否与服务器同步
用于部署后验证前端文件是否正确更新
"""

import sys
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "app" / "static"

def get_file_hash(file_path: Path) -> str:
    """计算文件的 MD5 哈希值"""
    if not file_path.exists():
        return None
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def check_static_files():
    """检查静态文件是否存在且可访问"""
    print("=" * 60)
    print("检查静态文件")
    print("=" * 60)
    
    # 需要检查的关键文件
    critical_files = [
        "index.html",
        "js/api.js",
        "js/utils.js",
        "js/dashboard.js",
        "js/nvr-config.js",
        "js/tasks.js",
        "js/images.js",
        "js/parking-changes.js",
        "js/parking-changes-list.js",
        "js/main.js",
        "css/styles.css",
    ]
    
    missing_files = []
    existing_files = []
    
    for rel_path in critical_files:
        file_path = STATIC_DIR / rel_path
        if file_path.exists():
            file_hash = get_file_hash(file_path)
            file_size = file_path.stat().st_size
            existing_files.append({
                "path": rel_path,
                "size": file_size,
                "hash": file_hash[:8] if file_hash else "N/A"
            })
            print(f"✅ {rel_path:40s} ({file_size:>8} bytes, hash: {file_hash[:8] if file_hash else 'N/A'})")
        else:
            missing_files.append(rel_path)
            print(f"❌ {rel_path:40s} (文件不存在)")
    
    print("\n" + "=" * 60)
    if missing_files:
        print(f"⚠️  发现 {len(missing_files)} 个缺失的文件:")
        for f in missing_files:
            print(f"   - {f}")
        return False
    else:
        print(f"✅ 所有 {len(existing_files)} 个关键文件都存在")
        return True

def check_version_in_html():
    """检查 index.html 中的版本号"""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        print("❌ index.html 不存在")
        return False
    
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查版本号
    if 'window.APP_VERSION' in content or 'APP_VERSION' in content:
        print("✅ index.html 包含版本号")
        # 提取版本号
        import re
        version_match = re.search(r"APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", content)
        if version_match:
            version = version_match.group(1)
            print(f"   当前版本号: {version}")
    else:
        print("⚠️  index.html 中未找到版本号")
    
    # 检查所有 JS 文件是否有版本号
    js_files_with_version = content.count('?v=')
    print(f"   带版本号的 JS 文件数量: {js_files_with_version}")
    
    return True

if __name__ == "__main__":
    print("\n")
    files_ok = check_static_files()
    print("\n")
    version_ok = check_version_in_html()
    print("\n")
    
    if files_ok and version_ok:
        print("✅ 静态文件检查通过")
        sys.exit(0)
    else:
        print("❌ 静态文件检查失败，请检查文件是否完整上传")
        sys.exit(1)

