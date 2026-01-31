#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新版本号脚本
自动更新 index.html 中的 APP_VERSION 和所有 JS 文件的版本号，使用当前时间戳
"""

import re
import os
from datetime import datetime

HTML_FILE = "app/static/index.html"

def update_version():
    """更新 index.html 中的版本号"""
    if not os.path.exists(HTML_FILE):
        print(f"❌ 错误: 找不到文件 {HTML_FILE}")
        return False
    
    # 读取文件内容
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 生成新的版本号（时间戳格式：YYYYMMDDHHMM）
    new_version = datetime.now().strftime("%Y%m%d%H%M")
    
    # 替换 window.APP_VERSION
    pattern1 = r"window\.APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]"
    replacement1 = f"window.APP_VERSION = '{new_version}'"
    content = re.sub(pattern1, replacement1, content)
    
    # 替换所有 JS 文件的版本号 (?v=版本号)
    pattern2 = r"(\?v=)(\d{12})"
    replacement2 = f"\\g<1>{new_version}"
    content = re.sub(pattern2, replacement2, content)
    
    # 写入文件
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 版本号已更新为: {new_version}")
    print(f"   文件: {HTML_FILE}")
    print(f"   已更新 window.APP_VERSION 和所有 JS 文件的 ?v= 参数")
    return True

if __name__ == "__main__":
    update_version()

