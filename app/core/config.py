"""应用配置和常量"""
import os
import sys
import threading
from pathlib import Path
from typing import Dict, List
import subprocess

# 兼容直接运行时的相对导入问题
CURRENT_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 静态文件目录
STATIC_DIR = CURRENT_DIR / "static"

# 截图目录
SCREENSHOT_BASE = PROJECT_ROOT / "screenshots"
SCREENSHOT_BASE.mkdir(exist_ok=True, parents=True)

# HLS 目录
HLS_BASE = PROJECT_ROOT / "hls"
HLS_BASE.mkdir(exist_ok=True, parents=True)

# 全局状态
HLS_PROCS: Dict[str, subprocess.Popen] = {}

# 任务存储（从 schemas.tasks 导入 TaskSegment）
from schemas.tasks import TaskSegment
TASK_STORE: Dict[str, List[TaskSegment]] = {}

# 运行中的任务键
RUNNING_KEYS: set[str] = set()

# 并发控制（从根目录 config.py 读取，支持环境变量配置）
# 如果根目录 config.py 存在，则使用其配置；否则使用默认值
try:
    import sys
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from config import settings
    MAX_COMBO_CONCURRENCY = settings.MAX_COMBO_CONCURRENCY  # 全局并发：同时运行多少个通道组合（日期+IP+通道）
    MAX_WORKERS_PER_COMBO = settings.MAX_WORKERS_PER_COMBO  # 单组合并发：每个组合内部并行处理多少个任务段
except ImportError:
    # 如果导入失败，使用默认值
    MAX_COMBO_CONCURRENCY = int(os.getenv("MAX_COMBO_CONCURRENCY", "6"))
    MAX_WORKERS_PER_COMBO = int(os.getenv("MAX_WORKERS_PER_COMBO", "6"))

COMBO_SEM = threading.Semaphore(MAX_COMBO_CONCURRENCY)

# OCR功能已移除

# ==================== 车辆特征比对配置 ====================
# 特征比对阈值（用于判断是否为同一辆车）
# 降低阈值以减少误判：同一辆车在不同帧之间可能存在特征波动（光照、角度、检测框位置等）
VEHICLE_SIMILARITY_THRESHOLD_SAME_DAY = float(os.getenv("VEHICLE_SIMILARITY_THRESHOLD_SAME_DAY", "0.70"))  # 从0.85降低到0.70
VEHICLE_SIMILARITY_THRESHOLD_CROSS_DAY = float(os.getenv("VEHICLE_SIMILARITY_THRESHOLD_CROSS_DAY", "0.65"))  # 从0.75降低到0.65
# 短时间间隔的宽松阈值（用于时间间隔很短的情况，如连续截图）
VEHICLE_SIMILARITY_THRESHOLD_SHORT_INTERVAL = float(os.getenv("VEHICLE_SIMILARITY_THRESHOLD_SHORT_INTERVAL", "0.60"))  # 时间间隔<5分钟时的阈值
SHORT_INTERVAL_SECONDS = int(os.getenv("SHORT_INTERVAL_SECONDS", "300"))  # 5分钟（300秒）

# 时间段阈值调整系数（考虑24小时内的光照变化）
# 凌晨(0-6点)：极暗，阈值降低最多
TIME_PERIOD_EARLY_MORNING = (0, 6)  # 凌晨时段
TIME_PERIOD_DAYTIME = (6, 18)  # 白天时段
TIME_PERIOD_EVENING = (18, 20)  # 傍晚时段
TIME_PERIOD_NIGHT = (20, 24)  # 夜间时段

# 不同时间段的阈值调整系数（相对于基础阈值）
# 系数越小，阈值越低（更宽松）
TIME_PERIOD_THRESHOLD_FACTOR_EARLY_MORNING = float(os.getenv("TIME_PERIOD_THRESHOLD_FACTOR_EARLY_MORNING", "0.85"))  # 凌晨：降低15%
TIME_PERIOD_THRESHOLD_FACTOR_DAYTIME = float(os.getenv("TIME_PERIOD_THRESHOLD_FACTOR_DAYTIME", "1.0"))  # 白天：标准
TIME_PERIOD_THRESHOLD_FACTOR_EVENING = float(os.getenv("TIME_PERIOD_THRESHOLD_FACTOR_EVENING", "0.90"))  # 傍晚：降低10%
TIME_PERIOD_THRESHOLD_FACTOR_NIGHT = float(os.getenv("TIME_PERIOD_THRESHOLD_FACTOR_NIGHT", "0.80"))  # 夜间：降低20%

