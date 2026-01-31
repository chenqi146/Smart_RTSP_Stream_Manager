"""
-*- coding:utf-8 -*-
Time:2025-12-19 11:02
Author:GuoJun
FileName:test_openvc.py
SoftWare:PyCharm
PS:
"""
import cv2
import numpy as np

# 读取图像
image_path = 'img.png'  # 替换为你的图片路径
img = cv2.imread(image_path)

# 定义车位坐标列表 (x, y, w, h)
parking_spaces = [
    (241, 155, 185, 116),  # GXSL001
    (454, 101, 198, 117),  # GXSL002
    (712, 78, 329, 131),  # GXSL003
    (1132, 126, 297, 127),  # GXSL004
    (1460, 198, 196, 122),  # GXSL005
    (1652, 258, 146, 114)  # GXSL006
]

# 颜色定义（BGR）
colors = [
    (0, 255, 0),  # 绿色
    (0, 0, 255),  # 红色
    (255, 0, 0),  # 蓝色
    (255, 255, 0),  # 青色
    (255, 0, 255),  # 品红
    (0, 255, 255)  # 黄色
]

# 绘制每个车位
for i, (x, y, w, h) in enumerate(parking_spaces):
    color = colors[i % len(colors)]
    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)

    # 添加文字标签
    label = f"GXSL{i + 1:03d}"
    cv2.putText(img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

# 显示图像
cv2.imshow('Parking Spaces', img)
cv2.waitKey(0)
cv2.destroyAllWindows()

# 可选：保存结果
cv2.imwrite('parking_spaces_marked.jpg', img)
print("已保存带车位标注的图像：parking_spaces_marked.jpg")