"""
测试脚本：在图片上绘制跟踪区域和停车位坐标

使用方法：
1. 准备一张测试图片
2. 在代码中直接修改下面的配置参数
3. 运行脚本：python test_draw_parking_areas.py
4. 生成标注后的图片

或者使用命令行参数（见 main 函数）
"""

# ==================== 配置区域：在这里直接修改参数 ====================
# 方式1: 使用通道自动加载坐标（推荐）
USE_CHANNEL = True  # 设置为 True 使用通道，False 使用手动坐标
IMAGE_PATH = "testimge/img_1.png"  # 输入图片路径
NVR_IP = "10.10.11.123"  # NVR IP地址
CHANNEL_CODE = "c1"  # 通道编码（如 c1, c2）
OUTPUT_PATH = ""  # 输出图片路径（可选，不填自动生成）

# 方式2: 手动指定坐标（当 USE_CHANNEL = False 时使用）
TRACK_SPACE = None  # 跟踪区域坐标，例如: '{"bbox": [100, 100, 500, 400]}'
PARKING_SPACES = None  # 停车位坐标，例如: '[{"space_name": "GXSL091", "bbox_x1": 150, "bbox_y1": 150, "bbox_x2": 250, "bbox_y2": 250}]'

# 坐标文件目录（如果使用通道方式）
COORDINATES_DIR = "channel_coordinates"

# 坐标缩放配置（如果数据库中的坐标是基于其他分辨率的，需要缩放）
ORIGINAL_WIDTH = 1920  # 数据库中坐标的原始宽度（默认1920×1080）
ORIGINAL_HEIGHT = 1080  # 数据库中坐标的原始高度
# 如果设置为 None，则使用实际图片尺寸（不缩放）
# 如果设置了值，会将坐标从 ORIGINAL_WIDTH×ORIGINAL_HEIGHT 缩放到实际图片尺寸
# ==================== 配置区域结束 ====================

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("错误: 需要安装 Pillow 库")
    print("请运行: pip install Pillow")
    sys.exit(1)


def parse_track_space(track_space_str: str) -> Optional[Any]:
    """解析跟踪区域坐标字符串（可能是JSON格式）"""
    if not track_space_str or not track_space_str.strip():
        return None
    
    try:
        # 尝试解析为JSON
        return json.loads(track_space_str)
    except json.JSONDecodeError:
        # 如果不是JSON，尝试其他格式
        # 这里可以根据实际格式进行扩展
        print(f"警告: track_space 不是有效的JSON格式: {track_space_str}")
        return None


def parse_parking_spaces(parking_spaces_str: str) -> List[Dict[str, Any]]:
    """解析停车位坐标字符串（JSON数组格式）"""
    if not parking_spaces_str or not parking_spaces_str.strip():
        return []
    
    try:
        spaces = json.loads(parking_spaces_str)
        if isinstance(spaces, list):
            return spaces
        elif isinstance(spaces, dict):
            return [spaces]
        else:
            print(f"警告: parking_spaces 格式不正确: {parking_spaces_str}")
            return []
    except json.JSONDecodeError as e:
        print(f"错误: 解析 parking_spaces JSON 失败: {e}")
        return []


def scale_coordinate(value, original_size, target_size):
    """缩放坐标值从原始尺寸到目标尺寸"""
    if original_size == target_size:
        return value
    return int(value * target_size / original_size)


def scale_coordinates(x1, y1, x2, y2, original_width, original_height, target_width, target_height):
    """缩放坐标从原始分辨率到目标分辨率"""
    scale_x = target_width / original_width
    scale_y = target_height / original_height
    
    x1_scaled = x1 * scale_x
    y1_scaled = y1 * scale_y
    x2_scaled = x2 * scale_x
    y2_scaled = y2 * scale_y
    
    return x1_scaled, y1_scaled, x2_scaled, y2_scaled