# 图像质量对阈值的影响系数
# 亮度影响：暗光环境下阈值降低
BRIGHTNESS_THRESHOLD_FACTOR_DARK = float(os.getenv("BRIGHTNESS_THRESHOLD_FACTOR_DARK", "0.90"))  # 暗光(<80)：降低10%
BRIGHTNESS_THRESHOLD_FACTOR_VERY_DARK = float(os.getenv("BRIGHTNESS_THRESHOLD_FACTOR_VERY_DARK", "0.85"))  # 极暗(<50)：降低15%
# 清晰度影响：模糊图像阈值降低
CLARITY_THRESHOLD_FACTOR_LOW = float(os.getenv("CLARITY_THRESHOLD_FACTOR_LOW", "0.90"))  # 低清晰度：降低10%

# 天气条件对阈值的影响系数
# 不同天气条件下特征提取的稳定性不同，需要调整阈值
WEATHER_THRESHOLD_FACTOR_RAINY = float(os.getenv("WEATHER_THRESHOLD_FACTOR_RAINY", "0.85"))  # 雨天：降低15%（反光、水珠影响）
WEATHER_THRESHOLD_FACTOR_FOGGY = float(os.getenv("WEATHER_THRESHOLD_FACTOR_FOGGY", "0.80"))  # 雾天：降低20%（能见度差、模糊）
WEATHER_THRESHOLD_FACTOR_CLOUDY = float(os.getenv("WEATHER_THRESHOLD_FACTOR_CLOUDY", "0.90"))  # 阴天：降低10%（光照均匀但较暗）
WEATHER_THRESHOLD_FACTOR_SUNNY = float(os.getenv("WEATHER_THRESHOLD_FACTOR_SUNNY", "1.0"))  # 晴天：标准（光照充足、清晰）

# 干扰判定参数
BRIGHTNESS_LOW_THRESHOLD = int(os.getenv("BRIGHTNESS_LOW_THRESHOLD", "40"))  # 暗光阈值
BRIGHTNESS_HIGH_THRESHOLD = int(os.getenv("BRIGHTNESS_HIGH_THRESHOLD", "220"))  # 过曝阈值
CLARITY_THRESHOLD = int(os.getenv("CLARITY_THRESHOLD", "100"))  # 清晰度阈值（Laplacian方差）

# 干扰模式下的鲁棒性参数
HIGH_ROBUSTNESS_MODE_ENABLED = os.getenv("HIGH_ROBUSTNESS_MODE_ENABLED", "true").lower() == "true"
MAX_CONSECUTIVE_MISS_DETECTIONS = int(os.getenv("MAX_CONSECUTIVE_MISS_DETECTIONS", "2"))  # 允许连续漏检帧数

# ==================== 状态稳定性机制配置 ====================
# 最低置信度阈值：YOLO置信度低于此值时，不参与"换车"判断
MIN_YOLO_CONFIDENCE_FOR_CHANGE_DETECTION = float(os.getenv("MIN_YOLO_CONFIDENCE_FOR_CHANGE_DETECTION", "0.50"))  # 50%

# 车位匹配的最低置信度阈值：用于判断车位是否有车
# 如果匹配到的车辆置信度低于此值，即使IoU够高，也判定为"无车"
MIN_SPACE_MATCH_CONFIDENCE_DAY = float(os.getenv("MIN_SPACE_MATCH_CONFIDENCE_DAY", "0.35"))  # 白天：35%
MIN_SPACE_MATCH_CONFIDENCE_NIGHT = float(os.getenv("MIN_SPACE_MATCH_CONFIDENCE_NIGHT", "0.25"))  # 夜间（暗光）：25%

# 状态延续保护机制：当相似度略低于阈值时，如果满足条件仍视为同一辆车
STATE_CONTINUATION_PROTECTION_ENABLED = os.getenv("STATE_CONTINUATION_PROTECTION_ENABLED", "true").lower() == "true"
STATE_CONTINUATION_TIME_THRESHOLD = float(os.getenv("STATE_CONTINUATION_TIME_THRESHOLD", "3.0"))  # 时间间隔≤3秒
STATE_CONTINUATION_POSITION_THRESHOLD = float(os.getenv("STATE_CONTINUATION_POSITION_THRESHOLD", "0.15"))  # 位置偏移<15%车位宽度
# 相似度容差：数值越大，越“保守”（更容易认为是同一辆车）；
# 为了让明显离开/换车更容易被识别，这里保持相对收紧的 10%
STATE_CONTINUATION_SIMILARITY_MARGIN = float(os.getenv("STATE_CONTINUATION_SIMILARITY_MARGIN", "0.10"))  # 相似度允许低于阈值10%

# 状态锁机制：连续多帧不变时锁定状态，必须连续多帧检测到无车才允许离开
# 之前为了极度防抖启用了状态锁，现在默认关闭，让真实的“驶离”更容易被检测出来
STATE_LOCK_ENABLED = os.getenv("STATE_LOCK_ENABLED", "false").lower() == "true"
STATE_LOCK_FRAMES = int(os.getenv("STATE_LOCK_FRAMES", "3"))  # 连续3帧不变时锁定状态
STATE_UNLOCK_FRAMES = int(os.getenv("STATE_UNLOCK_FRAMES", "1"))  # 调整为1帧无车即可解锁离开判断

