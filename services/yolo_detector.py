"""YOLOv8 车辆检测封装模块

说明：
- 使用 Ultralytics YOLOv8 进行车辆检测
- 模型文件不存在时会自动下载到项目目录下的 models/ 文件夹
- 使用全局单例模式，避免重复加载模型
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

# 在导入 ultralytics 之前设置环境变量，避免 git 检测问题
# 检查 git 是否可用
_git_available = False
try:
    subprocess.run(["git", "--version"], capture_output=True, check=True, timeout=2)
    _git_available = True
except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
    _git_available = False

# 如果 git 不可用，设置环境变量跳过 git 检测
if not _git_available:
    os.environ.setdefault("YOLO_SKIP_GIT_CHECK", "1")
    os.environ.setdefault("ULTRALYTICS_SKIP_GIT", "1")
    # 尝试设置 ultralytics 内部使用的环境变量
    os.environ.setdefault("YOLO_VERBOSE", "False")

# 获取项目目录（Smart_RTSP_Stream_Manager 目录）
_current_file = Path(__file__).resolve()
PROJECT_DIR = _current_file.parent.parent  # services -> Smart_RTSP_Stream_Manager
MODELS_DIR = PROJECT_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

# 全局模型实例（单例模式，避免重复加载）
_yolo_model: Optional[Any] = None
_model_lock = None

# 默认模型配置（可通过环境变量覆盖）
# 可选: yolov8n.pt, yolov8s.pt, yolov8m.pt, yolov8l.pt, yolov8x.pt
DEFAULT_MODEL_NAME = os.getenv("YOLO_MODEL_NAME", "yolov8n.pt")
# 自定义模型路径（优先级高于 DEFAULT_MODEL_NAME）
CUSTOM_MODEL_PATH = os.getenv("YOLO_CUSTOM_MODEL_PATH", "")
# 自定义下载 URL 列表，逗号分隔；会按顺序尝试
# 例如: export YOLO_MODEL_URLS="https://mirror1.xxx/yolov8n.pt,https://mirror2.xxx/yolov8n.pt"
CUSTOM_MODEL_URLS = [
    u.strip()
    for u in os.getenv("YOLO_MODEL_URLS", "").split(",")
    if u.strip()
]
# COCO 数据集中 "car" 的类别 ID 是 2
CAR_CLASS_ID = int(os.getenv("YOLO_CAR_CLASS_ID", "2"))
# 车辆类别ID列表（car=2, motorcycle=3, bus=5, truck=7）
VEHICLE_CLASS_IDS = {2, 3, 5, 7}
# 默认置信度阈值
DEFAULT_CONF_THRESHOLD = float(os.getenv("YOLO_CONF_THRESHOLD", "0.25"))
# 区域检测时的最小尺寸（如果区域太小，可能检测不准）
# 降低到 16 以提高小车位的检测率
MIN_REGION_SIZE = int(os.getenv("YOLO_MIN_REGION_SIZE", "16"))
# 区域检测时的padding（在车位坐标基础上扩大一点，提高检测率）
REGION_PADDING = int(os.getenv("YOLO_REGION_PADDING", "10"))


def _download_from_urls_with_retry(urls: List[str], target_path: Path, retries: int = 3) -> bool:
    """从多个 URL 尝试下载模型，带简单重试。

    任意一个 URL 在重试次数内成功即可返回 True。
    """
    if not urls:
        return False

    try:
        # 确保环境变量已设置（防止在其他地方导入 ultralytics 时出错）
        if not _git_available:
            os.environ.setdefault("YOLO_SKIP_GIT_CHECK", "1")
            os.environ.setdefault("ULTRALYTICS_SKIP_GIT", "1")
        from ultralytics.utils.downloads import download
    except Exception as e:  # noqa: BLE001
        print(f"[YOLODetector] 无法导入 ultralytics 下载工具: {e}")
        return False

    for url in urls:
        for attempt in range(1, retries + 1):
            try:
                print(f"[YOLODetector] 尝试从 {url} 下载模型 (第 {attempt}/{retries} 次)...")
                download(url, dir=str(target_path.parent), unzip=False)
                if target_path.exists():
                    print(f"[YOLODetector] 已从 {url} 下载模型到: {target_path}")
                    return True
            except Exception as e:  # noqa: BLE001
                print(f"[YOLODetector] 从 {url} 下载失败: {e}")
        print(f"[YOLODetector] 多次尝试从 {url} 下载均失败，尝试下一个镜像源...")

    return False


def _download_model_to_project(model_name: str) -> Path:
    """下载模型到项目目录下的 models/ 文件夹。
    
    参数:
        model_name: 模型名称，如 "yolov8n.pt"
    
    返回:
        模型文件的路径（项目目录下）
    """
    project_model_path = MODELS_DIR / model_name
    
    # 如果项目目录下已存在，直接返回
    if project_model_path.exists():
        print(f"[YOLODetector] 使用项目目录下的模型: {project_model_path}")
        return project_model_path
    
    print(f"[YOLODetector] 模型文件不存在，开始下载 {model_name} 到项目目录...")

    ultralytics_home = None

    # 方法1: 先让 YOLO 自动下载到默认位置，然后复制到项目目录
    try:
        # 确保环境变量已设置
        if not _git_available:
            os.environ.setdefault("YOLO_SKIP_GIT_CHECK", "1")
            os.environ.setdefault("ULTRALYTICS_SKIP_GIT", "1")
        from ultralytics import YOLO

        print("[YOLODetector] 尝试通过 Ultralytics 默认机制下载模型（可能需要几分钟）...")
        _ = YOLO(model_name)  # noqa: F841

        # 获取 Ultralytics 默认下载位置
        try:
            from ultralytics.utils import SETTINGS

            ultralytics_home = Path(
                SETTINGS.get("settings_dir", Path.home() / ".ultralytics")
            )
        except Exception:  # noqa: BLE001
            # 如果无法获取设置，使用默认路径
            ultralytics_home = Path.home() / ".ultralytics"

        default_model_path = ultralytics_home / "weights" / model_name

        # 如果默认位置存在，复制到项目目录
        if default_model_path.exists():
            print(
                f"[YOLODetector] 从默认位置复制模型到项目目录: "
                f"{default_model_path} -> {project_model_path}"
            )
            shutil.copy2(default_model_path, project_model_path)
            print(f"[YOLODetector] 模型已保存到项目目录: {project_model_path}")
            return project_model_path
    except ImportError:
        print(
            "[YOLODetector] 警告: 未安装 ultralytics，无法使用 YOLO(model_name) 自动下载。"
        )
    except Exception as e:  # noqa: BLE001
        print(f"[YOLODetector] 通过 YOLO(model_name) 下载模型失败: {e}")

    # 方法2: 尝试从已知缓存路径复制（即使上一步失败，也可能已经有老缓存）
    if ultralytics_home is None:
        ultralytics_home = Path.home() / ".ultralytics"

    possible_paths = [
        ultralytics_home / "weights" / model_name,
        Path.home() / ".cache" / "ultralytics" / model_name,
    ]

    for possible_path in possible_paths:
        if possible_path.exists():
            print(
                f"[YOLODetector] 在缓存位置找到模型，复制到项目目录: "
                f"{possible_path} -> {project_model_path}"
            )
            shutil.copy2(possible_path, project_model_path)
            print(f"[YOLODetector] 模型已保存到项目目录: {project_model_path}")
            return project_model_path

    # 方法3: 按优先级从多源 URL 下载（自定义镜像 > 官方 GitHub）
    urls: List[str] = []
    if CUSTOM_MODEL_URLS:
        urls.extend(CUSTOM_MODEL_URLS)

    # 官方 GitHub 作为最后兜底
    official_url = (
        f"https://github.com/ultralytics/assets/releases/download/v0.0.0/{model_name}"
    )
    urls.append(official_url)

    print(f"[YOLODetector] 尝试从以下 URL 下载模型（按顺序）:")
    for u in urls:
        print(f"  - {u}")

    ok = _download_from_urls_with_retry(urls, project_model_path)
    if ok and project_model_path.exists():
        return project_model_path

    # 所有方案都失败，给出清晰提示但不隐藏具体原因
    raise FileNotFoundError(
        f"无法自动下载模型文件 {model_name}。\n"
        f"请尝试手动下载并放置到: {project_model_path}\n"
        f"或设置环境变量 YOLO_CUSTOM_MODEL_PATH 指向已有模型文件。\n"
        f"如存在网络/镜像问题，可配置 YOLO_MODEL_URLS 使用自定义下载源。"
    )


def _get_model_path() -> str:
    """获取模型路径，优先使用自定义路径，否则使用默认模型名（会自动下载到项目目录）。"""
    if CUSTOM_MODEL_PATH and CUSTOM_MODEL_PATH.strip():
        custom_path = Path(CUSTOM_MODEL_PATH.strip())
        if custom_path.exists():
            return str(custom_path.resolve())
        # 自定义路径不存在，抛出错误
        raise FileNotFoundError(
            f"自定义模型文件不存在: {custom_path}\n"
            f"请检查环境变量 YOLO_CUSTOM_MODEL_PATH 或确保文件存在。"
        )
    
    # 使用默认模型名，检查项目目录下是否存在，不存在则下载
    project_model_path = _download_model_to_project(DEFAULT_MODEL_NAME)
    return str(project_model_path.resolve())


def _load_model():
    """加载 YOLOv8 模型（单例模式，全局只加载一次）。"""
    global _yolo_model, _model_lock
    
    if _yolo_model is not None:
        return _yolo_model
    
    try:
        # 环境变量已在模块级别设置，直接导入
        from ultralytics import YOLO
    except ImportError:
        raise ImportError(
            "未安装 ultralytics 库。请运行: pip install ultralytics\n"
            "如果使用 GPU，建议安装: pip install ultralytics torch torchvision"
        )
    
    # 使用线程锁确保多线程环境下只加载一次
    import threading
    if _model_lock is None:
        _model_lock = threading.Lock()
    
    with _model_lock:
        # 双重检查，避免并发时重复加载
        if _yolo_model is not None:
            return _yolo_model
        
        try:
            model_path = _get_model_path()
            model_path_obj = Path(model_path)
            
            # 验证模型文件是否存在
            if not model_path_obj.exists():
                raise FileNotFoundError(
                    f"模型文件不存在: {model_path}\n"
                    f"请检查文件路径是否正确，或运行 preload_model() 自动下载模型。"
                )
            
            # 验证文件是否可读
            if not model_path_obj.is_file():
                raise ValueError(f"模型路径不是文件: {model_path}")
            
            model_path_abs = str(model_path_obj.resolve())
            print(f"[YOLODetector] 正在加载模型: {model_path_abs}")
            print(f"[YOLODetector] 模型文件大小: {model_path_obj.stat().st_size / 1024 / 1024:.2f} MB")
            print(f"[YOLODetector] 模型文件可读: {model_path_obj.is_file() and model_path_obj.exists()}")
            
            # 验证文件权限
            try:
                with open(model_path_abs, 'rb') as f:
                    f.read(1)  # 尝试读取第一个字节
                print(f"[YOLODetector] 模型文件可访问")
            except Exception as e:
                raise PermissionError(f"无法读取模型文件: {e}")
            
            # 加载模型（使用绝对路径，确保 YOLO 可以正确访问）
            print(f"[YOLODetector] 调用 YOLO() 加载模型...")
            _yolo_model = YOLO(model_path_abs)
            
            print(f"[YOLODetector] 模型加载完成")
            return _yolo_model
        except FileNotFoundError as e:
            print(f"[YOLODetector] 模型文件未找到: {e}")
            raise
        except Exception as e:
            print(f"[YOLODetector] 加载模型时出错: {e}")
            import traceback
            traceback.print_exc()
            raise


def preload_model():
    """预加载 YOLO 模型（公开接口，供外部调用）。
    
    此函数可以在 Worker 启动时调用，确保模型已下载并加载。
    如果模型不存在，会自动下载到项目目录。
    """
    try:
        # 确保 models 目录存在
        MODELS_DIR.mkdir(exist_ok=True, parents=True)
        
        # 尝试加载模型（如果不存在会自动下载）
        print(f"[YOLODetector] 开始预加载模型...")
        _load_model()
        print(f"[YOLODetector] 模型预加载成功")
        return True
    except FileNotFoundError as e:
        print(f"[YOLODetector] 预加载模型失败（文件未找到）: {e}")
        print(f"[YOLODetector] 提示: 模型文件应位于: {MODELS_DIR / DEFAULT_MODEL_NAME}")
        print(f"[YOLODetector] 提示: 可以手动下载模型文件，或检查网络连接后重试")
        import traceback
        traceback.print_exc()
        return False
    except ImportError as e:
        print(f"[YOLODetector] 预加载模型失败（依赖缺失）: {e}")
        print(f"[YOLODetector] 提示: 请运行 'pip install ultralytics' 安装依赖")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"[YOLODetector] 预加载模型失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


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


def detect_cars_on_image(
    image_path: Path,
    conf_threshold: float = None,
    image_brightness: float = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """在单张图片上检测车辆，并返回YOLO的预处理信息（用于坐标映射）。

    参数:
        image_path: 图片的绝对路径。
        conf_threshold: 置信度阈值，默认使用 DEFAULT_CONF_THRESHOLD。
        image_brightness: 图像亮度，用于动态调整阈值。

    返回:
        (car_boxes, preprocess_info):
        - car_boxes: 列表，每个元素为一个 dict，例如：
          {
              "x1": int,
              "y1": int,
              "x2": int,
              "y2": int,
              "confidence": float,
              "class_id": int,
          }
          只返回类别为"车辆"的检测框（COCO 数据集中 car=2, truck=7, bus=5, motorcycle=3）。
        - preprocess_info: 预处理信息字典，包含：
          {
              "original_size": (width, height),
              "model_input_size": (width, height),
              "scale": float,
              "pad_x": int,
              "pad_y": int,
          }
    """
    if not image_path.exists():
        print(f"[YOLODetector] 警告: 图片文件不存在: {image_path}")
        return [], {}
    
    if conf_threshold is None:
        conf_threshold = DEFAULT_CONF_THRESHOLD
    
    try:
        # 读取原始图像
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"[YOLODetector] 警告: 无法读取图片: {image_path}")
            return [], {}
        
        original_height, original_width = img.shape[:2]
        
        # 动态调整置信度阈值
        # 注意：在暗光环境下，应该使用更低的阈值来接受更多检测结果
        if image_brightness and image_brightness < 120:
            dynamic_threshold = _calculate_dynamic_threshold(image_brightness, conf_threshold)
            # 在暗光环境下，后处理阈值应该与推理阈值保持一致或更低
            # 推理时使用 conf=0.1，后处理也应该接受 >= 0.1 的检测
            if dynamic_threshold > 0.1:
                # 如果动态阈值 > 0.1，在暗光环境下应该降低到 0.1
                conf_threshold = 0.1
                print(f"[YOLODetector] 暗光环境整图检测（亮度={image_brightness:.1f}），动态阈值={dynamic_threshold:.3f}，但后处理使用最低阈值: {conf_threshold:.3f}")
            else:
                conf_threshold = dynamic_threshold
                print(f"[YOLODetector] 暗光环境整图检测（亮度={image_brightness:.1f}），动态调整阈值: {conf_threshold:.3f}")
        
        # 夜间图像增强
        enhanced_path = image_path
        temp_enhanced_path = None
        if image_brightness and image_brightness < 120:
            img = _enhance_image_for_night(img, image_brightness)
            # 保存增强后的图像到临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                cv2.imwrite(str(tmp_path), img)
                enhanced_path = tmp_path
                temp_enhanced_path = tmp_path
                print(f"[YOLODetector] [DEBUG] 夜间增强图像已保存到临时文件: {enhanced_path}")
        
        model = _load_model()
        
        # 执行推理（使用更低的置信度以获取所有可能的检测结果）
        inference_conf = min(0.1, conf_threshold) if image_brightness and image_brightness < 120 else conf_threshold
        print(f"[YOLODetector] 整图检测推理参数: conf={inference_conf:.3f} (动态阈值={conf_threshold:.3f})")
        print(f"[YOLODetector] [DEBUG] 调用YOLO推理，图像路径: {enhanced_path}, 文件存在: {enhanced_path.exists()}")
        
        try:
            # 注意：YOLO的model()方法返回的是一个Results对象列表
            # 尝试使用predict()方法，这可能返回更标准的结果格式
            # 如果predict()不可用，则使用model()方法
            if hasattr(model, 'predict'):
                print(f"[YOLODetector] [DEBUG] 使用 model.predict() 方法")
                results = model.predict(str(enhanced_path), conf=inference_conf, verbose=False)
            else:
                print(f"[YOLODetector] [DEBUG] 使用 model() 方法")
                results = model(str(enhanced_path), conf=inference_conf, verbose=False)
            
            print(f"[YOLODetector] [DEBUG] YOLO推理完成，results类型: {type(results)}")
            
            # 检查results的实际结构
            if hasattr(results, '__len__'):
                print(f"[YOLODetector] [DEBUG] results长度: {len(results)}")
                if len(results) > 0:
                    print(f"[YOLODetector] [DEBUG] results[0]类型: {type(results[0])}")
                    if hasattr(results[0], 'boxes'):
                        print(f"[YOLODetector] [DEBUG] results[0].boxes类型: {type(results[0].boxes)}")
                        if results[0].boxes is not None:
                            print(f"[YOLODetector] [DEBUG] results[0].boxes长度: {len(results[0].boxes)}")
                        else:
                            print(f"[YOLODetector] [DEBUG] results[0].boxes 为 None")
                    else:
                        print(f"[YOLODetector] [DEBUG] results[0] 没有 boxes 属性")
                        print(f"[YOLODetector] [DEBUG] results[0] 的属性: {dir(results[0])}")
                else:
                    print(f"[YOLODetector] [DEBUG] results列表为空！")
                    # 尝试从predictor获取结果（自定义YOLO版本可能将结果存储在predictor.all_outputs中）
                    if hasattr(model, 'predictor') and hasattr(model.predictor, 'all_outputs'):
                        print(f"[YOLODetector] [DEBUG] 尝试从 predictor.all_outputs 获取结果")
                        if model.predictor.all_outputs:
                            print(f"[YOLODetector] [DEBUG] predictor.all_outputs长度: {len(model.predictor.all_outputs)}")
                            # all_outputs中存储的是原始检测张量，需要转换为Results对象或直接处理
                            # 暂时使用all_outputs，后续代码会处理
                            results = model.predictor.all_outputs
                            print(f"[YOLODetector] [DEBUG] 从predictor.all_outputs获取到结果，类型: {type(results[0]) if results else 'N/A'}")
            else:
                print(f"[YOLODetector] [DEBUG] results不是列表类型，实际类型: {type(results)}")
                # 尝试将results转换为列表
                try:
                    results = list(results) if results else []
                    print(f"[YOLODetector] [DEBUG] 转换后results长度: {len(results)}")
                except Exception as e:
                    print(f"[YOLODetector] [ERROR] 无法转换results: {e}")
                    results = []
        except Exception as e:
            print(f"[YOLODetector] [ERROR] YOLO推理失败: {e}")
            import traceback
            traceback.print_exc()
            # 清理临时文件
            if temp_enhanced_path and temp_enhanced_path.exists():
                try:
                    temp_enhanced_path.unlink()
                except Exception:
                    pass
            return [], {}
        
        # 清理临时增强图像（推理完成后才删除，但确保results已经被处理）
        if temp_enhanced_path and temp_enhanced_path.exists():
            try:
                temp_enhanced_path.unlink()
                print(f"[YOLODetector] [DEBUG] 已清理临时增强图像: {temp_enhanced_path}")
            except Exception as e:
                print(f"[YOLODetector] [WARN] 清理临时文件失败: {e}")
        
        # 解析结果，只保留车辆类别
        car_boxes: List[Dict[str, Any]] = []
        
        # 调试：统计所有检测结果
        all_detections_count = 0
        vehicle_detections_count = 0
        filtered_by_conf_count = 0
        
        # 调试：检查results的结构
        print(f"[YOLODetector] [DEBUG] results类型: {type(results)}, 长度: {len(results) if hasattr(results, '__len__') else 'N/A'}")
        
        for idx, result in enumerate(results):
            print(f"[YOLODetector] [DEBUG] result[{idx}]类型: {type(result)}")
            
            # 检查result是否是Results对象
            if hasattr(result, 'boxes'):
                # 标准Results对象
                print(f"[YOLODetector] [DEBUG] result[{idx}].boxes类型: {type(result.boxes)}")
                
                if result.boxes is None:
                    print(f"[YOLODetector] [DEBUG] result[{idx}].boxes 为 None，跳过")
                    continue
                
                boxes = result.boxes
                print(f"[YOLODetector] [DEBUG] boxes类型: {type(boxes)}, 长度: {len(boxes) if hasattr(boxes, '__len__') else 'N/A'}")
                
                # 检查boxes是否有数据
                if hasattr(boxes, '__len__') and len(boxes) == 0:
                    print(f"[YOLODetector] [DEBUG] boxes为空列表")
                    continue
                
                all_detections_count = len(boxes)
                print(f"[YOLODetector] [DEBUG] YOLO原始检测结果: 共 {all_detections_count} 个检测框")
                
                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i])
                    conf = float(boxes.conf[i])
                    
                    # 调试：打印所有检测结果（包括非车辆）
                    if i < 10:  # 只打印前10个，避免日志过多
                        print(f"[YOLODetector] [DEBUG] 检测框 {i+1}: 类别ID={cls_id}, 置信度={conf:.3f}, 是否车辆={cls_id in VEHICLE_CLASS_IDS}")
                    
                    # 检查车辆类别（car, motorcycle, bus, truck）
                    if cls_id in VEHICLE_CLASS_IDS:
                        vehicle_detections_count += 1
                        # 获取边界框坐标（xyxy 格式，相对于原始图像）
                        # YOLO返回的坐标已经是相对于原始图像的，因为YOLO内部处理了缩放
                        x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().tolist()
            else:
                # 可能是原始检测张量（torch.Tensor），格式为 [N, 6] 其中每行为 [x1, y1, x2, y2, conf, cls]
                import torch
                if isinstance(result, torch.Tensor):
                    print(f"[YOLODetector] [DEBUG] result[{idx}]是torch.Tensor，形状: {result.shape}")
                    det = result
                    all_detections_count = len(det)
                    print(f"[YOLODetector] [DEBUG] YOLO原始检测结果（张量）: 共 {all_detections_count} 个检测框")
                    
                    for i in range(len(det)):
                        # 张量格式: [x1, y1, x2, y2, conf, cls]
                        x1, y1, x2, y2, conf, cls_id = det[i].cpu().numpy().tolist()
                        cls_id = int(cls_id)
                        conf = float(conf)
                        
                        # 调试：打印所有检测结果（包括非车辆）
                        if i < 10:  # 只打印前10个，避免日志过多
                            print(f"[YOLODetector] [DEBUG] 检测框 {i+1}: 类别ID={cls_id}, 置信度={conf:.3f}, 是否车辆={cls_id in VEHICLE_CLASS_IDS}")
                        
                        # 检查车辆类别（car, motorcycle, bus, truck）
                        if cls_id in VEHICLE_CLASS_IDS:
                            vehicle_detections_count += 1
                            # 坐标已经是相对于原始图像的
                            x1 = max(0, min(int(x1), original_width))
                            y1 = max(0, min(int(y1), original_height))
                            x2 = max(0, min(int(x2), original_width))
                            y2 = max(0, min(int(y2), original_height))
                            
                            # 应用动态阈值和宽松检测策略
                            accepted = False
                            reject_reason = ""
                            
                            if conf >= conf_threshold:
                                accepted = True
                            elif image_brightness and image_brightness < 120 and conf >= 0.1:
                                accepted = True
                                print(f"[YOLODetector] 暗光环境宽松检测：置信度={conf:.3f}（阈值={conf_threshold:.3f}）")
                            else:
                                filtered_by_conf_count += 1
                                if image_brightness and image_brightness < 120:
                                    reject_reason = f"置信度{conf:.3f} < 0.1（暗光环境最低阈值）"
                                else:
                                    reject_reason = f"置信度{conf:.3f} < {conf_threshold:.3f}（动态阈值）"
                            
                            if accepted:
                                car_boxes.append({
                                    "x1": x1,
                                    "y1": y1,
                                    "x2": x2,
                                    "y2": y2,
                                    "confidence": conf,
                                    "class_id": cls_id,
                                })
                                print(f"[YOLODetector] ✓ 接受车辆检测: 类别ID={cls_id}, 坐标=({x1},{y1})-({x2},{y2}), 置信度={conf:.3f}")
                            else:
                                print(f"[YOLODetector] ✗ 过滤车辆检测: 类别ID={cls_id}, 置信度={conf:.3f}, 原因={reject_reason}")
                else:
                    print(f"[YOLODetector] [DEBUG] result[{idx}]既不是Results对象也不是torch.Tensor，无法处理")
                    continue
            
            # 处理Results对象的情况（标准YOLO返回格式）
            if hasattr(result, 'boxes') and result.boxes is not None:
                boxes = result.boxes
                print(f"[YOLODetector] [DEBUG] boxes类型: {type(boxes)}, 长度: {len(boxes) if hasattr(boxes, '__len__') else 'N/A'}")
                
                # 检查boxes是否有数据
                if hasattr(boxes, '__len__') and len(boxes) == 0:
                    print(f"[YOLODetector] [DEBUG] boxes为空列表")
                    continue
                
                all_detections_count = len(boxes)
                print(f"[YOLODetector] [DEBUG] YOLO原始检测结果: 共 {all_detections_count} 个检测框")
                
                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i])
                    conf = float(boxes.conf[i])
                    
                    # 调试：打印所有检测结果（包括非车辆）
                    if i < 10:  # 只打印前10个，避免日志过多
                        print(f"[YOLODetector] [DEBUG] 检测框 {i+1}: 类别ID={cls_id}, 置信度={conf:.3f}, 是否车辆={cls_id in VEHICLE_CLASS_IDS}")
                    
                    # 检查车辆类别（car, motorcycle, bus, truck）
                    if cls_id in VEHICLE_CLASS_IDS:
                        vehicle_detections_count += 1
                        # 获取边界框坐标（xyxy 格式，相对于原始图像）
                        # YOLO返回的坐标已经是相对于原始图像的，因为YOLO内部处理了缩放
                        x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().tolist()
                        
                        # 确保坐标在图像范围内
                        x1 = max(0, min(int(x1), original_width))
                        y1 = max(0, min(int(y1), original_height))
                        x2 = max(0, min(int(x2), original_width))
                        y2 = max(0, min(int(y2), original_height))
                        
                        # 应用动态阈值和宽松检测策略
                        accepted = False
                        reject_reason = ""
                        
                        if conf >= conf_threshold:
                            accepted = True
                        elif image_brightness and image_brightness < 120 and conf >= 0.1:
                            accepted = True
                            print(f"[YOLODetector] 暗光环境宽松检测：置信度={conf:.3f}（阈值={conf_threshold:.3f}）")
                        else:
                            filtered_by_conf_count += 1
                            if image_brightness and image_brightness < 120:
                                reject_reason = f"置信度{conf:.3f} < 0.1（暗光环境最低阈值）"
                            else:
                                reject_reason = f"置信度{conf:.3f} < {conf_threshold:.3f}（动态阈值）"
                        
                        if accepted:
                            car_boxes.append({
                                "x1": x1,
                                "y1": y1,
                                "x2": x2,
                                "y2": y2,
                                "confidence": conf,
                                "class_id": cls_id,
                            })
                            print(f"[YOLODetector] ✓ 接受车辆检测: 类别ID={cls_id}, 坐标=({x1},{y1})-({x2},{y2}), 置信度={conf:.3f}")
                        else:
                            print(f"[YOLODetector] ✗ 过滤车辆检测: 类别ID={cls_id}, 置信度={conf:.3f}, 原因={reject_reason}")
        
        # 调试总结
        print(f"[YOLODetector] [DEBUG] 检测统计: 总检测框={all_detections_count}, 车辆类别={vehicle_detections_count}, 通过过滤={len(car_boxes)}, 被过滤={filtered_by_conf_count}")
        
        # 获取预处理信息（YOLO内部处理的缩放信息）
        # 注意：YOLOv8会自动处理缩放，返回的坐标已经是相对于原始图像的
        # 但我们仍然需要记录一些信息用于调试
        preprocess_info = {
            "original_size": (original_width, original_height),
            "model_input_size": (640, 640),  # YOLOv8默认输入尺寸
            "scale": 1.0,  # YOLO内部已处理，坐标已映射回原始图像
            "pad_x": 0,
            "pad_y": 0,
        }
        
        if car_boxes:
            print(f"[YOLODetector] ✓ 在 {image_path.name} 中检测到 {len(car_boxes)} 辆车")
        else:
            if vehicle_detections_count > 0:
                print(f"[YOLODetector] ⚠️  警告: YOLO检测到 {vehicle_detections_count} 个车辆对象，但全部被过滤（置信度阈值可能过高）")
            elif all_detections_count > 0:
                print(f"[YOLODetector] ⚠️  警告: YOLO检测到 {all_detections_count} 个对象，但没有车辆类别（类别ID可能不匹配）")
            else:
                print(f"[YOLODetector] 在 {image_path.name} 中未检测到任何对象")
        
        return car_boxes, preprocess_info
        
    except Exception as e:
        print(f"[YOLODetector] 检测失败: {e}")
        import traceback
        traceback.print_exc()
        return [], {}


def _enhance_image_for_night(roi: np.ndarray, brightness: float = None) -> np.ndarray:
    """对夜间图像进行增强处理，提高YOLO检测率。
    
    参数:
        roi: 输入图像（BGR格式）
        brightness: 图像平均亮度（0-255），如果为None则自动计算
    
    返回:
        增强后的图像（BGR格式）
    """
    try:
        if brightness is None:
            # 计算平均亮度
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            brightness = float(np.mean(gray))
        
        # 如果亮度较高（>120），不需要增强
        if brightness > 120:
            return roi
        
        # 方法1: CLAHE（对比度受限的自适应直方图均衡化）- 对夜间图像效果最好
        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # 对L通道应用CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l)
        
        # 合并通道
        lab_enhanced = cv2.merge([l_enhanced, a, b])
        enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
        
        # 方法2: Gamma校正（如果亮度很低，额外应用Gamma校正）
        if brightness < 60:
            # 计算Gamma值（亮度越低，Gamma值越大，增强越明显）
            gamma = 1.5 + (60 - brightness) / 60 * 0.5  # 1.5 到 2.0 之间
            inv_gamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
            enhanced = cv2.LUT(enhanced, table)
        
        return enhanced
    except Exception as e:
        print(f"[YOLODetector] 图像增强失败: {e}")
        return roi  # 失败时返回原图


def _calculate_dynamic_threshold(brightness: float, base_threshold: float = None) -> float:
    """根据图像亮度动态计算置信度阈值。
    
    参数:
        brightness: 图像平均亮度（0-255）
        base_threshold: 基础阈值，默认使用 DEFAULT_CONF_THRESHOLD
    
    返回:
        调整后的置信度阈值
    """
    if base_threshold is None:
        base_threshold = DEFAULT_CONF_THRESHOLD
    
    # 亮度阈值分段调整
    if brightness < 50:
        # 极暗环境（<50）：大幅降低阈值，提高检测率
        # 从 base_threshold 降低到 base_threshold * 0.4（最低0.1）
        dynamic_threshold = max(0.1, base_threshold * 0.4)
    elif brightness < 80:
        # 暗环境（50-80）：适度降低阈值
        # 线性插值：50->0.4, 80->0.7
        ratio = 0.4 + (brightness - 50) / 30 * 0.3
        dynamic_threshold = max(0.1, base_threshold * ratio)
    elif brightness < 120:
        # 中等亮度（80-120）：轻微降低阈值
        # 线性插值：80->0.7, 120->0.9
        ratio = 0.7 + (brightness - 80) / 40 * 0.2
        dynamic_threshold = base_threshold * ratio
    else:
        # 正常亮度（>=120）：使用标准阈值
        dynamic_threshold = base_threshold
    
    return dynamic_threshold


def extract_vehicle_features(vehicle_roi: np.ndarray) -> Dict[str, Any]:
    """从车辆ROI图像中提取视觉特征。
    
    参数:
        vehicle_roi: 车辆区域的图像（BGR格式，numpy数组）
    
    返回:
        特征字典，包含：
        - color_hist_h: HSV H通道直方图（32 bins）
        - color_hist_s: HSV S通道直方图（32 bins）
        - aspect_ratio: 宽高比
        - has_rear_wiper: 是否有后雨刮（布尔值）
    """
    try:
        # 转换为HSV颜色空间
        hsv = cv2.cvtColor(vehicle_roi, cv2.COLOR_BGR2HSV)
        
        # 提取H和S通道直方图（32 bins）
        hist_h = cv2.calcHist([hsv], [0], None, [32], [0, 180])
        hist_s = cv2.calcHist([hsv], [1], None, [32], [0, 256])
        
        # 归一化直方图
        hist_h = hist_h.flatten() / (hist_h.sum() + 1e-6)
        hist_s = hist_s.flatten() / (hist_s.sum() + 1e-6)
        
        # 计算宽高比
        h, w = vehicle_roi.shape[:2]
        aspect_ratio = float(w) / (h + 1e-6)
        
        # 检测后雨刮（简单边缘检测方法）
        # 在后车窗区域（图像下半部分）检测水平边缘
        gray = cv2.cvtColor(vehicle_roi, cv2.COLOR_BGR2GRAY)
        lower_half = gray[h // 2:, :]
        
        # 使用Canny边缘检测
        edges = cv2.Canny(lower_half, 50, 150)
        
        # 检测水平线（雨刮通常是水平线）
        horizontal_lines = 0
        for y in range(edges.shape[0]):
            line_pixels = np.sum(edges[y, :] > 0)
            if line_pixels > edges.shape[1] * 0.3:  # 如果一行中有30%以上是边缘
                horizontal_lines += 1
        
        has_rear_wiper = horizontal_lines >= 2  # 至少2条水平线
        
        return {
            "color_hist_h": hist_h.tolist(),
            "color_hist_s": hist_s.tolist(),
            "aspect_ratio": aspect_ratio,
            "has_rear_wiper": bool(has_rear_wiper),
        }
    except Exception as e:
        print(f"[YOLODetector] 特征提取失败: {e}")
        # 返回默认特征
        return {
            "color_hist_h": [0.0] * 32,
            "color_hist_s": [0.0] * 32,
            "aspect_ratio": 1.8,
            "has_rear_wiper": False,
        }


def detect_cars_in_region(
    image_path: Path,
    region: Tuple[int, int, int, int],
    conf_threshold: float = None,
    use_padding: bool = True,
    extract_features: bool = True,
    image_brightness: float = None,  # 图像亮度，用于动态调整阈值
    enable_night_enhancement: bool = True,  # 是否启用夜间图像增强
) -> Tuple[bool, float, Optional[Dict[str, Any]]]:
    """在图片的指定区域内检测是否有车辆，并可选择提取车辆特征。

    参数:
        image_path: 图片的绝对路径。
        region: 区域坐标 (x, y, width, height)，其中 x, y 是左上角坐标。
        conf_threshold: 置信度阈值，默认使用 DEFAULT_CONF_THRESHOLD。如果提供了 image_brightness，会动态调整。
        use_padding: 是否在区域基础上添加padding，提高检测率。
        extract_features: 是否提取车辆特征（用于车辆重识别）。
        image_brightness: 图像平均亮度（0-255），用于动态调整置信度阈值。如果为None，会从ROI自动计算。
        enable_night_enhancement: 是否启用夜间图像增强（CLAHE + Gamma校正）。

    返回:
        (bool, float, Optional[Dict]): 
        - bool: 如果在该区域内检测到车辆（置信度 >= conf_threshold），返回 True；否则返回 False。
        - float: 检测到的最高置信度（如果有车），否则返回 0.0。
        - Optional[Dict]: 车辆特征字典（如果 extract_features=True 且检测到车辆），否则为 None。
    """
    if not image_path.exists():
        print(f"[YOLODetector] 警告: 图片文件不存在: {image_path}")
        return False, 0.0, None
    
    if conf_threshold is None:
        conf_threshold = DEFAULT_CONF_THRESHOLD
    
    try:
        # 读取图片
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"[YOLODetector] 警告: 无法读取图片: {image_path}")
            return False, 0.0, None
        
        img_height, img_width = img.shape[:2]
        
        # 解析区域坐标 (x, y, width, height)
        x, y, w, h = region
        
        # 调试：输出原始区域坐标
        print(f"[YOLODetector] 检测区域: 原始坐标=({x}, {y}, {w}, {h}), 图像尺寸=({img_width}, {img_height})")
        
        # 如果使用padding，在区域基础上扩大一点
        if use_padding and REGION_PADDING > 0:
            x = max(0, x - REGION_PADDING)
            y = max(0, y - REGION_PADDING)
            w = min(img_width - x, w + 2 * REGION_PADDING)
            h = min(img_height - y, h + 2 * REGION_PADDING)
            print(f"[YOLODetector] 应用padding后: ({x}, {y}, {w}, {h})")
        
        x1, y1 = x, y
        x2, y2 = x + w, y + h
        
        # 确保坐标在图片范围内
        x1 = max(0, min(x1, img_width))
        y1 = max(0, min(y1, img_height))
        x2 = max(0, min(x2, img_width))
        y2 = max(0, min(y2, img_height))
        
        # 如果区域无效或太小，返回 False
        if x2 <= x1 or y2 <= y1:
            print(f"[YOLODetector] 警告: 区域无效 (x1={x1}, y1={y1}, x2={x2}, y2={y2})")
            return False, 0.0, None
        
        region_width = x2 - x1
        region_height = y2 - y1
        if region_width < MIN_REGION_SIZE or region_height < MIN_REGION_SIZE:
            # 区域太小，可能检测不准，返回 False
            print(f"[YOLODetector] 警告: 区域太小 ({region_width}x{region_height} < {MIN_REGION_SIZE}x{MIN_REGION_SIZE})")
            return False, 0.0, None
        
        # 裁剪区域
        roi = img[y1:y2, x1:x2]
        if roi.size == 0:
            print(f"[YOLODetector] 警告: ROI为空")
            return False, 0.0, None
        
        # 如果裁剪后的区域太小，可能检测不准
        roi_height, roi_width = roi.shape[:2]
        if roi_width < MIN_REGION_SIZE or roi_height < MIN_REGION_SIZE:
            print(f"[YOLODetector] 警告: ROI尺寸太小 ({roi_width}x{roi_height} < {MIN_REGION_SIZE}x{MIN_REGION_SIZE})")
            return False, 0.0, None
        
        print(f"[YOLODetector] ROI尺寸: {roi_width}x{roi_height}")
        
        # 加载模型
        model = _load_model()
        
        # 执行推理：由于 ultralytics 的某些版本不支持直接传入 numpy 数组，
        # 我们需要将 ROI 保存为临时文件，然后让 YOLO 读取
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            # 保存 ROI 为临时图片文件
            cv2.imwrite(str(tmp_path), roi)
            
            try:
                # 使用临时文件路径进行推理
                # 注意：在暗光环境下，使用更低的初始置信度（0.1）来获取所有可能的检测结果
                # 然后在后处理中根据动态阈值进行过滤
                inference_conf = min(0.1, conf_threshold) if image_brightness and image_brightness < 120 else conf_threshold
                print(f"[YOLODetector] YOLO推理参数: conf={inference_conf:.3f} (动态阈值={conf_threshold:.3f})")
                results = model(str(tmp_path), conf=inference_conf, verbose=False)
            finally:
                # 清理临时文件
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
        
        # 检查是否有车辆检测结果（支持多种车辆类型）
        max_confidence = 0.0
        has_vehicle = False
        vehicle_classes = []  # 记录检测到的车辆类型
        best_box = None  # 记录置信度最高的检测框
        all_detections = []  # 记录所有检测结果（用于调试）
        
        for result in results:
            if result.boxes is None:
                continue
            
            boxes = result.boxes
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i])
                conf = float(boxes.conf[i])
                
                # 记录所有检测结果（用于调试）
                all_detections.append({
                    "class_id": cls_id,
                    "confidence": conf,
                    "is_vehicle": cls_id in VEHICLE_CLASS_IDS,
                })
                
                # 检查车辆类别（car, motorcycle, bus, truck）
                # 注意：在暗光环境下，即使置信度略低于阈值，也考虑接受（但降低权重）
                if cls_id in VEHICLE_CLASS_IDS:
                    # 标准阈值检查
                    if conf >= conf_threshold:
                        has_vehicle = True
                        if conf > max_confidence:
                            max_confidence = conf
                            # 记录置信度最高的检测框（相对于ROI的坐标）
                            x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
                            best_box = (int(x1), int(y1), int(x2), int(y2))
                        vehicle_classes.append(cls_id)
                    # 暗光环境下的宽松检查（置信度在阈值的70%-100%之间，且亮度<80）
                    elif image_brightness < 80 and conf >= conf_threshold * 0.7:
                        # 在暗光环境下，即使置信度略低，也接受检测结果
                        has_vehicle = True
                        if conf > max_confidence:
                            max_confidence = conf
                            x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
                            best_box = (int(x1), int(y1), int(x2), int(y2))
                        vehicle_classes.append(cls_id)
                        print(f"[YOLODetector] 暗光环境宽松检测：置信度={conf:.3f}（阈值={conf_threshold:.3f}）")
                    # 更宽松的检查：在暗光环境下（亮度<120），接受置信度>=0.1的检测结果
                    elif image_brightness < 120 and conf >= 0.1:
                        has_vehicle = True
                        if conf > max_confidence:
                            max_confidence = conf
                            x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
                            best_box = (int(x1), int(y1), int(x2), int(y2))
                        vehicle_classes.append(cls_id)
                        print(f"[YOLODetector] 暗光环境超宽松检测：置信度={conf:.3f}（阈值={conf_threshold:.3f}，亮度={image_brightness:.1f}）")
        
        # 输出调试信息
        if all_detections:
            vehicle_detections = [d for d in all_detections if d["is_vehicle"]]
            if vehicle_detections:
                print(f"[YOLODetector] ROI区域检测到 {len(vehicle_detections)} 个车辆对象:")
                for det in vehicle_detections:
                    status = "✓通过" if det['confidence'] >= conf_threshold else "✗低于阈值"
                    print(f"  类别ID={det['class_id']}, 置信度={det['confidence']:.3f}, 阈值={conf_threshold:.3f}, {status}")
            else:
                print(f"[YOLODetector] ROI区域检测到 {len(all_detections)} 个对象，但都不是车辆类型:")
                for det in all_detections[:5]:  # 只显示前5个
                    print(f"  类别ID={det['class_id']}, 置信度={det['confidence']:.3f}")
        else:
            print(f"[YOLODetector] ROI区域未检测到任何对象")
        
        if has_vehicle:
            print(f"[YOLODetector] ✓ 最终判定：有车，最高置信度={max_confidence:.3f}")
        else:
            print(f"[YOLODetector] ✗ 最终判定：无车")
        
        # 如果检测到车辆且需要提取特征，提取最高置信度车辆的特征
        vehicle_features = None
        if has_vehicle and extract_features and best_box is not None:
            try:
                # 从ROI中裁剪出车辆区域（best_box是相对于ROI的坐标）
                bx1, by1, bx2, by2 = best_box
                # 确保坐标在ROI范围内
                bx1 = max(0, min(bx1, roi.shape[1]))
                by1 = max(0, min(by1, roi.shape[0]))
                bx2 = max(0, min(bx2, roi.shape[1]))
                by2 = max(0, min(by2, roi.shape[0]))
                
                if bx2 > bx1 and by2 > by1:
                    vehicle_roi = roi[by1:by2, bx1:bx2]
                    if vehicle_roi.size > 0:
                        vehicle_features = extract_vehicle_features(vehicle_roi)
            except Exception as e:
                print(f"[YOLODetector] 提取车辆特征时出错: {e}")
                vehicle_features = None
        
        # 返回检测结果、最高置信度和特征
        return has_vehicle, max_confidence, vehicle_features
        
    except Exception as e:
        print(f"[YOLODetector] 区域检测失败: {e}")
        import traceback
        traceback.print_exc()
        return False, 0.0, None