def normalize_bbox(x1, y1, x2, y2, img_width, img_height):
    """规范化边界框坐标，确保 x1 < x2 且 y1 < y2，并在图片范围内"""
    # 交换坐标如果顺序错误
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1
    
    # 限制在图片范围内
    x1 = max(0, min(int(x1), img_width - 1))
    y1 = max(0, min(int(y1), img_height - 1))
    x2 = max(x1 + 1, min(int(x2), img_width))
    y2 = max(y1 + 1, min(int(y2), img_height))
    
    return x1, y1, x2, y2


def draw_track_space(draw: ImageDraw.Draw, track_space: Any, img_width: int, img_height: int, 
                     original_width: Optional[int] = None, original_height: Optional[int] = None):
    """在图片上绘制跟踪区域（红色），并在框上显示坐标数值
    
    参数:
        draw: ImageDraw对象
        track_space: 跟踪区域坐标数据
        img_width: 实际图片宽度
        img_height: 实际图片高度
        original_width: 坐标的原始宽度（如果提供，会进行缩放）
        original_height: 坐标的原始高度（如果提供，会进行缩放）
    """
    if not track_space:
        return
    
    # 红色，线宽3
    color = (255, 0, 0)  # RGB红色
    width = 3
    
    # 确定是否需要缩放
    need_scale = (original_width is not None and original_height is not None and 
                  (original_width != img_width or original_height != img_height))
    
    # 尝试加载字体（如果失败则使用默认字体）
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        except:
            font = ImageFont.load_default()
    
    def get_text_size(text, font):
        """获取文本尺寸（兼容不同PIL版本）"""
        try:
            # 新版本PIL使用 textbbox
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            # 旧版本PIL使用 textsize
            try:
                return draw.textsize(text, font=font)
            except:
                # 如果都不可用，返回估算值
                return len(text) * 8, 14
    
    def draw_rectangle_with_coords(x1, y1, x2, y2, original_coords=None):
        """绘制矩形并在框上显示坐标"""
        # 如果需要缩放，先缩放坐标
        if need_scale and original_coords is not None:
            x1_scaled, y1_scaled, x2_scaled, y2_scaled = scale_coordinates(
                original_coords[0], original_coords[1], original_coords[2], original_coords[3],
                original_width, original_height, img_width, img_height
            )
            x1, y1, x2, y2 = normalize_bbox(x1_scaled, y1_scaled, x2_scaled, y2_scaled, img_width, img_height)
        elif need_scale:
            # 如果没有原始坐标，直接缩放当前坐标
            x1_scaled, y1_scaled, x2_scaled, y2_scaled = scale_coordinates(
                x1, y1, x2, y2, original_width, original_height, img_width, img_height
            )
            x1, y1, x2, y2 = normalize_bbox(x1_scaled, y1_scaled, x2_scaled, y2_scaled, img_width, img_height)
        else:
            # 不需要缩放，直接规范化
            x1, y1, x2, y2 = normalize_bbox(x1, y1, x2, y2, img_width, img_height)
        
        # 绘制矩形
        draw.rectangle([x1, y1, x2, y2], outline=color, width=width)
        
        # 准备坐标文本（显示原始坐标值）
        if original_coords is not None:
            # 使用原始坐标值显示
            coord_text = f"[{original_coords[0]}, {original_coords[1]}, {original_coords[2]}, {original_coords[3]}]"
        else:
            # 使用规范化后的坐标值
            coord_text = f"[{x1}, {y1}, {x2}, {y2}]"
        
        # 在左上角显示完整坐标
        text_width, text_height = get_text_size(coord_text, font)
        padding = 2
        
        # 在左上角绘制背景框（白色背景）
        bg_box = [x1, y1, x1 + text_width + padding * 2, y1 + text_height + padding * 2]
        draw.rectangle(bg_box, fill=(255, 255, 255), outline=color, width=1)
        
        # 在左上角显示坐标文本
        draw.text((x1 + padding, y1 + padding), coord_text, fill=color, font=font)
        
        # 在四个角显示对应的坐标点
        corner_size = 6
        corner_labels = [
            (x1, y1, f"({original_coords[0] if original_coords else x1},{original_coords[1] if original_coords else y1})"),  # 左上角
            (x2, y1, f"({original_coords[2] if original_coords else x2},{original_coords[1] if original_coords else y1})"),  # 右上角
            (x1, y2, f"({original_coords[0] if original_coords else x1},{original_coords[3] if original_coords else y2})"),  # 左下角
            (x2, y2, f"({original_coords[2] if original_coords else x2},{original_coords[3] if original_coords else y2})"),  # 右下角
        ]
        
        for cx, cy, label in corner_labels:
            # 绘制角点标记（小圆点）
            draw.ellipse([cx - corner_size//2, cy - corner_size//2, 
                         cx + corner_size//2, cy + corner_size//2], 
                        fill=color, outline=color, width=1)
            
            # 在角点旁边显示坐标
            label_width, label_height = get_text_size(label, font)
            
            # 根据角点位置调整标签位置，避免超出图片
            if cx == x1:  # 左角
                label_x = cx + corner_size + 3
            else:  # 右角
                label_x = cx - label_width - corner_size - 3
            
            if cy == y1:  # 上角
                label_y = cy + corner_size + 3
            else:  # 下角
                label_y = cy - label_height - corner_size - 3
            
            # 确保标签在图片范围内
            label_x = max(0, min(label_x, img_width - label_width))
            label_y = max(0, min(label_y, img_height - label_height))
            
            # 绘制标签背景（白色背景）
            label_bg = [label_x - 1, label_y - 1, 
                       label_x + label_width + 1, label_y + label_height + 1]
            draw.rectangle(label_bg, fill=(255, 255, 255), outline=color, width=1)
            draw.text((label_x, label_y), label, fill=color, font=font)
    
    try:
        if isinstance(track_space, dict):
            # 单个对象格式
            if "bbox" in track_space and isinstance(track_space["bbox"], list) and len(track_space["bbox"]) >= 4:
                # bbox格式: [x1, y1, x2, y2]
                bbox = track_space["bbox"]
                original_coords = [int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])]
                # draw_rectangle_with_coords 内部会处理缩放
                draw_rectangle_with_coords(bbox[0], bbox[1], bbox[2], bbox[3], original_coords)
            elif all(k in track_space for k in ["x1", "y1", "x2", "y2"]):
                # 对象格式: {x1, y1, x2, y2}
                original_coords = [int(track_space["x1"]), int(track_space["y1"]), 
                                  int(track_space["x2"]), int(track_space["y2"])]
                draw_rectangle_with_coords(
                    track_space["x1"], track_space["y1"], 
                    track_space["x2"], track_space["y2"], 
                    original_coords
                )
        elif isinstance(track_space, list):
            # 数组格式
            if len(track_space) >= 4 and all(isinstance(x, (int, float)) for x in track_space[:4]):
                # [x1, y1, x2, y2] 格式
                original_coords = [int(track_space[0]), int(track_space[1]), 
                                  int(track_space[2]), int(track_space[3])]
                draw_rectangle_with_coords(
                    track_space[0], track_space[1], 
                    track_space[2], track_space[3], 
                    original_coords
                )
            else:
                # 多个区域的数组
                for area in track_space:
                    if isinstance(area, dict):
                        if "bbox" in area and isinstance(area["bbox"], list) and len(area["bbox"]) >= 4:
                            bbox = area["bbox"]
                            original_coords = [int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])]
                            draw_rectangle_with_coords(bbox[0], bbox[1], bbox[2], bbox[3], original_coords)
                        elif all(k in area for k in ["x1", "y1", "x2", "y2"]):
                            original_coords = [int(area["x1"]), int(area["y1"]), 
                                              int(area["x2"]), int(area["y2"])]
                            draw_rectangle_with_coords(
                                area["x1"], area["y1"], 
                                area["x2"], area["y2"], 
                                original_coords
                            )
                    elif isinstance(area, list) and len(area) >= 4:
                        original_coords = [int(area[0]), int(area[1]), int(area[2]), int(area[3])]
                        draw_rectangle_with_coords(area[0], area[1], area[2], area[3], original_coords)
        elif isinstance(track_space, str):
            # 字符串格式（可能是JSON字符串）
            try:
                import json
                parsed = json.loads(track_space)
                # 递归调用处理解析后的数据
                draw_track_space(draw, parsed, img_width, img_height, original_width, original_height)
            except:
                # 如果不是JSON，尝试解析为列表格式 "[11, 19, 1875, 430]"
                try:
                    import ast
                    parsed = ast.literal_eval(track_space)
                    if isinstance(parsed, list) and len(parsed) >= 4:
                        original_coords = [int(parsed[0]), int(parsed[1]), int(parsed[2]), int(parsed[3])]
                        # 如果需要缩放，先缩放坐标
                        if need_scale:
                            x1, y1, x2, y2 = scale_coordinates(
                                original_coords[0], original_coords[1], original_coords[2], original_coords[3],
                                original_width, original_height, img_width, img_height
                            )
                            x1, y1, x2, y2 = normalize_bbox(x1, y1, x2, y2, img_width, img_height)
                        else:
                            x1, y1, x2, y2 = normalize_bbox(parsed[0], parsed[1], parsed[2], parsed[3], img_width, img_height)
                        draw_rectangle_with_coords(x1, y1, x2, y2, original_coords)
                except:
                    print(f"警告: 无法解析 track_space 字符串: {track_space}")
    except Exception as e:
        print(f"警告: 绘制跟踪区域时出错: {e}")
        import traceback
        traceback.print_exc()


