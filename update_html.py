# -*- coding: utf-8 -*-
import re

html_path = "app/static/index.html"

with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 使用正则表达式替换
pattern = r'<div id="pc-msg" class="muted" style="font-size:12px; margin-bottom:8px;">请先点击"搜索"加载车位变化数据。</div>'
replacement = '''<div id="pc-msg" class="muted" style="font-size:13px; margin-bottom:12px; padding:12px; background:rgba(148,163,184,0.1); border-radius:6px;">
            💡 提示：请先选择日期并点击"搜索"按钮加载车位变化数据。系统将按通道分组展示所有变化快照，每张快照包含"上一张"和"当前"两张对比图，点击图片可放大查看或对比。
          </div>'''

content = re.sub(pattern, replacement, content)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("HTML提示信息已更新")
