"""全局常量定义"""

# API 路径前缀
API_PREFIX = "/api"

# 任务相关路径
TASKS_PREFIX = f"{API_PREFIX}/tasks"
TASK_CONFIGS_PREFIX = f"{TASKS_PREFIX}/configs"

# 图片相关路径
IMAGES_PREFIX = f"{API_PREFIX}/images"

# 自动调度相关路径
AUTO_SCHEDULE_PREFIX = f"{API_PREFIX}/auto-schedule"

# 默认分页大小
DEFAULT_PAGE_SIZE = 20
MIN_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50

# 任务状态
TASK_STATUS_PENDING = "pending"
TASK_STATUS_PLAYING = "playing"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_SCREENSHOT_TAKEN = "screenshot_taken"

# 状态映射（中文）
STATUS_MAP = {
    TASK_STATUS_PENDING: "待运行",
    TASK_STATUS_PLAYING: "运行中",
    TASK_STATUS_SCREENSHOT_TAKEN: "完成",
    TASK_STATUS_COMPLETED: "完成",
    TASK_STATUS_FAILED: "部分失败",
}

# 最大重试次数
MAX_RETRY_COUNT = 3

# 重试延迟（秒）
RETRY_DELAY_HOURS = 1