def draw_parking_spaces(draw: ImageDraw.Draw, parking_spaces: List[Dict[str, Any]], img_width: int, img_height: int,
                        original_width: Optional[int] = None, original_height: Optional[int] = None):
    """在图片上绘制停车位坐标（黄色）
    
    支持两种格式：
    1. 矩形格式：{"bbox_x1": x1, "bbox_y1": y1, "bbox_x2": x2, "bbox_y2": y2}
    2. 多边形格式：{"bbox": [x1, y1, x2, y2, x3, y3, x4, y4, ...]} 或 {"bbox": [x, y, width, height]}
    
    参数:
        draw: ImageDraw对象
        parking_spaces: 停车位坐标列表
        img_width: 实际图片宽度
        img_height: 实际图片高度
        original_width: 坐标的原始宽度（如果提供，会进行缩放）
        original_height: 坐标的原始高度（如果提供，会进行缩放）
    """
    if not parking_spaces:
        return
    
    # 黄色，线宽2
    color = (255, 255, 0)  # RGB黄色
    width = 2
    
    # 确定是否需要缩放
    need_scale = (original_width is not None and original_height is not None and 
                  (original_width != img_width or original_height != img_height))
    
    # 尝试加载字体（如果失败则使用默认字体）
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
        except:
            font = ImageFont.load_default()
    
    for space in parking_spaces:
        try:
            space_name = space.get("space_name", "")
            
            # 方式1: 如果提供了原始bbox数组（可能是多边形或 [x, y, width, height]）
            if "bbox" in space and isinstance(space["bbox"], list):
                bbox = space["bbox"]
                
                if len(bbox) >= 4:
                    # 判断是 [x, y, width, height] 还是多边形坐标
                    if len(bbox) == 4:
                        # 判断格式：如果 x + width < img_width 且 y + height < img_height，可能是 [x, y, width, height]
                        # 否则可能是 [x1, y1, x2, y2] 格式
                        x, y, val3, val4 = bbox[0], bbox[1], bbox[2], bbox[3]
                        
                        # 使用原始分辨率判断格式（如果提供了原始分辨率）
                        check_width = original_width if need_scale and original_width else img_width
                        check_height = original_height if need_scale and original_height else img_height
                        
                        # 尝试作为 [x, y, width, height] 格式处理
                        # 如果 val3 和 val4 都小于图片尺寸，且 x + val3 < check_width, y + val4 < check_height，则是 width/height
                        if (x + val3 < check_width * 1.5 and y + val4 < check_height * 1.5 and 
                            val3 > 0 and val4 > 0 and val3 < check_width and val4 < check_height):
                            # [x, y, width, height] 格式
                            x1_orig, y1_orig = int(x), int(y)
                            x2_orig, y2_orig = int(x + val3), int(y + val4)
                        else:
                            # [x1, y1, x2, y2] 格式
                            x1_orig, y1_orig, x2_orig, y2_orig = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                            if x1_orig > x2_orig:
                                x1_orig, x2_orig = x2_orig, x1_orig
                            if y1_orig > y2_orig:
                                y1_orig, y2_orig = y2_orig, y1_orig
                        
                        # 如果需要缩放，先缩放坐标
                        if need_scale:
                            x1, y1, x2, y2 = scale_coordinates(
                                x1_orig, y1_orig, x2_orig, y2_orig,
                                original_width, original_height, img_width, img_height
                            )
                        else:
                            x1, y1, x2, y2 = x1_orig, y1_orig, x2_orig, y2_orig
                        
                        # 规范化坐标
                        x1, y1, x2, y2 = normalize_bbox(x1, y1, x2, y2, img_width, img_height)
                        
                        # 绘制矩形框
                        draw.rectangle([x1, y1, x2, y2], outline=color, width=width)
                        
                        # 绘制车位编号
                        if space_name:
                            draw.text((x1 + 2, y1 + 2), space_name, fill=color, font=font)
                    else:
                        # 多边形格式：至少4个点（8个值），可能是 [x1, y1, x2, y2, x3, y3, x4, y4, ...]
                        if len(bbox) % 2 == 0 and len(bbox) >= 8:
                            # 构建多边形点列表 [(x1, y1), (x2, y2), ...]
                            points = []
                            for i in range(0, len(bbox), 2):
                                if i + 1 < len(bbox):
                                    x_orig, y_orig = int(bbox[i]), int(bbox[i + 1])
                                    # 如果需要缩放，先缩放坐标
                                    if need_scale:
                                        x = scale_coordinate(x_orig, original_width, img_width)
                                        y = scale_coordinate(y_orig, original_height, img_height)
                                    else:
                                        x, y = x_orig, y_orig
                                    # 限制在图片范围内
                                    x = max(0, min(x, img_width - 1))
                                    y = max(0, min(y, img_height - 1))
                                    points.append((x, y))
                            
                            if len(points) >= 3:
                                # 绘制多边形
                                draw.polygon(points, outline=color, width=width)
                                
                                # 绘制车位编号（在多边形中心或第一个点附近）
                                if space_name and points:
                                    label_x, label_y = points[0]
                                    draw.text((label_x + 2, label_y + 2), space_name, fill=color, font=font)
                        else:
                            print(f"警告: 停车位 {space_name} 的bbox格式不正确（长度: {len(bbox)}），跳过")
                            continue
            
            # 方式2: 矩形格式（bbox_x1, bbox_y1, bbox_x2, bbox_y2）
            elif all(k in space for k in ["bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2"]):
                x1_orig = int(space["bbox_x1"])
                y1_orig = int(space["bbox_y1"])
                x2_orig = int(space["bbox_x2"])
                y2_orig = int(space["bbox_y2"])
                
                # 验证和修正坐标（确保 x1 < x2 且 y1 < y2）
                if x1_orig > x2_orig:
                    x1_orig, x2_orig = x2_orig, x1_orig
                if y1_orig > y2_orig:
                    y1_orig, y2_orig = y2_orig, y1_orig
                
                # 检查坐标是否有效
                if x1_orig == x2_orig or y1_orig == y2_orig:
                    print(f"警告: 停车位 {space_name} 的坐标无效（宽度或高度为0），跳过绘制")
                    continue
                
                # 如果需要缩放，先缩放坐标
                if need_scale:
                    x1, y1, x2, y2 = scale_coordinates(
                        x1_orig, y1_orig, x2_orig, y2_orig,
                        original_width, original_height, img_width, img_height
                    )
                else:
                    x1, y1, x2, y2 = x1_orig, y1_orig, x2_orig, y2_orig
                
                # 规范化坐标
                x1, y1, x2, y2 = normalize_bbox(x1, y1, x2, y2, img_width, img_height)
                
                # 绘制矩形框
                draw.rectangle([x1, y1, x2, y2], outline=color, width=width)
                
                # 绘制车位编号
                if space_name:
                    draw.text((x1 + 2, y1 + 2), space_name, fill=color, font=font)
            else:
                print(f"警告: 停车位 {space_name} 的坐标格式不正确，跳过")
                continue
                
        except Exception as e:
            print(f"警告: 绘制停车位 {space.get('space_name', 'unknown')} 时出错: {e}")
            import traceback
            traceback.print_exc()


