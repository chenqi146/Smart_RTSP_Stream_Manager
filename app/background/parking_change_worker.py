"""车位变化检测 Worker

独立进程运行，用于异步执行：
- 从 screenshots 表中读取 yolo_status = 'pending' 的截图；
- 调用 YOLOv8 检测车辆；
- 按车位坐标计算每个车位当前是否有车；
- 与历史记录对比，写入 parking_changes / parking_change_snapshots；
- 更新 screenshots.yolo_status 和 yolo_last_error。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

from sqlalchemy import desc

# 兼容从项目根目录直接运行或从 app.main 导入
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import SessionLocal  # noqa: E402
from models import (  # noqa: E402
    Screenshot,
    Task,
    NvrConfig,
    ChannelConfig,
    ParkingSpace,
    ParkingChange,
    ParkingChangeSnapshot,
)
from app.core.config import (  # noqa: E402
    SCREENSHOT_BASE,
    VEHICLE_SIMILARITY_THRESHOLD_SAME_DAY,
    VEHICLE_SIMILARITY_THRESHOLD_CROSS_DAY,
    VEHICLE_SIMILARITY_THRESHOLD_SHORT_INTERVAL,
    SHORT_INTERVAL_SECONDS,
    BRIGHTNESS_LOW_THRESHOLD,
    BRIGHTNESS_HIGH_THRESHOLD,
    CLARITY_THRESHOLD,
    HIGH_ROBUSTNESS_MODE_ENABLED,
    MAX_CONSECUTIVE_MISS_DETECTIONS,
    TIME_PERIOD_EARLY_MORNING,
    TIME_PERIOD_DAYTIME,
    TIME_PERIOD_EVENING,
    TIME_PERIOD_NIGHT,
    MIN_SPACE_MATCH_CONFIDENCE_DAY,
    MIN_SPACE_MATCH_CONFIDENCE_NIGHT,
    TIME_PERIOD_THRESHOLD_FACTOR_EARLY_MORNING,
    TIME_PERIOD_THRESHOLD_FACTOR_DAYTIME,
    TIME_PERIOD_THRESHOLD_FACTOR_EVENING,
    TIME_PERIOD_THRESHOLD_FACTOR_NIGHT,
    BRIGHTNESS_THRESHOLD_FACTOR_DARK,
    BRIGHTNESS_THRESHOLD_FACTOR_VERY_DARK,
    CLARITY_THRESHOLD_FACTOR_LOW,
    WEATHER_THRESHOLD_FACTOR_RAINY,
    WEATHER_THRESHOLD_FACTOR_FOGGY,
    WEATHER_THRESHOLD_FACTOR_CLOUDY,
    WEATHER_THRESHOLD_FACTOR_SUNNY,
    MIN_YOLO_CONFIDENCE_FOR_CHANGE_DETECTION,
    STATE_CONTINUATION_PROTECTION_ENABLED,
    STATE_CONTINUATION_TIME_THRESHOLD,
    STATE_CONTINUATION_POSITION_THRESHOLD,
    STATE_CONTINUATION_SIMILARITY_MARGIN,
    STATE_LOCK_ENABLED,
    STATE_LOCK_FRAMES,
    STATE_UNLOCK_FRAMES,
)
from services.yolo_detector import detect_cars_in_region, detect_cars_on_image, extract_vehicle_features, preload_model  # noqa: E402
import json
import cv2
import numpy as np
from datetime import datetime, timedelta


def _bbox_intersection_area(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> int:
    """计算两个矩形框的交集面积。"""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0
    return (ix2 - ix1) * (iy2 - iy1)


def _parse_track_space(track_space_str: str) -> Tuple[int, int, int, int] | None:
    """解析跟踪区域坐标字符串。
    
    支持格式：
    - JSON数组字符串: "[x1, y1, x2, y2]"
    - 字典字符串: '{"x1": 10, "y1": 20, "x2": 100, "y2": 200}'
    
    返回: (x1, y1, x2, y2) 或 None
    """
    if not track_space_str or not track_space_str.strip():
        return None
    
    try:
        # 尝试解析JSON
        parsed = json.loads(track_space_str.strip())
        
        if isinstance(parsed, list) and len(parsed) >= 4:
            # 格式: [x1, y1, x2, y2]
            return (int(parsed[0]), int(parsed[1]), int(parsed[2]), int(parsed[3]))
        elif isinstance(parsed, dict):
            # 格式: {"x1": ..., "y1": ..., "x2": ..., "y2": ...}
            if all(k in parsed for k in ["x1", "y1", "x2", "y2"]):
                return (int(parsed["x1"]), int(parsed["y1"]), int(parsed["x2"]), int(parsed["y2"]))
    except (json.JSONDecodeError, ValueError, KeyError):
        pass
    
    return None


def _calculate_iou(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
    """计算两个边界框的IoU（Intersection over Union）。
    
    参数:
        box1: (x1, y1, x2, y2) 格式
        box2: (x1, y1, x2, y2) 格式
    
    返回:
        IoU值（0.0-1.0）
    """
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    # 计算交集
    x1_i = max(x1_1, x1_2)
    y1_i = max(y1_1, y1_2)
    x2_i = min(x2_1, x2_2)
    y2_i = min(y2_1, y2_2)
    
    if x2_i <= x1_i or y2_i <= y1_i:
        return 0.0
    
    intersection = (x2_i - x1_i) * (y2_i - y1_i)
    
    # 计算并集
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union = area1 + area2 - intersection
    
    if union == 0:
        return 0.0
    
    return intersection / union


def _detect_space_occupancy(
    image_path: Path,
    spaces: List[ParkingSpace],
    track_space_str: str | None = None,
    overlap_threshold: float = 0.3,
    extract_features: bool = True,
    image_brightness: float = None,  # 图像亮度，用于动态调整检测参数
) -> Tuple[Dict[int, bool], Dict[int, Tuple[int, int, int, int]], Dict[int, float], Dict[int, Dict[str, Any]]]:
    """对每个车位坐标区域进行 YOLO 检测，判断是否有车辆。

    采用新的策略：整张图检测 + 坐标匹配
    1. 在整张图上进行YOLO检测（避免ROI裁剪导致的坐标错位和细节丢失）
    2. 计算每个检测框与车位区域的IoU，判断车辆是否在车位内
    3. 如果IoU >= overlap_threshold，则认为车位有车

    注意：
    - 当前项目中 ParkingSpace.bbox_x1 / bbox_y1 / bbox_x2 / bbox_y2 实际含义是：
      bbox_x1 = x（左上角X）
      bbox_y1 = y（左上角Y）
      bbox_x2 = width（宽度）
      bbox_y2 = height（高度）
      即 [x, y, width, height]，而不是 [x1, y1, x2, y2]。
    - YOLO返回的坐标已经是相对于原始图像的，无需坐标映射。

    返回:
        (占用状态字典, 检测区域字典, 置信度字典, 特征字典)
        - 占用状态字典: {space_id: bool} - 每个车位是否有车
        - 检测区域字典: {space_id: (x, y, w, h)} - 每个车位实际检测的区域坐标
        - 置信度字典: {space_id: float} - 每个车位检测的置信度（0.0-1.0）
        - 特征字典: {space_id: Dict} - 每个车位的车辆特征（如果有车）
    """
    result: Dict[int, bool] = {}
    detection_regions: Dict[int, Tuple[int, int, int, int]] = {}
    confidence_map: Dict[int, float] = {}
    features_map: Dict[int, Dict[str, Any]] = {}
    
    # 读取原始图像（用于特征提取）
    import cv2
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"[ParkingChangeWorker] 警告: 无法读取图片: {image_path}")
        for space in spaces:
            result[space.id] = False
            confidence_map[space.id] = 0.0
            x = int(space.bbox_x1)
            y = int(space.bbox_y1)
            w = max(1, int(space.bbox_x2))
            h = max(1, int(space.bbox_y2))
            detection_regions[space.id] = (x, y, w, h)
        return result, detection_regions, confidence_map, features_map
    
    img_height, img_width = img.shape[:2]
    
    # 在整张图上进行YOLO检测
    print(f"[ParkingChangeWorker] 使用整图检测+坐标匹配策略（图像尺寸: {img_width}x{img_height}）")
    car_boxes, preprocess_info = detect_cars_on_image(
        image_path,
        image_brightness=image_brightness,
    )
    
    print(f"[ParkingChangeWorker] 整图检测到 {len(car_boxes)} 个车辆对象")
    
    # 对每个车位，计算与检测框的IoU
    for space in spaces:
        # 车位坐标格式：[x, y, width, height]
        x = int(space.bbox_x1)
        y = int(space.bbox_y1)
        w = max(1, int(space.bbox_x2))
        h = max(1, int(space.bbox_y2))
        
        # 转换为 (x1, y1, x2, y2) 格式用于IoU计算
        space_box = (x, y, x + w, y + h)
        
        # 查找与该车位IoU最大的车辆检测框
        best_iou = 0.0
        best_confidence = 0.0
        best_car_box = None
        
        for car_box in car_boxes:
            car_box_xyxy = (car_box["x1"], car_box["y1"], car_box["x2"], car_box["y2"])
            iou = _calculate_iou(space_box, car_box_xyxy)
            
            if iou > best_iou:
                best_iou = iou
                best_confidence = car_box["confidence"]
                best_car_box = car_box
                print(f"[ParkingChangeWorker] 车位 {space.space_name}: 找到匹配车辆 (IoU={iou:.3f}, 置信度={best_confidence:.3f}, 车辆坐标=({car_box['x1']},{car_box['y1']})-({car_box['x2']},{car_box['y2']}))")
        
        # 确定最低置信度阈值（根据环境：白天/夜间）
        min_confidence_threshold = MIN_SPACE_MATCH_CONFIDENCE_DAY
        if image_brightness is not None and image_brightness < 120:
            min_confidence_threshold = MIN_SPACE_MATCH_CONFIDENCE_NIGHT
        
        # 如果IoU >= overlap_threshold 且置信度 >= 最低阈值，则认为车位有车
        if best_iou >= overlap_threshold and best_confidence >= min_confidence_threshold:
            result[space.id] = True
            confidence_map[space.id] = best_confidence
            detection_regions[space.id] = (x, y, w, h)
            
            # 提取车辆特征
            if extract_features and best_car_box:
                try:
                    # 从原始图像中裁剪车辆区域
                    car_x1 = max(0, min(best_car_box["x1"], img_width))
                    car_y1 = max(0, min(best_car_box["y1"], img_height))
                    car_x2 = max(0, min(best_car_box["x2"], img_width))
                    car_y2 = max(0, min(best_car_box["y2"], img_height))
                    
                    if car_x2 > car_x1 and car_y2 > car_y1:
                        vehicle_roi = img[car_y1:car_y2, car_x1:car_x2]
                        if vehicle_roi.size > 0:
                            features = extract_vehicle_features(vehicle_roi)
                            features_map[space.id] = features
                except Exception as e:
                    print(f"[ParkingChangeWorker] 提取车辆特征失败: {e}")
            
            print(f"[ParkingChangeWorker] 车位 {space.space_name}: 有车 (IoU={best_iou:.3f}, 置信度={best_confidence:.3f})")
        else:
            result[space.id] = False
            confidence_map[space.id] = 0.0
            detection_regions[space.id] = (x, y, w, h)
            if best_iou >= overlap_threshold and best_confidence < min_confidence_threshold:
                print(f"[ParkingChangeWorker] 车位 {space.space_name}: 无车 (IoU={best_iou:.3f} >= {overlap_threshold}, 但置信度={best_confidence:.3f} < {min_confidence_threshold:.3f})")
            elif best_iou > 0:
                print(f"[ParkingChangeWorker] 车位 {space.space_name}: 无车 (IoU={best_iou:.3f} < {overlap_threshold}, 最高置信度={best_confidence:.3f})")
            else:
                print(f"[ParkingChangeWorker] 车位 {space.space_name}: 无车 (未找到匹配的车辆检测框)")
    
    return result, detection_regions, confidence_map, features_map


def _draw_detection_regions(
    image_path: Path,
    spaces: List[ParkingSpace],
    detection_regions: Dict[int, Tuple[int, int, int, int]],
    output_path: Path | None = None,
) -> Path:
    """在图片上绘制绿色线标记实际检测的区域。
    
    参数:
        image_path: 原始图片路径
        spaces: 车位列表
        detection_regions: 检测区域字典 {space_id: (x, y, w, h)}
        output_path: 输出图片路径，如果为 None 则自动生成
    
    返回:
        输出图片路径
    """
    try:
        # 读取图片
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"[ParkingChangeWorker] 警告: 无法读取图片用于绘制检测区域: {image_path}")
            return image_path
        
        # 创建 space_id 到 space 的映射
        space_map = {space.id: space for space in spaces}
        
        # 绘制每个检测区域（绿色框）
        for space_id, region in detection_regions.items():
            x, y, w, h = region
            x1, y1 = x, y
            x2, y2 = x + w, y + h
            
            # 绘制绿色矩形框（BGR格式，绿色是 (0, 255, 0)）
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # 添加车位名称标签
            space = space_map.get(space_id)
            if space and space.space_name:
                label = space.space_name
                # 计算文字位置（在框的上方）
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.6
                thickness = 2
                (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
                
                # 确保文字不超出图片边界
                text_x = max(0, min(x1, img.shape[1] - text_width))
                text_y = max(text_height + baseline, y1 - 5)
                
                # 绘制文字背景（半透明黑色）
                cv2.rectangle(img, 
                            (text_x, text_y - text_height - baseline),
                            (text_x + text_width, text_y + baseline),
                            (0, 0, 0), -1)
                
                # 绘制文字（绿色）
                cv2.putText(img, label, (text_x, text_y),
                          font, font_scale, (0, 255, 0), thickness)
        
        # 确定输出路径
        if output_path is None:
            # 自动生成：原文件名_detected.jpg
            output_path = image_path.parent / f"{image_path.stem}_detected{image_path.suffix}"
        else:
            output_path = Path(output_path)
        
        # 保存图片
        cv2.imwrite(str(output_path), img)
        print(f"[ParkingChangeWorker] ✓ 已保存检测区域标记图: {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"[ParkingChangeWorker] 绘制检测区域失败: {e}")
        import traceback
        traceback.print_exc()
        return image_path


def _get_channel_config_and_spaces(db, task: Task) -> Tuple[ChannelConfig | None, List[ParkingSpace]]:
    """根据任务的 IP + 通道找到对应的 ChannelConfig 及其车位列表。"""
    ip = (task.ip or "").strip()
    ch_code = (task.channel or "").strip().lower()
    if not ip or not ch_code:
        return None, []

    nvr = db.query(NvrConfig).filter(NvrConfig.nvr_ip == ip).first()
    if not nvr:
        return None, []

    channel_cfg = (
        db.query(ChannelConfig)
        .filter(
            ChannelConfig.nvr_config_id == nvr.id,
            ChannelConfig.channel_code == ch_code,
        )
        .first()
    )
    if not channel_cfg:
        return None, []

    spaces = (
        db.query(ParkingSpace)
        .filter(ParkingSpace.channel_config_id == channel_cfg.id)
        .all()
    )
    return channel_cfg, spaces


def _detect_weather_condition(img: np.ndarray, brightness: float, clarity: float) -> str:
    """检测天气条件（雨天、雾天、阴天、晴天）。
    
    基于图像特征分析：
    - 雨天：较暗、有反光区域、对比度降低、可能有水珠特征
    - 雾天：模糊、对比度低、整体偏灰白色、能见度差
    - 阴天：光照均匀但较暗、对比度适中、无强烈阴影
    - 晴天：光照充足、对比度高、图像清晰、可能有强烈阴影
    
    参数:
        img: BGR图像数组
        brightness: 平均亮度
        clarity: 清晰度（Laplacian方差）
    
    返回:
        天气条件字符串："rainy" | "foggy" | "cloudy" | "sunny"
    """
    try:
        # 转换为灰度图
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        
        # 计算对比度（标准差）
        contrast = float(np.std(gray))
        
        # 计算饱和度（HSV S通道的平均值）
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV) if len(img.shape) == 3 else None
        saturation = float(np.mean(hsv[:, :, 1])) if hsv is not None else 50.0
        
        # 检测高光区域（反光，可能是雨天）
        high_brightness_ratio = float(np.sum(gray > 200) / gray.size)
        
        # 检测低对比度区域（可能是雾天）
        low_contrast_ratio = float(np.sum(np.abs(gray.astype(float) - brightness) < 20) / gray.size)
        
        # 1. 雾天检测：模糊 + 低对比度 + 低饱和度
        if clarity < CLARITY_THRESHOLD * 0.7 and contrast < 30 and saturation < 40:
            return "foggy"
        
        # 2. 雨天检测：较暗 + 有反光区域 + 对比度降低
        if brightness < 100 and high_brightness_ratio > 0.05 and contrast < 40:
            return "rainy"
        
        # 3. 阴天检测：光照均匀但较暗 + 对比度适中 + 无强烈阴影
        if brightness < 120 and 30 <= contrast <= 50 and saturation < 60:
            return "cloudy"
        
        # 4. 晴天：默认情况（光照充足、对比度高、清晰）
        return "sunny"
        
    except Exception as e:
        print(f"[ParkingChangeWorker] 天气检测失败: {e}")
        return "sunny"  # 默认返回晴天


def _determine_day_night(image_time: datetime | None, brightness: float) -> str:
    """判断是白天还是晚上。
    
    优先使用时间判断，如果时间不可用则使用图像亮度判断。
    
    参数:
        image_time: 图像时间（可选）
        brightness: 图像平均亮度 (0-255)
    
    返回:
        "day" | "night"
    """
    if image_time:
        hour = image_time.hour
        # 6:00-18:00 视为白天，其他时间视为晚上
        if 6 <= hour < 18:
            return "day"
        else:
            return "night"
    else:
        # 如果没有时间信息，使用亮度判断
        # 亮度 >= 100 视为白天，< 100 视为晚上
        if brightness >= 100:
            return "day"
        else:
            return "night"


def _get_image_quality_description(image_quality: Dict[str, Any]) -> str:
    """生成图像质量的文字描述。
    
    参数:
        image_quality: 图像质量分析结果
    
    返回:
        质量描述字符串
    """
    brightness = image_quality.get("brightness", 128.0)
    clarity = image_quality.get("clarity", 100.0)
    interference_level = image_quality.get("interference_level", "normal")
    is_overexposed = image_quality.get("is_overexposed", False)
    is_underexposed = image_quality.get("is_underexposed", False)
    is_blurry = image_quality.get("is_blurry", False)
    weather = image_quality.get("weather", "sunny")
    
    quality_parts = []
    
    # 亮度评估
    if is_overexposed:
        quality_parts.append("过曝")
    elif is_underexposed:
        quality_parts.append("欠曝")
    elif brightness < 80:
        quality_parts.append("较暗")
    elif brightness < 120:
        quality_parts.append("偏暗")
    elif brightness > 200:
        quality_parts.append("较亮")
    else:
        quality_parts.append("亮度正常")
    
    # 清晰度评估
    if is_blurry:
        quality_parts.append("模糊")
    elif clarity < CLARITY_THRESHOLD * 0.7:
        quality_parts.append("清晰度较低")
    elif clarity < CLARITY_THRESHOLD:
        quality_parts.append("清晰度一般")
    else:
        quality_parts.append("清晰")
    
    # 干扰等级
    interference_names = {"high": "高干扰", "normal": "中等干扰", "low": "低干扰"}
    quality_parts.append(interference_names.get(interference_level, "未知"))
    
    # 天气
    weather_names = {"rainy": "雨天", "foggy": "雾天", "cloudy": "阴天", "sunny": "晴天"}
    quality_parts.append(weather_names.get(weather, "未知"))
    
    return " | ".join(quality_parts)


def _analyze_image_quality(image_path: Path, image_time: datetime | None = None) -> Dict[str, Any]:
    """分析图像质量，判定干扰等级和天气条件。
    
    参数:
        image_path: 图像路径
        image_time: 图像时间（可选，用于判断白天/晚上）
    
    返回:
        {
            "brightness": float,  # 平均亮度 (0-255)
            "clarity": float,  # 清晰度 (Laplacian方差)
            "interference_level": str,  # "high", "normal", "low"
            "is_overexposed": bool,  # 是否过曝
            "is_underexposed": bool,  # 是否欠曝
            "is_blurry": bool,  # 是否模糊
            "weather": str,  # 天气条件 "rainy" | "foggy" | "cloudy" | "sunny"
            "day_night": str,  # "day" | "night"
            "quality_description": str,  # 质量描述文字
        }
    """
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return {
                "brightness": 128.0,
                "clarity": 0.0,
                "interference_level": "high",
                "is_overexposed": False,
                "is_underexposed": False,
                "is_blurry": True,
                "weather": "sunny",
            }
        
        # 转换为灰度图
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 计算平均亮度
        brightness = float(np.mean(gray))
        
        # 计算清晰度（Laplacian方差）
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        clarity = float(laplacian_var)
        
        # 判定干扰等级
        is_overexposed = brightness > BRIGHTNESS_HIGH_THRESHOLD
        is_underexposed = brightness < BRIGHTNESS_LOW_THRESHOLD
        is_blurry = clarity < CLARITY_THRESHOLD
        
        if is_overexposed or is_underexposed or is_blurry:
            interference_level = "high"
        elif abs(brightness - 128) > 30 or clarity < CLARITY_THRESHOLD * 1.5:
            interference_level = "normal"
        else:
            interference_level = "low"
        
        # 检测天气条件
        weather = _detect_weather_condition(img, brightness, clarity)
        
        # 判断白天/晚上
        day_night = _determine_day_night(image_time, brightness)
        
        # 生成质量描述
        quality_result = {
            "brightness": brightness,
            "clarity": clarity,
            "interference_level": interference_level,
            "is_overexposed": is_overexposed,
            "is_underexposed": is_underexposed,
            "is_blurry": is_blurry,
            "weather": weather,
            "day_night": day_night,
        }
        quality_description = _get_image_quality_description(quality_result)
        quality_result["quality_description"] = quality_description
        
        return quality_result
    except Exception as e:
        print(f"[ParkingChangeWorker] 图像质量分析失败: {e}")
        return {
            "brightness": 128.0,
            "clarity": 0.0,
            "interference_level": "high",
            "is_overexposed": False,
            "is_underexposed": False,
            "is_blurry": True,
            "weather": "sunny",
            "day_night": "day",
            "quality_description": "分析失败",
        }


def _calculate_dynamic_similarity_threshold(
    base_threshold: float,
    current_time: datetime,
    prev_time: datetime | None,
    image_quality_curr: Dict[str, Any],
    image_quality_prev: Dict[str, Any] | None = None,
    time_diff_seconds: float | None = None,
    is_short_interval: bool = False,
    is_cross_day: bool = False,
) -> Tuple[float, str]:
    """根据时间段、图像质量和时间间隔动态计算相似度阈值。
    
    考虑因素：
    1. 时间段（凌晨、白天、傍晚、夜间）- 不同时间段光照条件不同
    2. 图像质量（亮度、清晰度）- 暗光/模糊环境下特征提取不稳定
    3. 时间间隔（短间隔、长间隔）- 短间隔时车辆变化可能性低
    4. 跨天情况 - 跨天时阈值降低
    
    参数:
        base_threshold: 基础阈值
        current_time: 当前截图时间
        prev_time: 上一张截图时间
        image_quality_curr: 当前图像质量分析结果
        image_quality_prev: 上一张图像质量分析结果（可选）
        time_diff_seconds: 时间间隔（秒）
        is_short_interval: 是否为短时间间隔
        is_cross_day: 是否跨天
    
    返回:
        (调整后的阈值, 阈值描述字符串)
    """
    threshold = base_threshold
    adjustments = []
    
    # 1. 短时间间隔：最优先，使用最宽松的阈值
    if is_short_interval and time_diff_seconds is not None:
        threshold = VEHICLE_SIMILARITY_THRESHOLD_SHORT_INTERVAL
        adjustments.append(f"短间隔({time_diff_seconds:.0f}秒)")
        return threshold, "短间隔"
    
    # 2. 跨天：使用跨天阈值
    if is_cross_day:
        threshold = VEHICLE_SIMILARITY_THRESHOLD_CROSS_DAY
        adjustments.append("跨天")
        return threshold, "跨天"
    
    # 3. 时间段调整（基于当前时间）
    current_hour = current_time.hour
    time_period_factor = 1.0
    time_period_name = ""
    
    if TIME_PERIOD_EARLY_MORNING[0] <= current_hour < TIME_PERIOD_EARLY_MORNING[1]:
        # 凌晨 0-6点
        time_period_factor = TIME_PERIOD_THRESHOLD_FACTOR_EARLY_MORNING
        time_period_name = "凌晨"
    elif TIME_PERIOD_DAYTIME[0] <= current_hour < TIME_PERIOD_DAYTIME[1]:
        # 白天 6-18点
        time_period_factor = TIME_PERIOD_THRESHOLD_FACTOR_DAYTIME
        time_period_name = "白天"
    elif TIME_PERIOD_EVENING[0] <= current_hour < TIME_PERIOD_EVENING[1]:
        # 傍晚 18-20点
        time_period_factor = TIME_PERIOD_THRESHOLD_FACTOR_EVENING
        time_period_name = "傍晚"
    else:
        # 夜间 20-24点
        time_period_factor = TIME_PERIOD_THRESHOLD_FACTOR_NIGHT
        time_period_name = "夜间"
    
    threshold *= time_period_factor
    if time_period_factor < 1.0:
        adjustments.append(f"{time_period_name}(系数{time_period_factor:.2f})")
    
    # 4. 图像质量调整（亮度）
    brightness_curr = image_quality_curr.get("brightness", 128.0)
    brightness_factor = 1.0
    
    if brightness_curr < 50:
        # 极暗环境
        brightness_factor = BRIGHTNESS_THRESHOLD_FACTOR_VERY_DARK
        adjustments.append(f"极暗(亮度{brightness_curr:.1f})")
    elif brightness_curr < 80:
        # 暗光环境
        brightness_factor = BRIGHTNESS_THRESHOLD_FACTOR_DARK
        adjustments.append(f"暗光(亮度{brightness_curr:.1f})")
    
    threshold *= brightness_factor
    
    # 5. 图像质量调整（清晰度）
    clarity_curr = image_quality_curr.get("clarity", 100.0)
    if clarity_curr < CLARITY_THRESHOLD:
        # 低清晰度
        threshold *= CLARITY_THRESHOLD_FACTOR_LOW
        adjustments.append(f"模糊(清晰度{clarity_curr:.1f})")
    
    # 6. 天气条件调整
    weather_curr = image_quality_curr.get("weather", "sunny")
    weather_factor = 1.0
    
    if weather_curr == "rainy":
        weather_factor = WEATHER_THRESHOLD_FACTOR_RAINY
        adjustments.append("雨天")
    elif weather_curr == "foggy":
        weather_factor = WEATHER_THRESHOLD_FACTOR_FOGGY
        adjustments.append("雾天")
    elif weather_curr == "cloudy":
        weather_factor = WEATHER_THRESHOLD_FACTOR_CLOUDY
        adjustments.append("阴天")
    # sunny: weather_factor = 1.0 (标准)
    
    threshold *= weather_factor
    
    # 7. 如果两张图都在暗光环境，进一步放宽
    if prev_time and image_quality_prev:
        brightness_prev = image_quality_prev.get("brightness", 128.0)
        if brightness_curr < 80 and brightness_prev < 80:
            # 两张图都在暗光环境，特征提取都不稳定，进一步放宽
            threshold *= 0.95
            adjustments.append("双暗光环境")
        
        # 如果两张图天气条件都不好（雨天或雾天），进一步放宽
        weather_prev = image_quality_prev.get("weather", "sunny")
        if weather_curr in ("rainy", "foggy") and weather_prev in ("rainy", "foggy"):
            threshold *= 0.95
            adjustments.append("双恶劣天气")
    
    # 确保阈值不低于最小值
    min_threshold = 0.50  # 最低阈值50%
    threshold = max(min_threshold, threshold)
    
    # 生成描述字符串
    if adjustments:
        # 如果有调整项，组合时间段和调整项
        if time_period_name:
            threshold_desc = f"{time_period_name} + " + " + ".join(adjustments)
        else:
            threshold_desc = " + ".join(adjustments)
    else:
        # 如果没有调整项，只显示时间段
        threshold_desc = time_period_name or "标准"
    
    return threshold, threshold_desc


def _compare_vehicle_features(
    features_curr: Dict[str, Any],
    features_prev: Dict[str, Any],
    is_cross_day: bool = False,
) -> float:
    """比对两辆车的特征，返回相似度得分（0.0-1.0）。
    
    使用 Hellinger 距离计算直方图相似度，加权融合颜色、形状、结构特征。
    
    参数:
        features_curr: 当前车辆特征
        features_prev: 历史车辆特征
        is_cross_day: 是否跨天（跨天时阈值降低）
    
    返回:
        相似度得分 (0.0-1.0)，1.0 表示完全相同
    """
    try:
        # 提取直方图
        hist_h_curr = np.array(features_curr.get("color_hist_h", [0.0] * 32))
        hist_s_curr = np.array(features_curr.get("color_hist_s", [0.0] * 32))
        hist_h_prev = np.array(features_prev.get("color_hist_h", [0.0] * 32))
        hist_s_prev = np.array(features_prev.get("color_hist_s", [0.0] * 32))
        
        # 计算 Hellinger 距离（直方图相似度）
        # Hellinger 距离 = sqrt(sum((sqrt(p_i) - sqrt(q_i))^2)) / sqrt(2)
        # 相似度 = 1 - Hellinger距离
        def hellinger_distance(p, q):
            p_sqrt = np.sqrt(p + 1e-10)
            q_sqrt = np.sqrt(q + 1e-10)
            return np.sqrt(np.sum((p_sqrt - q_sqrt) ** 2)) / np.sqrt(2)
        
        dist_h = hellinger_distance(hist_h_curr, hist_h_prev)
        dist_s = hellinger_distance(hist_s_curr, hist_s_prev)
        similarity_color = 1.0 - (dist_h + dist_s) / 2.0
        
        # 宽高比相似度
        aspect_curr = features_curr.get("aspect_ratio", 1.8)
        aspect_prev = features_prev.get("aspect_ratio", 1.8)
        aspect_diff = abs(aspect_curr - aspect_prev) / max(aspect_curr, aspect_prev, 1e-6)
        similarity_aspect = 1.0 - min(aspect_diff, 1.0)
        
        # 雨刮特征相似度（布尔值）
        wiper_curr = features_curr.get("has_rear_wiper", False)
        wiper_prev = features_prev.get("has_rear_wiper", False)
        similarity_wiper = 1.0 if wiper_curr == wiper_prev else 0.5
        
        # 加权融合（颜色权重最高）
        # 在夜间环境下，提高颜色相似度的权重（因为光照变化主要影响颜色）
        # 同时降低宽高比和雨刮特征的权重（因为这些特征在夜间更不稳定）
        # 通过直方图的平均值来判断是否为夜间环境
        hist_h_mean_curr = np.mean(hist_h_curr)
        hist_s_mean_curr = np.mean(hist_s_curr)
        hist_h_mean_prev = np.mean(hist_h_prev)
        hist_s_mean_prev = np.mean(hist_s_prev)
        # 如果直方图整体较暗（H通道和S通道的值都较低），可能是夜间环境
        is_likely_dark = (hist_h_mean_curr < 0.1 and hist_s_mean_curr < 0.1) or \
                        (hist_h_mean_prev < 0.1 and hist_s_mean_prev < 0.1)
        
        if is_likely_dark:
            # 夜间环境下，提高颜色相似度权重，降低其他特征权重
            # 因为夜间光照变化主要影响颜色，而形状特征相对稳定
            similarity = (
                similarity_color * 0.70 +
                similarity_aspect * 0.20 +
                similarity_wiper * 0.10
            )
        else:
            # 标准权重
            similarity = (
                similarity_color * 0.60 +
                similarity_aspect * 0.30 +
                similarity_wiper * 0.10
            )
        
        return float(max(0.0, min(1.0, similarity)))
    except Exception as e:
        print(f"[ParkingChangeWorker] 特征比对失败: {e}")
        return 0.0


def _verify_and_revoke_false_leave(
    db,
    channel_config_id: int,
    space_id: int,
    space_name: str,
    current_screenshot_id: int,
    current_screenshot_time: datetime,
    current_has_car: bool,
) -> bool:
    """验证并撤销误判的"离开"事件。
    
    检查上一张截图（约10分钟前）是否有该车位的"leave"事件。
    如果当前截图显示车位有车，则撤销之前的"leave"判定。
    
    参数:
        db: 数据库会话
        channel_config_id: 通道配置ID
        space_id: 车位ID
        space_name: 车位名称（用于日志）
        current_screenshot_id: 当前截图ID
        current_screenshot_time: 当前截图时间
        current_has_car: 当前截图该车位是否有车
    
    返回:
        True 如果撤销了误判的leave事件，False 否则
    """
    if not current_has_car:
        # 当前无车，不撤销
        return False
    
    try:
        # 查找上一张截图（约10分钟前）中该车位的"leave"事件
        # 时间范围：5-15分钟前（允许一定容差）
        time_min = current_screenshot_time - timedelta(seconds=900)  # 15分钟前
        time_max = current_screenshot_time - timedelta(seconds=300)   # 5分钟前
        
        prev_leave_change = (
            db.query(ParkingChange)
            .join(Screenshot, ParkingChange.screenshot_id == Screenshot.id)
            .filter(
                ParkingChange.channel_config_id == channel_config_id,
                ParkingChange.space_id == space_id,
                ParkingChange.change_type == "leave",  # 只查找leave事件
                Screenshot.id < current_screenshot_id,  # 必须是之前的截图
                Screenshot.created_at >= time_min,
                Screenshot.created_at <= time_max,
            )
            .order_by(desc(Screenshot.created_at))  # 找到最近的一个
            .first()
        )
        
        if not prev_leave_change:
            return False
        
        # 找到了待确认的leave事件，当前截图显示有车，说明是误判
        print(f"[ParkingChangeWorker] 🔍 发现待确认的leave事件:")
        print(f"   车位: {space_name}")
        print(f"   上一张截图ID: {prev_leave_change.screenshot_id}")
        print(f"   当前截图ID: {current_screenshot_id}")
        print(f"   当前检测: 有车")
        print(f"   ⚠️  上一张判定为'离开'，但当前有车 -> 判定为误判（可能是路过车辆遮挡）")
        
        # 更新之前的leave记录为"无变化"
        prev_leave_change.change_type = None
        # 更新curr_occupied为True（因为当前有车，说明之前的状态应该是有车）
        prev_leave_change.curr_occupied = True
        
        # 更新快照记录：减少change_count
        prev_snapshot = (
            db.query(ParkingChangeSnapshot)
            .filter(ParkingChangeSnapshot.screenshot_id == prev_leave_change.screenshot_id)
            .first()
        )
        if prev_snapshot and prev_snapshot.change_count > 0:
            old_count = prev_snapshot.change_count
            prev_snapshot.change_count -= 1
            print(f"   ✓ 已更新快照记录 (screenshot_id={prev_leave_change.screenshot_id})，change_count: {old_count} -> {prev_snapshot.change_count}")
            
            # 如果change_count变为0，可以考虑删除快照记录（但保留变化记录）
            if prev_snapshot.change_count == 0:
                print(f"   ⚠️  快照记录的change_count已为0，但保留快照记录以便追溯")
        
        print(f"   ✓ 已撤销误判的leave事件，更新为'无变化'")
        return True
        
    except Exception as e:
        print(f"[ParkingChangeWorker] 验证leave事件失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def _get_prev_occupied_for_channel(
    db,
    channel_config_id: int,
    space_id: int,
    current_screenshot_id: int,
    current_screenshot_time: datetime | None = None,
    current_task_id: int = None,  # 为兼容旧调用保留参数，但不再用于过滤
    max_time_gap_seconds: int = 3600,  # 最大时间间隔（默认1小时）
) -> Tuple[bool | None, int | None, Dict[str, Any] | None]:
    """获取同一通道下该车位在上一张截图中的占用状态（按截图时间顺序，全局连续比较）。

    逻辑说明：
    - 不再局限于“同一 task_id”，而是基于 channel_config_id + screenshot_id
      在整个时间线上连续比较：图1对比图2，图2对比图3，图3对比图4...
    - 这样可以跨 Task 连续追踪同一通道的车位变化，更符合“同一通道”的业务语义。
    """
    # 获取当前截图的时间（必须）
    if current_screenshot_time is None:
        current_screenshot = db.query(Screenshot).filter(Screenshot.id == current_screenshot_id).first()
        if current_screenshot and current_screenshot.created_at:
            current_screenshot_time = current_screenshot.created_at
        else:
            # 如果没有时间信息，无法进行时间顺序对比，返回 None
            return None, None, None
    
    # 在 ParkingChange 表中查找同一通道、同一车位、当前截图时间之前最近的一条记录
    # 必须按时间排序，不能按 screenshot_id 排序
    prev_change = (
        db.query(ParkingChange)
        .join(Screenshot, ParkingChange.screenshot_id == Screenshot.id)
        .filter(
            ParkingChange.channel_config_id == channel_config_id,
            ParkingChange.space_id == space_id,
            Screenshot.created_at < current_screenshot_time,  # 按时间过滤，不是按ID
        )
        .order_by(desc(Screenshot.created_at))  # 按时间降序，找到时间上最近的一张
        .first()
    )

    if not prev_change:
        # 没有任何历史记录，视为第一张（上一张状态未知）
        return None, None, None
    
    # 检查时间间隔（必须检查，确保不跳过中间的截图）
    if prev_change.detected_at:
        time_gap = (current_screenshot_time - prev_change.detected_at).total_seconds()
        if time_gap > max_time_gap_seconds:
            # 时间间隔过大（例如超过15分钟），说明跳过了中间的截图，返回 None
            # 这样可以避免 10:00 直接对比 10:30 的情况
            print(f"[ParkingChangeWorker] 警告: 时间间隔过大 ({time_gap:.0f}秒 > {max_time_gap_seconds}秒)，跳过对比。当前: {current_screenshot_time}, 上一张: {prev_change.detected_at}")
            return None, None, None
    
    # 获取上一帧的车辆特征
    prev_features = prev_change.vehicle_features if prev_change.vehicle_features else None
    
    # 直接使用上一条记录中的 curr_occupied 作为上一张图的状态
    return prev_change.curr_occupied, prev_change.screenshot_id, prev_features


def _calculate_position_offset(
    region_curr: Tuple[int, int, int, int] | None,
    region_prev: Tuple[int, int, int, int] | None,
    space_width: int,
) -> float | None:
    """计算两个检测区域之间的位置偏移（相对于车位宽度的比例）。
    
    参数:
        region_curr: 当前检测区域 (x, y, w, h)
        region_prev: 上一帧检测区域 (x, y, w, h)
        space_width: 车位宽度（像素）
    
    返回:
        位置偏移比例（0.0-1.0），None 表示无法计算
    """
    if not region_curr or not region_prev or space_width <= 0:
        return None
    
    x_curr, y_curr, w_curr, h_curr = region_curr
    x_prev, y_prev, w_prev, h_prev = region_prev
    
    # 计算中心点
    center_x_curr = x_curr + w_curr / 2
    center_y_curr = y_curr + h_curr / 2
    center_x_prev = x_prev + w_prev / 2
    center_y_prev = y_prev + h_prev / 2
    
    # 计算欧氏距离
    distance = ((center_x_curr - center_x_prev) ** 2 + (center_y_curr - center_y_prev) ** 2) ** 0.5
    
    # 转换为相对于车位宽度的比例
    offset_ratio = distance / space_width if space_width > 0 else None
    
    return offset_ratio


def _check_state_lock(
    db,
    channel_config_id: int,
    space_id: int,
    current_screenshot_time: datetime,
    max_time_gap_seconds: int = 900,  # 15分钟
) -> Tuple[bool, int]:
    """检查车位状态是否已锁定，以及连续无车帧数。
    
    状态锁逻辑：
    - 如果连续 STATE_LOCK_FRAMES 帧状态不变，则锁定状态
    - 如果状态已锁定，必须连续 STATE_UNLOCK_FRAMES 帧检测到无车才允许离开
    
    参数:
        db: 数据库会话
        channel_config_id: 通道配置ID
        space_id: 车位ID
        current_screenshot_time: 当前截图时间
        max_time_gap_seconds: 最大时间间隔（秒）
    
    返回:
        (is_locked, consecutive_empty_frames)
        - is_locked: 状态是否已锁定
        - consecutive_empty_frames: 连续无车帧数
    """
    if not STATE_LOCK_ENABLED:
        return False, 0
    
    try:
        # 查询最近 STATE_LOCK_FRAMES + STATE_UNLOCK_FRAMES 帧的记录
        recent_changes = (
            db.query(ParkingChange)
            .join(Screenshot, ParkingChange.screenshot_id == Screenshot.id)
            .filter(
                ParkingChange.channel_config_id == channel_config_id,
                ParkingChange.space_id == space_id,
                Screenshot.created_at < current_screenshot_time,
            )
            .order_by(desc(Screenshot.created_at))
            .limit(STATE_LOCK_FRAMES + STATE_UNLOCK_FRAMES + 1)
            .all()
        )
        
        if len(recent_changes) < STATE_LOCK_FRAMES:
            # 历史记录不足，无法判断是否锁定
            return False, 0
        
        # 检查最近 STATE_LOCK_FRAMES 帧是否状态一致
        recent_states = [change.curr_occupied for change in recent_changes[:STATE_LOCK_FRAMES]]
        if len(set(recent_states)) == 1:
            # 状态一致，检查是否锁定
            state_value = recent_states[0]
            # 只有"有车"状态才需要锁定（防止频繁误判为"离开"）
            # 注意：我们也可以锁定"无车"状态（防止频繁误判为"进车"），但当前主要问题是"离开"误判
            is_locked = state_value == True  # 只有"有车"状态才需要锁定
            
            # 计算连续无车帧数（用于判断是否达到解锁条件）
            consecutive_empty = 0
            for change in recent_changes:
                if not change.curr_occupied:
                    consecutive_empty += 1
                else:
                    break
            
            # 计算连续有车帧数（用于判断是否达到锁定条件）
            consecutive_occupied = 0
            for change in recent_changes:
                if change.curr_occupied:
                    consecutive_occupied += 1
                else:
                    break
            
            return is_locked, consecutive_empty
        else:
            # 状态不一致，未锁定
            return False, 0
    except Exception as e:
        print(f"[ParkingChangeWorker] 检查状态锁失败: {e}")
        return False, 0


def _determine_space_state(
    has_car_curr: bool,
    features_curr: Dict[str, Any] | None,
    has_car_prev: bool | None,
    features_prev: Dict[str, Any] | None,
    image_quality: Dict[str, Any],
    image_quality_prev: Dict[str, Any] | None = None,  # 上一张图的图像质量（可选）
    current_time: datetime | None = None,
    prev_time: datetime | None = None,
    space_name: str = "",  # 可选：车位名称，用于日志输出
    confidence_curr: float = 0.0,  # 当前帧YOLO置信度
    detection_region_curr: Tuple[int, int, int, int] | None = None,  # 当前检测区域 (x, y, w, h)
    detection_region_prev: Tuple[int, int, int, int] | None = None,  # 上一帧检测区域 (x, y, w, h)
    space_width: int = 0,  # 车位宽度（用于计算位置偏移）
) -> Tuple[bool, float, str]:
    """状态决策引擎：根据当前检测结果、历史状态和图像质量，确定最终的车位状态。
    
    参数:
        has_car_curr: 当前帧YOLO检测结果（是否有车）
        features_curr: 当前帧车辆特征（如果有车）
        has_car_prev: 上一帧最终状态（curr_occupied）
        features_prev: 上一帧车辆特征（如果有车）
        image_quality: 当前图像质量分析结果
        image_quality_prev: 上一张图的图像质量分析结果（可选）
        current_time: 当前截图时间
        prev_time: 上一帧截图时间
    
    返回:
        (curr_occupied, detection_confidence, change_type)
        - curr_occupied: 最终状态（经过多帧平滑+特征比对后的可信状态）
        - detection_confidence: 综合置信度（检测置信度或特征相似度）
        - change_type: 变化类型（arrive/leave/None）
    """
    # 判断是否跨天和时间间隔
    is_cross_day = False
    time_diff_seconds = None
    is_short_interval = False
    if prev_time and current_time:
        time_diff_seconds = (current_time - prev_time).total_seconds()
        is_cross_day = time_diff_seconds > 86400  # 超过24小时视为跨天
        is_short_interval = time_diff_seconds < SHORT_INTERVAL_SECONDS  # 时间间隔很短（如连续截图）
    
    # 如果没有提供当前时间，使用当前UTC时间
    if current_time is None:
        current_time = datetime.utcnow()
    
    # 获取干扰等级
    interference_level = image_quality.get("interference_level", "normal")
    is_high_interference = interference_level == "high"
    
    # 情况1: 第一张图（无历史记录）
    if has_car_prev is None:
        if has_car_curr:
            if space_name:
                print(f"      [决策] 第一张图，检测到车 -> 记录状态但不标记为进车（避免误判）")
            # 第一张图检测到车，记录状态但不标记为变化（因为无法确定是否真的是"进车"）
            # 只有在下一张图对比时才能确定是否有变化
            return True, 0.8, None  # 第一张图检测到车，不标记为进车，避免误判
        else:
            if space_name:
                print(f"      [决策] 第一张图，无车 -> 无变化")
            return False, 0.0, None  # 第一张图无车，无变化
    
    # 情况2: 当前无车
    if not has_car_curr:
        # 如果历史有车，需要判断是真实离场还是干扰误判
        if has_car_prev:
            # 第三步：状态锁机制 - 如果状态已锁定，需要连续多帧无车才允许离开
            # 注意：状态锁检查需要在调用此函数之前完成，因为需要查询数据库
            # 这里我们通过一个标志参数来传递状态锁信息（如果启用）
            # 实际的状态锁检查会在调用此函数之前完成
            #
            # 这里仅保留“高干扰模式”的保护，其余场景直接按照标准逻辑判定离场，
            # 避免因为暗光/时间间隔过短导致真实的“驶离”被长期压制。
            # 高干扰模式下，允许单帧漏检，维持 Occupied
            if is_high_interference and HIGH_ROBUSTNESS_MODE_ENABLED:
                if space_name:
                    print(f"      [决策] 历史有车，当前无车，但高干扰模式 -> 维持有车状态（不判定离场）")
                # 维持上一帧状态（Occupied），不判定为离场
                return True, 0.5, None  # 置信度降低，但不改变状态

            # 标准模式：判定为离场（不再因为暗光/时间短而额外拦截）
            # 注意：如果启用了状态锁，需要在调用此函数之前检查是否锁定；
            # 如果被状态锁拦截，将不会进入到这里。
            if space_name:
                print(f"      [决策] 历史有车，当前无车 -> 判定为离场 (leave)")
            return False, 0.0, "leave"
        else:
            if space_name:
                print(f"      [决策] 历史无车，当前无车 -> 无变化")
            # 历史无车，当前无车，无变化
            return False, 0.0, None
    
    # 情况3: 当前有车
    if has_car_curr:
        # 第一步：最低置信度过滤 - YOLO置信度<50%时不参与"换车"判断
        # 在夜间或暗光环境下，进一步放宽置信度要求（降低到40%）
        brightness_curr = image_quality.get("brightness", 128.0)
        is_dark = brightness_curr < 80  # 暗光环境
        min_confidence_threshold = MIN_YOLO_CONFIDENCE_FOR_CHANGE_DETECTION
        if is_dark:
            # 暗光环境下，降低置信度阈值到40%
            min_confidence_threshold = max(0.40, MIN_YOLO_CONFIDENCE_FOR_CHANGE_DETECTION * 0.8)
            if space_name:
                print(f"      [决策] 暗光环境，降低置信度阈值: {min_confidence_threshold:.2%} (标准: {MIN_YOLO_CONFIDENCE_FOR_CHANGE_DETECTION:.2%})")
        
        if confidence_curr < min_confidence_threshold:
            if space_name:
                print(f"      [决策] 当前有车，但YOLO置信度({confidence_curr:.2%}) < 最低阈值({min_confidence_threshold:.2%})")
            # 如果历史有车，维持状态；如果历史无车，但置信度太低，不判定为进车
            if has_car_prev:
                if space_name:
                    print(f"        历史有车 -> 维持有车状态（置信度低，不参与换车判断）")
                return True, confidence_curr, None  # 维持 Occupied，但置信度降低
            else:
                if space_name:
                    print(f"        历史无车 -> 置信度太低，不判定为进车（避免误判）")
                return False, confidence_curr, None  # 置信度太低，不判定为进车
        
        # 如果历史无车，判定为进车
        if not has_car_prev:
            confidence = 0.8 if features_curr else 0.6
            if space_name:
                print(f"      [决策] 历史无车，当前有车 -> 判定为进车 (arrive), 置信度={confidence:.2%}")
            return True, confidence, "arrive"
        
        # 如果历史有车，需要判断是否为同一辆车
        if features_curr and features_prev:
            # 进行特征比对
            similarity = _compare_vehicle_features(
                features_curr,
                features_prev,
                is_cross_day=is_cross_day,
            )
            
            # 使用动态阈值计算（考虑时间段、图像质量、时间间隔等因素）
            base_threshold = VEHICLE_SIMILARITY_THRESHOLD_SAME_DAY
            threshold, threshold_desc = _calculate_dynamic_similarity_threshold(
                base_threshold=base_threshold,
                current_time=current_time,
                prev_time=prev_time,
                image_quality_curr=image_quality,
                image_quality_prev=image_quality_prev,  # 使用上一张图的图像质量
                time_diff_seconds=time_diff_seconds,
                is_short_interval=is_short_interval,
                is_cross_day=is_cross_day,
            )
            
            if space_name:
                print(f"      [决策] 历史有车，当前有车 -> 进行特征比对")
                if time_diff_seconds is not None:
                    print(f"        时间间隔: {time_diff_seconds:.0f} 秒 ({time_diff_seconds/60:.1f} 分钟)")
                print(f"        相似度: {similarity:.2%}, 动态阈值: {threshold:.2%} ({threshold_desc})")
            
            # 第二步：状态延续保护机制
            # 即使相似度略低于阈值，如果满足条件仍视为同一辆车
            should_apply_protection = False
            protection_reason = ""
            
            if STATE_CONTINUATION_PROTECTION_ENABLED:
                # 检查时间间隔
                time_ok = time_diff_seconds is not None and time_diff_seconds <= STATE_CONTINUATION_TIME_THRESHOLD
                # 检查位置偏移
                position_ok = False
                if detection_region_curr and detection_region_prev and space_width > 0:
                    position_offset = _calculate_position_offset(
                        detection_region_curr,
                        detection_region_prev,
                        space_width
                    )
                    if position_offset is not None:
                        position_ok = position_offset < STATE_CONTINUATION_POSITION_THRESHOLD
                        if space_name:
                            print(f"        位置偏移: {position_offset:.2%} (阈值: {STATE_CONTINUATION_POSITION_THRESHOLD:.2%})")
                
                # 检查相似度是否在允许范围内（允许低于阈值一定比例）
                # 在夜间或暗光环境下，放宽相似度要求
                brightness_curr = image_quality.get("brightness", 128.0)
                is_dark = brightness_curr < 80  # 暗光环境
                similarity_margin = STATE_CONTINUATION_SIMILARITY_MARGIN
                if is_dark:
                    # 暗光环境下，允许更大的相似度容差（增加50%）
                    similarity_margin = STATE_CONTINUATION_SIMILARITY_MARGIN * 1.5
                    if space_name:
                        print(f"        暗光环境，放宽相似度容差: {similarity_margin:.2%} (标准: {STATE_CONTINUATION_SIMILARITY_MARGIN:.2%})")
                
                similarity_ok = similarity >= (threshold - similarity_margin)
                
                # 如果满足时间和位置条件，即使相似度略低，也给予更大的容差（夜间环境下）
                if time_ok and position_ok:
                    if similarity_ok:
                        should_apply_protection = True
                        protection_reason = f"时间间隔≤{STATE_CONTINUATION_TIME_THRESHOLD}秒且位置偏移<{STATE_CONTINUATION_POSITION_THRESHOLD:.0%}"
                    elif is_dark and similarity >= (threshold - similarity_margin * 1.5):
                        # 夜间环境下，如果相似度在更大容差范围内，也给予保护
                        should_apply_protection = True
                        protection_reason = f"时间间隔≤{STATE_CONTINUATION_TIME_THRESHOLD}秒且位置偏移<{STATE_CONTINUATION_POSITION_THRESHOLD:.0%}（夜间放宽）"
            
            if similarity >= threshold:
                # 同一辆车，状态延续
                if space_name:
                    print(f"        相似度 >= 阈值 -> 同一辆车，状态延续（无变化）")
                return True, similarity, None
            elif should_apply_protection:
                # 状态延续保护：相似度略低于阈值，但满足保护条件
                if space_name:
                    print(f"        相似度略低于阈值，但满足状态延续保护条件 ({protection_reason}) -> 视为同一辆车，状态延续")
                return True, similarity, None
            else:
                # 不同车，换车行为
                # 注意：虽然状态都是"有车"，但这是换车，不是"进车"
                # 为了区分"换车"和真正的"进车"，这里标记为 None，避免误判
                if space_name:
                    print(f"        相似度 < 阈值 -> 不同车辆，判定为换车（但不标记为进车，避免误判）")
                # 换车情况：状态都是"有车"，不标记为"进车"，避免用户看到"有车 → 有车"但显示"进车"的困惑
                return True, similarity, None
        else:
            # 特征缺失，无法比对，保守处理
            # 如果有历史状态，维持状态；否则使用当前检测结果
            if has_car_prev:
                if space_name:
                    print(f"      [决策] 历史有车，当前有车，但特征缺失 -> 维持有车状态，置信度降低")
                return True, 0.6, None  # 维持 Occupied，但置信度降低
            else:
                if space_name:
                    print(f"      [决策] 历史无车，当前有车（特征缺失）-> 判定为进车 (arrive)")
                return True, 0.7, "arrive"
    
    # 默认情况（理论上不会到达）
    return False, 0.0, None


def process_pending_screenshots(batch_size: int = 10) -> int:
    """处理一批待检测截图，返回本次处理的数量。"""
    with SessionLocal() as db:
        shots: List[Screenshot] = (
            db.query(Screenshot)
            .filter(Screenshot.yolo_status == "pending")
            .order_by(Screenshot.id.asc())
            .limit(batch_size)
            .all()
        )
        if not shots:
            return 0

        processed = 0
        for shot in shots:
            try:
                print(f"\n{'='*80}")
                print(f"[ParkingChangeWorker] 开始处理截图 ID={shot.id}, 文件路径={shot.file_path}")
                print(f"{'='*80}")
                
                shot.yolo_status = "processing"
                shot.yolo_last_error = None
                db.flush()

                task = db.query(Task).filter(Task.id == shot.task_id).first()
                if not task:
                    print(f"[ParkingChangeWorker] ❌ 截图 ID={shot.id} 关联的 Task (ID={shot.task_id}) 不存在，跳过")
                    shot.yolo_status = "failed"
                    shot.yolo_last_error = "关联 Task 不存在"
                    continue

                print(f"[ParkingChangeWorker] 任务信息: ID={task.id}, IP={task.ip}, 通道={task.channel}, 日期={task.date}")

                channel_cfg, spaces = _get_channel_config_and_spaces(db, task)
                if not channel_cfg or not spaces:
                    print(f"[ParkingChangeWorker] ⚠️  截图 ID={shot.id} 没有通道配置或车位配置")
                    print(f"   通道配置: {'存在' if channel_cfg else '不存在'}")
                    print(f"   车位数量: {len(spaces) if spaces else 0}")
                    # 没有通道/车位配置，直接标记 done，但不产生变化记录
                    shot.yolo_status = "done"
                    continue

                print(f"[ParkingChangeWorker] ✓ 通道配置: ID={channel_cfg.id}, 通道={channel_cfg.channel_code}")
                print(f"[ParkingChangeWorker] ✓ 车位配置: 共 {len(spaces)} 个车位")
                for space in spaces:
                    print(f"   - 车位 {space.space_name} (ID={space.id}): 坐标 ({space.bbox_x1},{space.bbox_y1}) -> ({space.bbox_x2},{space.bbox_y2})")

                img_path = Path(shot.file_path)
                if not img_path.is_absolute():
                    img_path = SCREENSHOT_BASE / img_path
                if not img_path.exists():
                    print(f"[ParkingChangeWorker] ❌ 截图 ID={shot.id} 图片文件不存在: {img_path}")
                    shot.yolo_status = "failed"
                    shot.yolo_last_error = f"图片文件不存在: {img_path}"
                    continue

                print(f"[ParkingChangeWorker] ✓ 图片文件存在: {img_path}")

                # 先分析图像质量（用于动态调整检测参数和干扰判定）
                print(f"[ParkingChangeWorker] ========== 图像质量分析 ==========")
                current_screenshot_time = shot.created_at if hasattr(shot, 'created_at') and shot.created_at else None
                image_quality = _analyze_image_quality(img_path, image_time=current_screenshot_time)
                
                # 提取质量信息
                image_brightness = image_quality.get('brightness', 128.0)
                clarity = image_quality.get('clarity', 100.0)
                interference_level = image_quality.get('interference_level', 'normal')
                weather = image_quality.get('weather', 'sunny')
                day_night = image_quality.get('day_night', 'day')
                quality_description = image_quality.get('quality_description', '')
                
                # 天气和时段名称映射
                weather_names = {"rainy": "雨天", "foggy": "雾天", "cloudy": "阴天", "sunny": "晴天"}
                day_night_names = {"day": "白天", "night": "晚上"}
                interference_names = {"high": "高", "normal": "中", "low": "低"}
                
                weather_name = weather_names.get(weather, "未知")
                day_night_name = day_night_names.get(day_night, "未知")
                interference_name = interference_names.get(interference_level, "未知")
                
                # 详细日志输出
                print(f"[ParkingChangeWorker] 📸 图像基本信息:")
                print(f"   文件路径: {img_path.name}")
                if current_screenshot_time:
                    print(f"   截图时间: {current_screenshot_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"   时段识别: {day_night_name} (基于时间: {current_screenshot_time.hour}时)")
                else:
                    print(f"   时段识别: {day_night_name} (基于亮度: {image_brightness:.1f})")
                
                print(f"[ParkingChangeWorker] 📊 图像质量指标:")
                print(f"   平均亮度: {image_brightness:.2f} (范围: 0-255)")
                print(f"   清晰度: {clarity:.2f} (Laplacian方差)")
                print(f"   干扰等级: {interference_name} ({interference_level})")
                print(f"   天气条件: {weather_name}")
                
                print(f"[ParkingChangeWorker] 🔍 质量评估:")
                print(f"   {quality_description}")
                
                # 问题警告
                warnings = []
                if image_brightness < BRIGHTNESS_LOW_THRESHOLD:
                    warnings.append(f"⚠️ 欠曝（亮度={image_brightness:.1f} < {BRIGHTNESS_LOW_THRESHOLD}）")
                elif image_brightness > BRIGHTNESS_HIGH_THRESHOLD:
                    warnings.append(f"⚠️ 过曝（亮度={image_brightness:.1f} > {BRIGHTNESS_HIGH_THRESHOLD}）")
                
                if clarity < CLARITY_THRESHOLD:
                    warnings.append(f"⚠️ 模糊（清晰度={clarity:.1f} < {CLARITY_THRESHOLD}）")
                
                if image_brightness < 120:
                    warnings.append(f"⚠️ 暗光环境（亮度={image_brightness:.1f}），将启用夜间增强和动态阈值调整")
                
                if weather in ("rainy", "foggy"):
                    warnings.append(f"⚠️ 恶劣天气（{weather_name}），将放宽相似度阈值")
                
                if warnings:
                    print(f"[ParkingChangeWorker] ⚠️ 检测到以下问题:")
                    for warning in warnings:
                        print(f"   {warning}")
                else:
                    print(f"[ParkingChangeWorker] ✅ 图像质量良好，无需特殊处理")
                
                print(f"[ParkingChangeWorker] ======================================")

                # 对每个车位坐标区域单独进行 YOLO 检测（包含特征提取）
                # 这样只检测车位范围内的车辆，提高精度和性能
                # 如果区域太小，会回退到使用跟踪区域（track_space）进行检测
                print(f"[ParkingChangeWorker] 开始 YOLO 检测...")
                track_space_str = channel_cfg.track_space if channel_cfg else None
                space_occupied_map, detection_regions, confidence_map, features_map = _detect_space_occupancy(
                    img_path, spaces, track_space_str, extract_features=True, image_brightness=image_brightness
                )
                
                # 输出检测结果
                print(f"[ParkingChangeWorker] YOLO 检测完成，结果如下:")
                for space in spaces:
                    occupied = space_occupied_map.get(space.id, False)
                    confidence = confidence_map.get(space.id, 0.0)
                    has_features = space.id in features_map and features_map[space.id] is not None
                    print(f"   车位 {space.space_name}: {'有车' if occupied else '无车'} (置信度: {confidence:.2%}) {'[已提取特征]' if has_features else '[无特征]'}")
                
                # 在图片上绘制绿色线标记实际检测的区域
                try:
                    _draw_detection_regions(img_path, spaces, detection_regions)
                except Exception as e:
                    # 绘制失败不影响主流程
                    print(f"[ParkingChangeWorker] 绘制检测区域失败（不影响检测）: {e}")

                changes: List[ParkingChange] = []
                changed_count = 0  # 本张图中实际“有变化”的车位数量（arrive/leave）
                # current_screenshot_time 已在图像质量分析时定义（第1072行），这里直接使用
                
                print(f"[ParkingChangeWorker] 开始分析车位状态变化...")
                if current_screenshot_time:
                    print(f"   当前截图时间: {current_screenshot_time.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    print(f"   当前截图时间: 未知")
                
                for space in spaces:
                    print(f"\n  [车位 {space.space_name}] 开始分析...")
                    curr_occupied = space_occupied_map.get(space.id, False)
                    curr_confidence = confidence_map.get(space.id, 0.0)
                    
                    # 延迟确认机制：验证并撤销误判的leave事件
                    # 如果上一张截图（约10分钟前）判定为"离开"，但当前截图显示有车，则撤销之前的判定
                    if current_screenshot_time:
                        revoked = _verify_and_revoke_false_leave(
                            db,
                            channel_cfg.id,
                            space.id,
                            space.space_name,
                            shot.id,
                            current_screenshot_time,
                            curr_occupied,
                        )
                        if revoked:
                            # 如果撤销了误判，需要刷新数据库状态
                            db.flush()
                    
                    # 获取同一通道下上一张截图中该车位的状态和特征（带时间间隔检查）
                    # 截图间隔10分钟，最大允许间隔15分钟（允许一定的容差）
                    prev_occupied, prev_screenshot_id, prev_features = _get_prev_occupied_for_channel(
                        db, 
                        channel_cfg.id, 
                        space.id, 
                        shot.id,
                        current_screenshot_time,
                        task.id,
                        max_time_gap_seconds=900  # 15分钟（截图间隔10分钟，允许15分钟容差）
                    )
                    
                    # 获取上一帧截图时间和图像质量（用于跨天判断和动态阈值计算）
                    prev_time = None
                    prev_image_quality = None
                    if prev_screenshot_id:
                        prev_screenshot = db.query(Screenshot).filter(Screenshot.id == prev_screenshot_id).first()
                        if prev_screenshot and prev_screenshot.created_at:
                            prev_time = prev_screenshot.created_at
                            # 分析上一张截图的图像质量（用于动态阈值调整）
                            if prev_screenshot.file_path:
                                prev_img_path = Path(prev_screenshot.file_path)
                                if not prev_img_path.is_absolute():
                                    prev_img_path = SCREENSHOT_BASE / prev_img_path
                                if prev_img_path.exists():
                                    try:
                                        prev_screenshot_time = prev_screenshot.created_at if prev_screenshot and prev_screenshot.created_at else None
                                        prev_image_quality = _analyze_image_quality(prev_img_path, image_time=prev_screenshot_time)
                                    except Exception as e:
                                        print(f"[ParkingChangeWorker] 分析上一张截图图像质量失败: {e}")
                    
                    # 获取当前帧的检测结果和特征
                    has_car_curr = space_occupied_map.get(space.id, False)
                    features_curr = features_map.get(space.id)
                    curr_confidence = confidence_map.get(space.id, 0.0)
                    detection_region_curr = detection_regions.get(space.id)
                    
                    # 获取上一帧的检测区域
                    # 注意：由于数据库中没有保存检测区域，我们使用智能估算方法
                    # 策略：如果当前帧有车，使用当前检测区域作为上一帧的参考（假设车辆位置变化不大）
                    # 如果当前帧无车但上一帧有车，使用车位坐标作为参考
                    detection_region_prev = None
                    if prev_occupied and prev_screenshot_id:
                        if detection_region_curr:
                            # 优先使用当前帧的检测区域作为参考（更准确，因为车辆位置变化通常不大）
                            detection_region_prev = detection_region_curr
                        else:
                            # 如果当前帧无车，使用车位坐标作为参考
                            detection_region_prev = (
                                int(space.bbox_x1),
                                int(space.bbox_y1),
                                max(1, int(space.bbox_x2)),
                                max(1, int(space.bbox_y2)),
                            )
                    
                    # 获取车位宽度（用于计算位置偏移）
                    space_width = max(1, int(space.bbox_x2))  # bbox_x2 是宽度
                    
                    print(f"    当前检测: {'有车' if has_car_curr else '无车'} (置信度: {curr_confidence:.2%})")
                    if prev_screenshot_id:
                        print(f"    上一张状态: {'有车' if prev_occupied else '无车'} (截图ID: {prev_screenshot_id})")
                        if prev_time:
                            time_gap = (current_screenshot_time - prev_time).total_seconds() if current_screenshot_time and prev_time else None
                            if time_gap:
                                print(f"    时间间隔: {time_gap:.0f} 秒 ({time_gap/60:.1f} 分钟)")
                        if prev_features:
                            print(f"    上一张特征: 已提取")
                        else:
                            print(f"    上一张特征: 无")
                    else:
                        print(f"    上一张状态: 无历史记录（第一张图）")
                    
                    # 第三步：状态锁检查（在调用状态决策引擎之前）
                    is_state_locked = False
                    consecutive_empty_frames = 0
                    if STATE_LOCK_ENABLED and current_screenshot_time:
                        is_state_locked, consecutive_empty_frames = _check_state_lock(
                            db,
                            channel_cfg.id,
                            space.id,
                            current_screenshot_time,
                            max_time_gap_seconds=900,  # 15分钟
                        )
                        if is_state_locked:
                            print(f"    [状态锁] 状态已锁定（连续{STATE_LOCK_FRAMES}帧不变）")
                            if not has_car_curr:
                                print(f"    [状态锁] 当前无车，连续无车帧数: {consecutive_empty_frames}/{STATE_UNLOCK_FRAMES}")
                                if consecutive_empty_frames < STATE_UNLOCK_FRAMES:
                                    print(f"    [状态锁] 未达到解锁条件（需要连续{STATE_UNLOCK_FRAMES}帧无车），维持有车状态")
                                    # 状态已锁定且未达到解锁条件，维持有车状态
                                    curr_occupied_final = True
                                    detection_confidence_final = 0.5
                                    change_type = None
                                    # 跳过状态决策引擎，直接使用锁定状态
                                    print(f"    [状态锁] 跳过状态决策，维持锁定状态")
                                else:
                                    print(f"    [状态锁] 已达到解锁条件，允许离开")
                                    # 已达到解锁条件，继续正常决策流程
                                    is_state_locked = False
                            else:
                                # 当前有车，状态锁不影响决策
                                is_state_locked = False
                    
                    # 调用状态决策引擎（如果状态锁未拦截）
                    if not (is_state_locked and not has_car_curr and consecutive_empty_frames < STATE_UNLOCK_FRAMES):
                        print(f"    调用状态决策引擎...")
                        curr_occupied_final, detection_confidence_final, change_type = _determine_space_state(
                            has_car_curr=has_car_curr,
                            features_curr=features_curr,
                            has_car_prev=prev_occupied,
                            features_prev=prev_features,
                            image_quality=image_quality,
                            image_quality_prev=prev_image_quality,  # 传递上一张图的图像质量
                            current_time=current_screenshot_time or datetime.utcnow(),
                            prev_time=prev_time,
                            space_name=space.space_name,  # 传递车位名称用于日志
                            confidence_curr=curr_confidence,  # 传递当前帧YOLO置信度
                            detection_region_curr=detection_region_curr,  # 传递当前检测区域
                            detection_region_prev=detection_region_prev,  # 传递上一帧检测区域
                            space_width=space_width,  # 传递车位宽度
                        )
                    
                    print(f"    决策结果: 最终状态={'有车' if curr_occupied_final else '无车'}, 置信度={detection_confidence_final:.2%}, 变化类型={change_type or '无变化'}")
                    
                    # 使用决策引擎的结果（已经包含了多帧确认、特征比对和干扰自适应逻辑）
                    curr_occupied = curr_occupied_final
                    curr_confidence = detection_confidence_final
                    # change_type 已由决策引擎确定
                    
                    # 记录所有车位状态（无论是否有变化），用于后续对比
                    # change_type 为 None 表示"无变化"
                    change = ParkingChange(
                        task_id=task.id,
                        screenshot_id=shot.id,
                        channel_config_id=channel_cfg.id,
                        space_id=space.id,
                        space_name=space.space_name,
                        prev_occupied=prev_occupied,  # None 表示"未知"（第一张图）
                        curr_occupied=curr_occupied,  # 经过状态决策引擎处理后的最终状态
                        change_type=change_type,  # 由决策引擎确定（arrive/leave/None）
                        detection_confidence=curr_confidence if curr_confidence > 0 else None,  # 综合置信度（检测置信度或特征相似度）
                        vehicle_features=features_curr,  # 保存当前帧的车辆特征（用于后续比对）
                    )
                    changes.append(change)
                    db.add(change)

                    # 统计有变化的车位数量（只统计 arrive/leave）
                    if change_type in ("arrive", "leave"):
                        changed_count += 1
                        print(f"    ✓ 检测到变化: {change_type}")

                print(f"\n[ParkingChangeWorker] 车位状态分析完成:")
                print(f"   总车位数: {len(spaces)}")
                print(f"   有变化车位: {changed_count} 个")
                print(f"   生成变化记录: {len(changes)} 条")

                # 只有在“至少有一个车位发生变化”时，才生成快照记录，
                # 这样车位变化列表页面只展示“有变化”的截图。
                if changes and changed_count > 0:
                    snapshot = ParkingChangeSnapshot(
                        task_id=task.id,
                        screenshot_id=shot.id,
                        channel_config_id=channel_cfg.id,
                        ip=task.ip,
                        channel_code=task.channel,
                        parking_name=channel_cfg.nvr_config.parking_name if channel_cfg.nvr_config else None,
                        change_count=changed_count,
                    )
                    db.add(snapshot)
                    print(f"  ✓ 已创建快照记录 (parking_change_snapshots), 变化数量: {changed_count}")
                else:
                    print(f"  ⚠️  无车位变化，不创建快照记录（但已保存所有车位的状态记录到 parking_changes 表）")

                shot.yolo_status = "done"
                processed += 1
                print(f"[ParkingChangeWorker] ✓ 截图 ID={shot.id} 处理完成\n")
            except Exception as e:  # noqa: BLE001
                print(f"[ParkingChangeWorker] ❌ 处理截图 ID={shot.id} 时发生错误: {e}")
                import traceback
                traceback.print_exc()
                shot.yolo_status = "failed"
                shot.yolo_last_error = str(e)
            finally:
                db.flush()

        db.commit()
        if processed > 0:
            print(f"[ParkingChangeWorker] 本次批次处理完成: 共处理 {processed} 张截图\n")
        return processed


def main_loop(interval_seconds: int = 5, batch_size: int = 10) -> None:
    """简单的轮询主循环，可由独立进程启动。"""
    print("[ParkingChangeWorker] 启动 Worker...")
    
    # 启动时预加载模型（会触发自动下载）
    print("[ParkingChangeWorker] 正在预加载 YOLO 模型（如果模型不存在会自动下载）...")
    if preload_model():
        print("[ParkingChangeWorker] ✓ YOLO 模型加载完成，Worker 已就绪")
    else:
        print("[ParkingChangeWorker] ✗ 模型加载失败，Worker 将继续运行，但无法处理截图，直到模型加载成功")
    
    print("[ParkingChangeWorker] 开始轮询待处理的截图...")
    while True:
        count = process_pending_screenshots(batch_size=batch_size)
        if count > 0:
            print(f"[ParkingChangeWorker] 本次处理了 {count} 张截图")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main_loop()

