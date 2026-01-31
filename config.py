import os
import sys
from pathlib import Path
from pydantic import BaseModel

# 添加项目根目录到路径，以便导入工具模块
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _auto_detect_concurrency() -> tuple[int, int]:
    """
    自动检测服务器性能并计算合适的并发数
    
    Returns:
        Tuple[int, int]: (MAX_COMBO_CONCURRENCY, MAX_WORKERS_PER_COMBO)
    """
    try:
        from utils.system_utils import calculate_optimal_concurrency
        
        # 获取数据库连接池配置（这里先使用默认值，实际会从 db.py 读取）
        # 由于可能存在循环导入，先使用默认值
        pool_size = 20
        max_overflow = 40
        
        max_combo, max_workers = calculate_optimal_concurrency(
            db_pool_size=pool_size,
            db_max_overflow=max_overflow,
        )
        
        print(f"[INFO] 自动检测并发配置: MAX_COMBO_CONCURRENCY={max_combo}, MAX_WORKERS_PER_COMBO={max_workers}")
        return max_combo, max_workers
    except Exception as e:
        print(f"[WARN] 自动检测并发配置失败: {e}，使用默认值 4, 4")
        import traceback
        traceback.print_exc()
        return 4, 4


# 在模块级别自动检测并发配置（如果环境变量未设置）
_env_max_combo = os.getenv("MAX_COMBO_CONCURRENCY")
_env_max_workers = os.getenv("MAX_WORKERS_PER_COMBO")

if _env_max_combo is None or _env_max_workers is None:
    # 自动检测
    print("[INFO] ========== 开始自动检测服务器并发配置 ==========")
    _AUTO_MAX_COMBO, _AUTO_MAX_WORKERS = _auto_detect_concurrency()
    _DEFAULT_MAX_COMBO = str(_AUTO_MAX_COMBO)
    _DEFAULT_MAX_WORKERS = str(_AUTO_MAX_WORKERS)
    print(f"[INFO] 自动检测完成: MAX_COMBO_CONCURRENCY={_AUTO_MAX_COMBO}, MAX_WORKERS_PER_COMBO={_AUTO_MAX_WORKERS}")
    print("[INFO] ================================================")
else:
    # 使用环境变量
    print(f"[INFO] 使用环境变量配置: MAX_COMBO_CONCURRENCY={_env_max_combo}, MAX_WORKERS_PER_COMBO={_env_max_workers}")
    _DEFAULT_MAX_COMBO = _env_max_combo
    _DEFAULT_MAX_WORKERS = _env_max_workers


class Settings(BaseModel):
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "test123456")
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_DB: str = os.getenv("MYSQL_DB", "smart_rtsp")
    USE_SQLITE_FALLBACK: bool = os.getenv("USE_SQLITE_FALLBACK", "true").lower() == "true"
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "sqlite:///./smart_rtsp.sqlite3")
    
    # 并发控制配置
    # 如果环境变量设置了值，则使用环境变量；否则自动检测服务器性能
    MAX_COMBO_CONCURRENCY: int = int(os.getenv("MAX_COMBO_CONCURRENCY", _DEFAULT_MAX_COMBO))  # 全局并发：同时运行多少个通道组合（日期+IP+通道）
    MAX_WORKERS_PER_COMBO: int = int(os.getenv("MAX_WORKERS_PER_COMBO", _DEFAULT_MAX_WORKERS))  # 单组合并发：每个组合内部并行处理多少个任务段

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:"
            f"{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:"
            f"{self.MYSQL_PORT}/{self.MYSQL_DB}"
            f"?charset=utf8mb4"
        )

    def get_engine_url(self) -> str:
        """
        Try MySQL; if DB not exists and allowed, create it; if fail and fallback enabled, use SQLite.
        """
        try:
            import pymysql  # noqa: F401
            conn = pymysql.connect(
                host=self.MYSQL_HOST,
                user=self.MYSQL_USER,
                password=self.MYSQL_PASSWORD,
                port=self.MYSQL_PORT,
                database=None,
                charset="utf8mb4",
                autocommit=True,
            )
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS {self.MYSQL_DB} DEFAULT CHARACTER SET utf8mb4;")
            conn.close()
            return self.mysql_url
        except Exception as e:
            if self.USE_SQLITE_FALLBACK:
                print(f"[warn] MySQL unavailable or DB create failed ({e}); fallback to SQLite: {self.SQLITE_PATH}")
                return self.SQLITE_PATH
            raise


settings = Settings()

# 在创建 settings 后再次打印最终配置（确保值正确）
print(f"[INFO] ========== 最终并发配置 ==========")
print(f"[INFO] settings.MAX_COMBO_CONCURRENCY = {settings.MAX_COMBO_CONCURRENCY}")
print(f"[INFO] settings.MAX_WORKERS_PER_COMBO = {settings.MAX_WORKERS_PER_COMBO}")
print(f"[INFO] 总并发任务数 = {settings.MAX_COMBO_CONCURRENCY * settings.MAX_WORKERS_PER_COMBO}")
print(f"[INFO] ==================================")