def draw_parking_areas_on_image(
    image_path: str,
    track_space: Optional[str] = None,
    parking_spaces: Optional[str] = None,
    output_path: Optional[str] = None
) -> str:
    """
    在图片上绘制跟踪区域和停车位坐标
    
    参数:
        image_path: 输入图片路径
        track_space: 跟踪区域坐标（JSON字符串）
        parking_spaces: 停车位坐标（JSON字符串，数组格式）
        output_path: 输出图片路径（如果不指定，自动生成）
    
    返回:
        输出图片路径
    """
    # 检查输入文件（支持相对路径，相对于 testopvc 目录）
    CURRENT_DIR = Path(__file__).resolve().parent  # testopvc 目录
    img_path = Path(image_path)
    if not img_path.is_absolute():
        # 相对路径，相对于 testopvc 目录
        img_path = CURRENT_DIR / img_path
    if not img_path.exists():
        raise FileNotFoundError(f"图片文件不存在: {image_path}")
    
    # 打开图片
    try:
        img = Image.open(img_path)
    except Exception as e:
        raise ValueError(f"无法打开图片文件: {e}")
    
    # 创建绘图对象
    draw = ImageDraw.Draw(img)
    
    # 解析坐标数据
    track_data = parse_track_space(track_space) if track_space else None
    parking_data = parse_parking_spaces(parking_spaces) if parking_spaces else []
    
    # 获取坐标缩放配置（从全局配置）
    # 如果配置了原始分辨率，且与实际图片尺寸不同，则进行缩放
    # 直接使用文件顶部定义的全局变量
    globals_dict = globals()
    orig_w = globals_dict.get('ORIGINAL_WIDTH', None)
    orig_h = globals_dict.get('ORIGINAL_HEIGHT', None)
    
    # 打印缩放信息
    if orig_w and orig_h:
        print(f"坐标缩放: {orig_w}×{orig_h} -> {img.width}×{img.height}")
        print(f"缩放比例: X={img.width/orig_w:.3f}, Y={img.height/orig_h:.3f}")
    else:
        print(f"图片尺寸: {img.width}×{img.height} (不缩放)")
    
    # 绘制跟踪区域（红色）
    if track_data:
        print(f"绘制跟踪区域: {track_data}")
        draw_track_space(draw, track_data, img.width, img.height, orig_w, orig_h)
    else:
        print("未提供跟踪区域坐标")
    
    # 绘制停车位坐标（黄色）
    if parking_data:
        print(f"绘制 {len(parking_data)} 个停车位")
        draw_parking_spaces(draw, parking_data, img.width, img.height, orig_w, orig_h)
    else:
        print("未提供停车位坐标")
    
    # 确定输出路径（始终保存在 testopvc 目录下）
    CURRENT_DIR = Path(__file__).resolve().parent  # testopvc 目录
    if not output_path:
        # 自动生成输出文件名，保存在 testopvc 目录
        output_path = CURRENT_DIR / f"{img_path.stem}_annotated{img_path.suffix}"
    else:
        output_path = Path(output_path)
        # 如果是相对路径，相对于 testopvc 目录
        if not output_path.is_absolute():
            output_path = CURRENT_DIR / output_path
        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存图片
    img.save(output_path, quality=95)
    print(f"✓ 已保存标注后的图片: {output_path}")
    
    return str(output_path)


def load_channel_coordinates(nvr_ip: str, channel_code: str, coordinates_dir: str = "channel_coordinates") -> tuple:
    """
    从导出的坐标文件中加载指定通道的坐标数据
    
    参数:
        nvr_ip: NVR IP地址
        channel_code: 通道编码（如 c1）
        coordinates_dir: 坐标文件目录（相对于 testopvc 目录）
    
    返回:
        (track_space, parking_spaces) 元组
    """
    # 坐标目录相对于当前脚本所在目录（testopvc）
    CURRENT_DIR = Path(__file__).resolve().parent
    coordinates_path = CURRENT_DIR / coordinates_dir
    if not coordinates_path.exists():
        return None, None
    
    # 生成文件名：{ip}_{channel_code}.json
    safe_ip = nvr_ip.replace(".", "_").replace(":", "_")
    safe_channel = channel_code.lower().replace("/", "_")
    filename = f"{safe_ip}_{safe_channel}.json"
    filepath = coordinates_path / filename
    
    if not filepath.exists():
        print(f"警告: 未找到坐标文件: {filepath}")
        return None, None
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        track_space = data.get("track_space")
        parking_spaces = data.get("parking_spaces", [])
        
        # 将parking_spaces转换为JSON字符串格式
        parking_spaces_str = json.dumps(parking_spaces, ensure_ascii=False) if parking_spaces else None
        
        return track_space, parking_spaces_str
    except Exception as e:
        print(f"错误: 读取坐标文件失败: {e}")
        return None, None


def main():
    parser = argparse.ArgumentParser(
        description="在图片上绘制跟踪区域和停车位坐标",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 方法1: 使用通道自动加载坐标（推荐）
  python test_draw_parking_areas.py --image test.jpg --channel 192.168.1.100 c1
  
  # 方法2: 手动指定坐标
  python test_draw_parking_areas.py --image test.jpg \\
      --track-space '{"bbox": [100, 100, 500, 400]}' \\
      --parking-spaces '[{"space_name": "GXSL091", "bbox_x1": 150, "bbox_y1": 150, "bbox_x2": 250, "bbox_y2": 250}]'
  
  # 方法3: 从文件读取坐标
  python test_draw_parking_areas.py --image test.jpg \\
      --track-space-file track_space.json \\
      --parking-spaces-file parking_spaces.json
  
  # 方法4: 从通道文件读取（指定完整文件路径）
  python test_draw_parking_areas.py --image test.jpg \\
      --channel-file channel_coordinates/192_168_1_100_c1.json
        """
    )
    
    parser.add_argument(
        "--image", "-i",
        required=True,
        help="输入图片路径"
    )
    
    # 通道相关参数
    parser.add_argument(
        "--channel", "-c",
        nargs=2,
        metavar=("NVR_IP", "CHANNEL_CODE"),
        help="NVR IP地址和通道编码（如: 192.168.1.100 c1），会自动从 channel_coordinates/ 目录加载坐标"
    )
    
    parser.add_argument(
        "--channel-file", "-C",
        type=str,
        help="通道坐标文件路径（完整路径），例如: channel_coordinates/192_168_1_100_c1.json"
    )
    
    parser.add_argument(
        "--coordinates-dir",
        type=str,
        default="channel_coordinates",
        help="坐标文件目录（默认: channel_coordinates）"
    )
    
    # 手动指定坐标参数
    parser.add_argument(
        "--track-space", "-t",
        type=str,
        help="跟踪区域坐标（JSON字符串），例如: '{\"bbox\": [100, 100, 500, 400]}'"
    )
    
    parser.add_argument(
        "--parking-spaces", "-p",
        type=str,
        help="停车位坐标（JSON数组字符串），例如: '[{\"space_name\": \"GXSL091\", \"bbox_x1\": 150, \"bbox_y1\": 150, \"bbox_x2\": 250, \"bbox_y2\": 250}]'"
    )
    
    parser.add_argument(
        "--track-space-file", "-T",
        type=str,
        help="从文件读取跟踪区域坐标（JSON格式）"
    )
    
    parser.add_argument(
        "--parking-spaces-file", "-P",
        type=str,
        help="从文件读取停车位坐标（JSON格式）"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="输出图片路径（如果不指定，自动生成）"
    )
    
    args = parser.parse_args()
    
    # 优先使用通道参数自动加载坐标
    track_space = args.track_space
    parking_spaces = args.parking_spaces
    
    if args.channel:
        # 从通道自动加载
        nvr_ip, channel_code = args.channel
        print(f"正在从通道加载坐标: NVR IP={nvr_ip}, 通道={channel_code}")
        track_space, parking_spaces = load_channel_coordinates(
            nvr_ip, 
            channel_code, 
            args.coordinates_dir
        )
        if not track_space and not parking_spaces:
            print("错误: 无法从通道加载坐标数据", file=sys.stderr)
            sys.exit(1)
    elif args.channel_file:
        # 从指定文件加载
        try:
            with open(args.channel_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            track_space = data.get("track_space")
            parking_spaces = json.dumps(data.get("parking_spaces", []), ensure_ascii=False) if data.get("parking_spaces") else None
            print(f"已从文件加载坐标: {args.channel_file}")
        except Exception as e:
            print(f"错误: 读取通道文件失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # 从文件读取坐标（如果提供了文件路径）
        if args.track_space_file:
            with open(args.track_space_file, "r", encoding="utf-8") as f:
                track_space = f.read()
        
        if args.parking_spaces_file:
            with open(args.parking_spaces_file, "r", encoding="utf-8") as f:
                parking_spaces = f.read()
    
    # 执行绘制
    try:
        output_path = draw_parking_areas_on_image(
            image_path=args.image,
            track_space=track_space,
            parking_spaces=parking_spaces,
            output_path=args.output
        )
        print(f"\n✓ 成功！标注后的图片已保存到: {output_path}")
    except Exception as e:
        print(f"\n✗ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def run_with_config():
    """使用代码中的配置参数运行"""
    if USE_CHANNEL:
        # 使用通道方式
        print(f"使用通道方式: NVR IP={NVR_IP}, 通道={CHANNEL_CODE}")
        track_space, parking_spaces = load_channel_coordinates(
            NVR_IP,
            CHANNEL_CODE,
            COORDINATES_DIR
        )
        if not track_space and not parking_spaces:
            print("错误: 无法从通道加载坐标数据")
            print(f"请检查: 1) 是否已运行 export_channel_coordinates.py")
            print(f"        2) 文件是否存在: {COORDINATES_DIR}/{NVR_IP.replace('.', '_')}_{CHANNEL_CODE.lower()}.json")
            return
    else:
        # 使用手动坐标
        track_space = TRACK_SPACE
        parking_spaces = PARKING_SPACES
        if not track_space and not parking_spaces:
            print("错误: 未提供坐标数据")
            print("请设置 TRACK_SPACE 或 PARKING_SPACES，或将 USE_CHANNEL 设置为 True")
            return
    
    try:
        output_path = draw_parking_areas_on_image(
            image_path=IMAGE_PATH,
            track_space=track_space,
            parking_spaces=parking_spaces,
            output_path=OUTPUT_PATH if OUTPUT_PATH else None
        )
        print(f"\n✓ 成功！标注后的图片已保存到: {output_path}")
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    # 如果提供了命令行参数，使用命令行模式
    if len(sys.argv) > 1:
        main()
    else:
        # 否则使用代码中的配置
        print("=" * 60)
        print("使用代码中的配置参数")
        print("=" * 60)
        print(f"图片路径: {IMAGE_PATH}")
        if USE_CHANNEL:
            print(f"NVR IP: {NVR_IP}")
            print(f"通道编码: {CHANNEL_CODE}")
        else:
            print("使用手动指定的坐标")
        if OUTPUT_PATH:
            print(f"输出路径: {OUTPUT_PATH}")
        print("=" * 60)
        print()
        
        run_with_config()
