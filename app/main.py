import os
import sys
import subprocess
import uuid
import time
import re
import threading
import logging
import stat
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Annotated
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from typing import Annotated
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm.exc import StaleDataError

# 兼容直接运行 main.py 时的相对导入问题
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ==================== 全局日志配置 ====================
# 目标：把整个系统（包括 print、logging、uvicorn）输出统一写入一个日志文件，
# 同时仍然在控制台输出，方便你后续做分析。
LOG_DIR = PROJECT_ROOT / "logs"
try:
    LOG_DIR.mkdir(exist_ok=True, parents=True)
    # 尝试设置目录权限（如果可能）
    try:
        os.chmod(LOG_DIR, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    except (OSError, PermissionError):
        pass  # 忽略权限设置失败
except (OSError, PermissionError) as e:
    # 如果无法创建目录，记录警告但继续执行
    import warnings
    warnings.warn(f"无法创建日志目录 {LOG_DIR}: {e}，将仅使用控制台输出")
    LOG_DIR = None

LOG_FILE = LOG_DIR / "smart_rtsp_stream_manager.log" if LOG_DIR else None

class _StreamToLogger:
    """把 print 等写到 stdout/stderr 的内容重定向到 logging。

    这样所有的 print()、traceback.print_exc() 等也都会进同一个日志文件。
    """

    def __init__(self, level: int, stream):
        self.level = level
        self.logger = logging.getLogger(
            "stdout" if level == logging.INFO else "stderr"
        )
        # 保存原始底层流，用于 isatty 和实际 flush
        self._stream = stream

    def write(self, message: str):
        message = message.rstrip()
        if not message:
            return
        self.logger.log(self.level, message)

    def flush(self):
        try:
            if hasattr(self._stream, "flush"):
                self._stream.flush()
        except Exception:
            pass

    def isatty(self) -> bool:  # 供 logging / uvicorn 判断终端能力
        try:
            return self._stream.isatty()
        except Exception:
            return False


 # 配置 root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 清理已有的 handler，避免重复写多份
for _h in list(root_logger.handlers):
    root_logger.removeHandler(_h)

log_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

# 文件滚动日志：10MB 一个文件，保留 5 个历史文件
# 如果无法创建日志文件，仅使用控制台输出，不影响应用启动
if LOG_FILE:
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(log_formatter)
        root_logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # 如果无法创建日志文件，记录警告但继续执行
        import warnings
        warnings.warn(f"无法创建日志文件 {LOG_FILE}: {e}，将仅使用控制台输出")
        # 尝试使用标准输出作为后备
        print(f"[WARNING] 无法创建日志文件 {LOG_FILE}: {e}，将仅使用控制台输出")
else:
    # LOG_DIR 为 None 的情况已在上面处理
    pass

# 控制台输出仍然写到原始 stdout，避免干扰 uvicorn 对 isatty 的判断
_REAL_STDOUT = sys.stdout
_REAL_STDERR = sys.stderr
console_handler = logging.StreamHandler(_REAL_STDOUT)
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# 重定向标准输出/错误到日志系统（在配置好 handler 之后执行）
sys.stdout = _StreamToLogger(logging.INFO, _REAL_STDOUT)   # 所有 print() → INFO
sys.stderr = _StreamToLogger(logging.ERROR, _REAL_STDERR)  # 异常栈等 → ERROR

from db import Base, engine, SessionLocal  # noqa: E402
from config import settings  # noqa: E402
from models import Task, Screenshot, MinuteScreenshot, AutoScheduleRule, TaskBatch, NvrConfig, ChannelConfig, ParkingSpace, ParkingChange, ParkingChangeSnapshot  # noqa: E402
from schemas.tasks import (  # noqa: E402
    RunTaskRequest,
    RunAllRequest,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskSegment,
    RerunConfigRequest,
    AutoScheduleRuleCreate,
    AutoScheduleRuleUpdate,
)
from schemas.nvr_config import (  # noqa: E402
    NvrConfigCreate,
    NvrConfigUpdate,
    NvrConfigResponse,
    ChannelConfigCreate,
    ChannelConfigUpdate,
    ChannelConfigResponse,
    ParkingSpaceInfo,
    ChannelView,
)
from services.segment_generator import build_segment_tasks  # noqa: E402
from services.screenshot import capture_frame  # noqa: E402
# from services.dedup import deduplicate_directory  # 暂停相似度去重

# OCR功能已移除
from app.services.image_service import ImageService  # noqa: E402
from services.stream_check import check_rtsp  # noqa: E402
from services.stream_hls import start_hls, probe_rtsp  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动和关闭时执行的操作"""
    # 启动时执行
    # 0. 确保数据库表已创建（必须在后台任务启动之前）
    try:
        print("[INFO] 正在创建数据库表（如果不存在）...")
        Base.metadata.create_all(bind=engine)
        print("[INFO] ✓ 数据库表检查完成")
    except Exception as e:
        print(f"[ERROR] 数据库表创建失败: {e}")
        raise
    
    # 0.1. 检查并添加缺失的数据库字段（表结构迁移）
    try:
        from app.core.db_migration import check_and_add_missing_columns
        print("[INFO] 正在检查数据库表结构...")
        added_columns = check_and_add_missing_columns()
        if added_columns:
            print(f"[INFO] ✓ 已自动添加 {len(added_columns)} 个缺失的字段: {', '.join(added_columns)}")
        else:
            print("[INFO] ✓ 数据库表结构检查完成，所有字段已存在")
    except Exception as e:
        print(f"[WARN] 数据库表结构检查时出错（不影响启动）: {e}")
        import traceback
        traceback.print_exc()
    
    # 1. 预加载 YOLO 模型（如果不存在会自动下载）
    try:
        from services.yolo_detector import preload_model
        print("[INFO] 正在检查 YOLO 模型（如果不存在会自动下载）...")
        if preload_model():
            print("[INFO] ✓ YOLO 模型已就绪")
        else:
            print("[WARN] YOLO 模型加载失败，车位变化检测功能将不可用")
    except Exception as e:
        print(f"[WARN] YOLO 模型预加载出错: {e}")
    
    # 2. 启动后台任务
    start_schedule_checker()
    print("[INFO] 自动分配配置定时任务检查器已启动")
    start_pending_runner()
    print("[INFO] 待运行任务自动执行器已启动")
    start_failed_task_retry_checker()
    print("[INFO] 失败任务自动重试检查器已启动")
    start_minute_screenshot_fill_checker()
    print("[INFO] 每分钟截图自动补齐检查器已启动")
    # OCR功能已移除
    start_parking_change_detector()
    print("[INFO] 车位变化检测后台任务已启动")
    
    yield
    # 关闭时执行（如果需要清理资源，可以在这里添加）
    # 目前不需要清理操作


app = FastAPI(
    title="Smart RTSP Stream Manager",
    description="按10分钟切片自动拉流、截图、去重、OCR的管理API",
    version="0.1.0",
    lifespan=lifespan,
)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True, parents=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 注意：数据库表创建已移至 lifespan 函数中，确保在后台任务启动之前完成

# 注册路由模块
from app.routers import images, auto_schedule, utils, parking_changes  # noqa: E402
app.include_router(images.router)
app.include_router(auto_schedule.router)
app.include_router(utils.router)
app.include_router(parking_changes.router)

SCREENSHOT_BASE = PROJECT_ROOT / "screenshots"
SCREENSHOT_BASE.mkdir(exist_ok=True, parents=True)
app.mount("/shots", StaticFiles(directory=SCREENSHOT_BASE), name="shots")
HLS_BASE = PROJECT_ROOT / "hls"
HLS_BASE.mkdir(exist_ok=True, parents=True)
app.mount("/hls", StaticFiles(directory=HLS_BASE), name="hls")
HLS_PROCS: Dict[str, subprocess.Popen] = {}

TASK_STORE: Dict[str, List[TaskSegment]] = {}
RUNNING_KEYS: set[str] = set()

# 从配置中读取并发限制（支持环境变量配置）
MAX_COMBO_CONCURRENCY = settings.MAX_COMBO_CONCURRENCY  # 全局并发：同时运行多少个通道组合（日期+IP+通道）
MAX_WORKERS_PER_COMBO = settings.MAX_WORKERS_PER_COMBO  # 单组合并发：每个组合内部并行处理多少个任务段
COMBO_SEM = threading.Semaphore(MAX_COMBO_CONCURRENCY)
MINUTE_SCREENSHOT_WORKERS = max(
    1,
    int(
        os.getenv(
            "MAX_MINUTE_SCREENSHOT_WORKERS",
            os.getenv("MINUTE_SCREENSHOT_WORKERS", "4"),
        )
    ),
)
MINUTE_SCREENSHOT_EXECUTOR = ThreadPoolExecutor(max_workers=MINUTE_SCREENSHOT_WORKERS)

# 启动时打印并发配置信息
print(f"[INFO] ========== 并发配置信息 ==========")
print(f"[INFO] MAX_COMBO_CONCURRENCY (全局并发): {MAX_COMBO_CONCURRENCY}")
print(f"[INFO] MAX_WORKERS_PER_COMBO (单组合并发): {MAX_WORKERS_PER_COMBO}")
print(f"[INFO] MAX_MINUTE_SCREENSHOT_WORKERS (分钟截图并发): {MINUTE_SCREENSHOT_WORKERS}")
print(f"[INFO] 总并发任务数: {MAX_COMBO_CONCURRENCY * MAX_WORKERS_PER_COMBO}")
print(f"[INFO] ==================================")


def _make_task_key(date: str, base_rtsp: str, channel: str) -> str:
    base_clean = (base_rtsp or "").rstrip("/")
    channel_clean = channel or ""
    return f"{date}::{base_clean}::{channel_clean}"


def _load_tasks_to_store_from_db(date: str, base_rtsp: str, channel: str):
    """从数据库读取指定日期+基础RTSP+通道的任务，填充 TASK_STORE。"""
    key = _make_task_key(date, base_rtsp, channel)
    with SessionLocal() as db:
        prefix = f"{base_rtsp.rstrip('/')}/{channel}/%"
        rows = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.rtsp_url.like(prefix))
            .order_by(Task.index)
            .all()
        )
        if not rows:
            return False
        
        # 验证加载的RTSP URL是否正确（关键调试）
        print(f"[DEBUG] 从数据库加载任务 - 日期: {date}, 通道: {channel}, 找到 {len(rows)} 条记录")
        for idx, r in enumerate(rows[:3]):  # 只打印前3条作为示例
            expected_channel = f"/{channel}/"
            if expected_channel not in r.rtsp_url:
                print(f"[WARN] 任务 {r.id} 的RTSP URL通道不匹配！期望: {expected_channel}, 实际: {r.rtsp_url}")
            else:
                print(f"[DEBUG] 任务 {r.id} RTSP URL验证通过: {r.rtsp_url}")
        
        items = [
            TaskSegment(
                index=r.index,
                start_ts=r.start_ts,
                end_ts=r.end_ts,
                rtsp_url=r.rtsp_url,
                status=r.status,
                screenshot_path=r.screenshot_path,
                error=r.error,
            )
            for r in rows
        ]
        TASK_STORE[key] = items
        print(f"[INFO] 已从数据库加载 {len(items)} 个任务段到 TASK_STORE[{key}]")
        return True


def _run_combo_async(run_req: RunTaskRequest):
    """独立线程执行一个通道组合的任务，使用全局并发限制。"""
    key = _make_task_key(run_req.date, run_req.base_rtsp, run_req.channel)
    if key in RUNNING_KEYS:
        print(f"[INFO] 任务组合已在运行中: {key}")
        return
    acquired = COMBO_SEM.acquire(blocking=False)
    if not acquired:
        print(f"[WARN] 并发已达上限({MAX_COMBO_CONCURRENCY})，暂不启动: {key}")
        return
    RUNNING_KEYS.add(key)
    try:
        # 确保 TASK_STORE 有数据
        loaded = _load_tasks_to_store_from_db(run_req.date, run_req.base_rtsp, run_req.channel)
        if not loaded:
            ensure_tasks(
                TaskCreateRequest(
                    date=run_req.date,
                    base_rtsp=run_req.base_rtsp,
                    channel=run_req.channel,
                    interval_minutes=run_req.interval_minutes,
                )
            )
        _process_run(run_req)
    finally:
        RUNNING_KEYS.discard(key)
        COMBO_SEM.release()


def start_pending_runner():
    """后台扫描待运行任务，自动启动未运行的组合。"""
    def loop():
        while True:
            try:
                with SessionLocal() as db:
                    rows = (
                        db.query(Task)
                        .filter(Task.status.in_(["pending", "playing"]))
                        .filter((Task.screenshot_path.is_(None)) | (Task.screenshot_path == ""))
                        .all()
                    )
                combos = []
                for r in rows:
                    channel_match = re.search(r"/(c\d+)/", r.rtsp_url)
                    if channel_match:
                        channel = channel_match.group(1)
                        base_rtsp = r.rtsp_url.split(f"/{channel}/")[0]
                        combos.append((r.date, base_rtsp, channel))
                combos = list({c for c in combos})
                for date, base_rtsp, channel in combos:
                    key = _make_task_key(date, base_rtsp, channel)
                    if key in RUNNING_KEYS:
                        continue
                    run_req = RunTaskRequest(
                        date=date,
                        base_rtsp=base_rtsp,
                        channel=channel,
                        interval_minutes=10,
                    )
                    t = threading.Thread(target=_run_combo_async, args=(run_req,))
                    t.daemon = True
                    t.start()
            except Exception as e:
                print(f"[WARN] pending runner error: {e}")
            time.sleep(5)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


def ensure_tasks(req: TaskCreateRequest) -> TaskCreateResponse:
    # 提取IP地址用于重复检查
    ip_match = re.search(r"@([\d.]+)(?::\d+)?", req.base_rtsp)
    ip_val = ip_match.group(1) if ip_match else None
    
    with SessionLocal() as db:
        # 检查该IP+日期+通道的任务是否已存在
        existing_query = db.query(Task).filter(Task.date == req.date)
        if ip_val:
            existing_query = existing_query.filter(
                (Task.ip == ip_val) | (Task.rtsp_url.ilike(f"%@{ip_val}%"))
            )
        else:
            existing_query = existing_query.filter(Task.rtsp_url.ilike(f"%{req.base_rtsp}%"))
        
        # 检查通道
        channel_clean = req.channel.strip().lower()
        if not channel_clean.startswith("c"):
            channel_clean = f"c{channel_clean}"
        existing_query = existing_query.filter(
            (Task.channel == channel_clean) | (Task.rtsp_url.ilike(f"%/{channel_clean}/%"))
        )
        
        existing_tasks = existing_query.all()
        
        if existing_tasks:
            # 检查是否所有时间段的任务都已存在（通过检查任务数量）
            # 估算该日期应该有多少个任务段（144个，每10分钟一个）
            expected_count = (24 * 60) // req.interval_minutes
            if len(existing_tasks) >= expected_count * 0.9:  # 允许10%的误差
                # 任务已存在，返回特殊响应而不是抛出异常
                return TaskCreateResponse(
                    date=req.date,
                    total_segments=len(existing_tasks),
                    segments=[],
                    message=f"该IP({ip_val or '未知'})在日期{req.date}下通道{req.channel}的任务已存在，共{len(existing_tasks)}个任务",
                    existing_count=len(existing_tasks),
                    created_count=0
                )
            else:
                print(f"[INFO] 发现部分任务已存在({len(existing_tasks)}个)，将继续生成新任务")
    
    # 先校验流可用性（用第一段 URL 检测），失败仅警告不阻塞生成
    test_segments = build_segment_tasks(
        req.date, base_rtsp=req.base_rtsp, channel=req.channel, interval_minutes=req.interval_minutes
    )
    if not test_segments:
        raise HTTPException(status_code=400, detail="no segments generated")
    first_url = test_segments[0]["rtsp_url"]
    ok, err = check_rtsp(first_url)
    if not ok:
        print(f"[WARN] RTSP check failed, continue generating tasks. detail={err[:300]}")

    segments = build_segment_tasks(
        req.date, base_rtsp=req.base_rtsp, channel=req.channel, interval_minutes=req.interval_minutes
    )
    models = [TaskSegment(**seg) for seg in segments]
    key = _make_task_key(req.date, req.base_rtsp, req.channel)
    TASK_STORE[key] = models

    if not models:
        raise HTTPException(status_code=400, detail="no segments generated")

    with SessionLocal() as db:
        # 清理同日期、同RTSP地址、同通道的旧记录（级联删除 screenshots/ocr_results）
        # 这样不同通道的任务可以共存
        print(f"[INFO] 生成任务 - 日期: {req.date}, RTSP: {req.base_rtsp}, 通道: {req.channel}, 间隔: {req.interval_minutes}分钟")
        _clear_date_data(db, req.date, base_rtsp=req.base_rtsp, channel=req.channel)
        
        # 检查清理后是否还有其他通道的任务
        remaining_tasks = db.query(Task).filter(Task.date == req.date).count()
        print(f"[INFO] 清理后，同日期还有 {remaining_tasks} 个任务（应该包含其他通道的任务）")
        
        # 验证：检查各个通道的任务数量
        if remaining_tasks > 0:
            all_remaining = db.query(Task.rtsp_url).filter(Task.date == req.date).all()
            channel_counts = {}
            for (rtsp_url,) in all_remaining:
                channel_match = re.search(r'/(c\d+)/', rtsp_url)
                if channel_match:
                    ch = channel_match.group(1)
                    channel_counts[ch] = channel_counts.get(ch, 0) + 1
            print(f"[INFO] 清理后各通道任务数量: {channel_counts}")
        
        # 创建任务批次记录
        first_rtsp = models[0].rtsp_url
        ip_val_for_batch = None
        ip_match_batch = re.search(r"@([\d.]+)(?::\d+)?", first_rtsp)
        if ip_match_batch:
            ip_val_for_batch = ip_match_batch.group(1)
        ch_val_for_batch = None
        ch_match_batch = re.search(r"/(c\d+)/", first_rtsp)
        if ch_match_batch:
            ch_val_for_batch = ch_match_batch.group(1)

        batch_start_ts = min(m.start_ts for m in models)
        batch_end_ts = max(m.end_ts for m in models)

        batch = TaskBatch(
            date=req.date,
            ip=ip_val_for_batch,
            channel=ch_val_for_batch or req.channel,
            base_rtsp=req.base_rtsp,
            start_ts=batch_start_ts,
            end_ts=batch_end_ts,
            interval_minutes=req.interval_minutes,
            status="pending",
            task_count=len(models),
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)

        print(
            f"[INFO] 创建任务批次 - 日期: {req.date}, IP: {ip_val_for_batch}, 通道: {ch_val_for_batch or req.channel}, "
            f"时间段: {batch_start_ts}-{batch_end_ts}, 间隔: {req.interval_minutes} 分钟, 分片数: {len(models)}"
        )

        # 添加新任务
        added_count = 0
        for seg in models:
            # 解析 IP 和通道，便于索引查询
            ip_val = None
            ip_match = re.search(r"@([\d.]+)(?::\d+)?", seg.rtsp_url)
            if ip_match:
                ip_val = ip_match.group(1)
            ch_val = None
            ch_match = re.search(r"/(c\d+)/", seg.rtsp_url)
            if ch_match:
                ch_val = ch_match.group(1)
            db.add(
                Task(
                    date=req.date,
                    index=seg.index,
                    start_ts=seg.start_ts,
                    end_ts=seg.end_ts,
                    rtsp_url=seg.rtsp_url,
                    status=seg.status,
                    ip=ip_val,
                    channel=ch_val,
                    batch_id=batch.id,
                )
            )
            added_count += 1
        db.commit()
        print(f"[INFO] 已添加 {added_count} 个新任务 - 日期: {req.date}, 通道: {req.channel}")
        
        # 验证：检查同日期所有任务数量
        total_tasks = db.query(Task).filter(Task.date == req.date).count()
        print(f"[INFO] 当前同日期总任务数: {total_tasks}")
        
        # 验证：检查各个通道的任务数量
        all_tasks = db.query(Task.rtsp_url).filter(Task.date == req.date).all()
        channel_counts = {}
        for (rtsp_url,) in all_tasks:
            channel_match = re.search(r'/(c\d+)/', rtsp_url)
            if channel_match:
                ch = channel_match.group(1)
                channel_counts[ch] = channel_counts.get(ch, 0) + 1
        print(f"[INFO] 当前各通道任务数量: {channel_counts}")
        
        # 验证：检查当前通道的任务数量
        current_channel_tasks = db.query(Task).filter(
            Task.date == req.date,
            Task.rtsp_url.like(f"{req.base_rtsp.rstrip('/')}/{req.channel}/%")
        ).count()
        print(f"[INFO] 当前通道 {req.channel} 的任务数量: {current_channel_tasks} (应该等于 {added_count})")
    return TaskCreateResponse(
        date=req.date,
        total_segments=len(models),
        segments=models,
        created_segments=added_count,
        existing_segments=0,
        created_count=added_count,
        existing_count=0
    )


def _reconcile_task_status(db):
    """
    将已生成截图但状态仍为非 completed 的任务纠正为 completed，避免前端显示“运行中但已有截图”。
    """
    stale = (
        db.query(Task)
        .filter(Task.screenshot_path.isnot(None))
        .filter(Task.screenshot_path != "")
        .filter(Task.status != "completed")
        .all()
    )
    if not stale:
        return
    batch_ids = {t.batch_id for t in stale if t.batch_id}
    for t in stale:
        t.status = "completed"
        t.error = None
        t.next_retry_at = None
    db.commit()
    for bid in batch_ids:
        _update_batch_status_if_done(db, bid)


@app.post("/api/tasks/create", response_model=TaskCreateResponse)
def create_tasks(req: TaskCreateRequest):
    """
    生成指定日期的10分钟分片任务列表（默认144个片段）。
    """
    res = ensure_tasks(req)
    # 生成后自动尝试运行对应组合
    run_req = RunTaskRequest(
        date=req.date,
        base_rtsp=req.base_rtsp,
        channel=req.channel,
        interval_minutes=req.interval_minutes,
    )
    threading.Thread(target=_run_combo_async, args=(run_req,), daemon=True).start()
    return res


@app.get("/api/tasks/available_dates")
def list_task_dates():
    """
    从任务表的 start_ts 字段提取所有唯一的日期（YYYY-MM-DD 格式），用于填充日期搜索下拉框。
    """
    dates_set = set()
    with SessionLocal() as db:
        rows = db.query(Task.start_ts).distinct().all()
        for (start_ts,) in rows:
            if start_ts:
                # 将时间戳转换为日期字符串 YYYY-MM-DD
                try:
                    dt = datetime.fromtimestamp(start_ts)
                    date_str = dt.strftime("%Y-%m-%d")
                    dates_set.add(date_str)
                except (ValueError, OSError):
                    continue
    # 按日期排序返回
    dates_list = sorted(list(dates_set), reverse=True)  # 最新的在前
    return {"dates": [{"date": d} for d in dates_list]}


@app.get("/api/tasks/available_ips")
def list_task_ips():
    """
    从任务表的 rtsp_url 字段提取所有唯一的 IP 地址，用于填充 IP 搜索下拉框。
    RTSP URL 格式：rtsp://admin:admin123=@192.168.54.227:554/c2/...
    """
    ips_set = set()
    with SessionLocal() as db:
        rows = db.query(Task.ip, Task.rtsp_url).distinct().all()
        for ip_val, rtsp_url in rows:
            if ip_val:
                ips_set.add(ip_val)
                continue
            if rtsp_url:
                match = re.search(r'@([\d.]+)(?::\d+)?/', rtsp_url)
                if match:
                    ips_set.add(match.group(1))
    # 按 IP 排序返回
    ips_list = sorted(list(ips_set))
    return {"ips": [{"ip": ip} for ip in ips_list]}


def parse_channel_code_from_display(display_text: str) -> str:
    """
    从通道显示名称（如 "C1 高新四路9号枪机"）中解析出 channel_code（如 "c1"）。
    如果无法解析，返回原始文本的小写形式。
    """
    if not display_text:
        return ""
    display_text = display_text.strip()
    # 尝试匹配开头的通道代码（如 C1, c1, c2 等）
    match = re.match(r'^([cC]\d+)', display_text)
    if match:
        return match.group(1).lower()
    # 如果没有匹配到，返回原始文本的小写形式（向后兼容）
    return display_text.lower()


def get_nvr_ip_from_channel_display(display_text: str) -> Optional[str]:
    """
    根据通道显示名称（如 "C1 高新四路9号枪机"）查询对应的 NVR IP。
    返回匹配的 NVR IP，如果找不到则返回 None。
    """
    from sqlalchemy import or_
    
    if not display_text:
        return None
    display_text = display_text.strip()
    
    # 解析 channel_code 和 camera_name
    match = re.match(r'^([cC]\d+)\s+(.+)', display_text)
    if not match:
        return None
    
    channel_code = match.group(1).lower()
    camera_name = match.group(2).strip()
    
    with SessionLocal() as db:
        # 查询匹配的 ChannelConfig（根据 channel_code 和 camera_name）
        channel_config = db.query(ChannelConfig).join(NvrConfig).filter(
            ChannelConfig.channel_code == channel_code,
            or_(
                ChannelConfig.camera_name == camera_name,
                ChannelConfig.camera_ip == camera_name
            )
        ).first()
        
        if channel_config and channel_config.nvr_config:
            return channel_config.nvr_config.nvr_ip
    
    return None


@app.get("/api/tasks/available_channels")
def list_task_channels():
    """
    从 ChannelConfig 表中获取所有唯一的通道编号（c1/c2/c3/c4...），
    用于填充任务列表、任务配置列表中的“通道”下拉框。
    这里只返回纯通道代码，不带摄像头名称。
    """
    channels_set = set()
    with SessionLocal() as db:
        # 从 ChannelConfig 表中查询所有唯一的 channel_code
        rows = db.query(ChannelConfig.channel_code).distinct().all()
        for row in rows:
            code = (row.channel_code or "").strip().lower()
            if code:
                channels_set.add(code)

    # 按通道编号中的数字部分排序（c1,c2,c3,...）
    channels_list = sorted(
        list(channels_set),
        key=lambda x: int(re.search(r"\d+", x).group()) if re.search(r"\d+", x) else 0,
    )
    # 返回形如 {"channels": [{"channel": "c1"}, {"channel": "c2"}, ...]}
    return {"channels": [{"channel": ch} for ch in channels_list]}


@app.post("/api/tasks/configs/rerun")
def rerun_config_tasks(
    request: RerunConfigRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    重新运行指定配置下的所有任务。
    根据日期、IP地址、通道匹配任务并重新运行。
    """
    date = request.date
    rtsp_ip = request.rtsp_ip
    channel = request.channel
    print(f"[INFO] 开始重新运行配置任务 - 日期: {date}, IP: {rtsp_ip}, 通道: {channel}")
    
    # 从通道参数中提取纯通道编号（如从 "c4 高新四路32号枪机" 提取 "c4"）
    channel_code = None
    if channel:
        import re
        # 提取 c1, c2, c3, c4 等通道编号（匹配 c 后跟数字）
        channel_match = re.search(r'\b(c\d+)\b', channel, re.IGNORECASE)
        if channel_match:
            channel_code = channel_match.group(1).lower()  # 统一转为小写
            print(f"[INFO] 从通道参数 '{channel}' 中提取到通道编号: {channel_code}")
        else:
            # 如果没有匹配到，尝试直接使用原始值（去除首尾空格）
            channel_code = channel.strip()
            print(f"[WARN] 无法从通道参数 '{channel}' 中提取通道编号，使用原始值: {channel_code}")
    
    with SessionLocal() as db:
        # 查找匹配的任务
        query = db.query(Task).filter(Task.date == date)
        if rtsp_ip:
            like_expr = f"%{rtsp_ip}%"
            query = query.filter(Task.rtsp_url.ilike(like_expr))
            print(f"[DEBUG] 添加IP过滤条件: {like_expr}")
        if channel_code:
            # 使用提取的通道编号进行匹配
            like_expr = f"%/{channel_code}/%"
            query = query.filter(Task.rtsp_url.ilike(like_expr))
            print(f"[DEBUG] 添加通道过滤条件: {like_expr}")
        
        # 打印查询条件用于调试
        print(f"[DEBUG] 查询条件 - 日期: {date}, IP: {rtsp_ip}, 通道编号: {channel_code}")
        
        tasks = query.all()
        print(f"[DEBUG] 查询结果: 找到 {len(tasks)} 个任务")
        
        if not tasks:
            # 尝试查询是否有该日期的任务（用于调试）
            total_tasks_for_date = db.query(Task).filter(Task.date == date).count()
            print(f"[WARN] 未找到匹配的任务 - 日期: {date}, IP: {rtsp_ip}, 通道: {channel} (通道编号: {channel_code})")
            print(f"[DEBUG] 该日期共有 {total_tasks_for_date} 个任务，但都不匹配当前查询条件")
            raise HTTPException(status_code=404, detail=f"未找到匹配的任务 - 日期: {date}, IP: {rtsp_ip}, 通道: {channel_code or channel}")
        
        print(f"[INFO] 找到 {len(tasks)} 个匹配的任务，开始筛选需重跑的子任务")

        # 仅重跑失败或无截图的子任务，避免已成功的重复执行
        rerun_tasks = [
            t for t in tasks
            if (t.status == "failed") or (t.screenshot_path is None or t.screenshot_path == "")
        ]
        if not rerun_tasks:
            print(f"[INFO] 无需重跑：所有匹配任务均已成功且有截图")
            return {
                "message": "无需重跑，已成功的子任务不会重复执行",
                "count": 0,
                "date": date,
                "rtsp_ip": rtsp_ip,
                "channel": channel,
            }

        print(f"[INFO] 需重跑 {len(rerun_tasks)} 个子任务（失败或无截图）")
        
        # 先将所有任务状态更新为"playing"（运行中）
        for task in rerun_tasks:
            task.status = "playing"
            task.updated_at = datetime.utcnow()
        db.commit()
        print(f"[INFO] 已将 {len(rerun_tasks)} 个待重跑任务状态更新为'运行中'")
        
        # 在后台重新运行所有任务
        for idx, task in enumerate(rerun_tasks, 1):
            print(f"[INFO] 添加任务 {idx}/{len(rerun_tasks)} 到重新运行队列 - 任务ID: {task.id}, RTSP: {task.rtsp_url}")
            background_tasks.add_task(_rerun_single_task, task.id)
        
        print(f"[INFO] 已将所有 {len(rerun_tasks)} 个任务加入重新运行队列")
        
        return {
            "message": f"已加入重新运行队列，共 {len(rerun_tasks)} 个任务（仅失败/无截图）",
            "count": len(rerun_tasks),
            "date": date,
            "rtsp_ip": rtsp_ip,
            "channel": channel,
        }


@app.get("/api/tasks/configs")
def list_task_configs(
    date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    # 新的搜索参数（FastAPI会将URL中的双下划线转换为单下划线，所以函数参数名使用单下划线，alias指定URL中的参数名）
    date_like: Optional[str] = Query(None, alias="date__like"),  # 模糊搜索日期（如 "2025-12"）
    ip: Optional[str] = None,  # 精准搜索IP
    ip_like: Optional[str] = Query(None, alias="ip__like"),  # 模糊搜索IP
    channel: Optional[str] = None,  # 精准搜索通道
    channel_like: Optional[str] = Query(None, alias="channel__like"),  # 模糊搜索通道
    rtsp_base_like: Optional[str] = Query(None, alias="rtsp_base__like"),  # 模糊搜索RTSP基础地址
    status: Optional[str] = None,  # 精准搜索状态（待运行、运行中、完成、部分失败）
    status_in: Optional[str] = Query(None, alias="status__in", description="多选状态，逗号分隔"),  # 多选状态
    start_ts_gte: Optional[int] = Query(None, alias="start_ts__gte"),  # 开始时间戳 >=
    start_ts_lte: Optional[int] = Query(None, alias="start_ts__lte"),  # 开始时间戳 <=
    end_ts_gte: Optional[int] = Query(None, alias="end_ts__gte"),  # 结束时间戳 >=
    end_ts_lte: Optional[int] = Query(None, alias="end_ts__lte"),  # 结束时间戳 <=
    interval_minutes: Optional[int] = None,  # 精准搜索间隔分钟数
    interval_minutes_gte: Optional[int] = Query(None, alias="interval_minutes__gte"),  # 间隔分钟数 >=
    interval_minutes_lte: Optional[int] = Query(None, alias="interval_minutes__lte"),  # 间隔分钟数 <=
    operation_time_gte: Optional[str] = Query(None, alias="operation_time__gte"),  # 操作时间 >= (ISO格式)
    operation_time_lte: Optional[str] = Query(None, alias="operation_time__lte"),  # 操作时间 <= (ISO格式)
):
    """
    获取任务配置汇总列表，按日期、RTSP地址、通道、间隔分组。
    返回每个配置的汇总信息，包括任务状态统计。
    支持丰富的搜索条件和分页，page_size 限制在 10-50 之间。
    """
    page = max(page, 1)
    page_size = max(min(page_size, 50), 10)  # 限制在10-50之间
    with SessionLocal() as db:
        from sqlalchemy import or_, and_

        # 纠正状态：有截图但状态非 completed 的，自动标为 completed
        _reconcile_task_status(db)
        
        # 通过 SQL 联表一次性查出摄像头名称（ChannelConfig.camera_name），
        # 后面用于把通道从 "c1" 显示为 "c1 高新四路36号枪机" 等
        query = (
            db.query(
            Task.id,
            Task.date,
            Task.start_ts,
            Task.end_ts,
            Task.rtsp_url,
            Task.ip,
            Task.channel,
            Task.status,
            Task.updated_at,
            Screenshot.id.label("shot_id"),
            Screenshot.file_path.label("shot_path"),
                ChannelConfig.camera_name.label("camera_name"),
                NvrConfig.parking_name.label("parking_name"),
            )
            .outerjoin(Screenshot, Screenshot.task_id == Task.id)
            .outerjoin(NvrConfig, NvrConfig.nvr_ip == Task.ip)
            .outerjoin(
                ChannelConfig,
                and_(
                    ChannelConfig.nvr_config_id == NvrConfig.id,
                    ChannelConfig.channel_code == Task.channel,
                ),
            )
        )

        # 日期搜索
        if date:
            query = query.filter(Task.date == date)
        elif date_like:
            query = query.filter(Task.date.like(f"%{date_like}%"))
        
        # IP地址搜索
        if ip:
            ip_clean = ip.strip()
            query = query.filter(
                or_(
                    Task.ip == ip_clean,
                    and_(Task.ip.is_(None), Task.rtsp_url.ilike(f"%@{ip_clean}%")),
                )
            )
        elif ip_like:
            ip_like_val = ip_like.strip()
            query = query.filter(
                or_(
                    Task.ip.ilike(f"%{ip_like_val}%"),
                    Task.rtsp_url.ilike(f"%@{ip_like_val}%"),
                )
            )
        
        # 通道搜索
        if channel:
            ch_clean = channel.strip().lower()
            if not ch_clean.startswith("c"):
                ch_clean = f"c{ch_clean}"
            if ch_clean.startswith("/"):
                ch_clean = ch_clean.strip("/")
            query = query.filter(
                or_(
                    Task.channel == ch_clean,
                    and_(Task.channel.is_(None), Task.rtsp_url.ilike(f"%/{ch_clean}/%")),
                )
            )
        elif channel_like:
            ch_like = channel_like.strip().lower()
            if not ch_like.startswith("c"):
                ch_like = f"c{ch_like}"
            query = query.filter(
                or_(
                    Task.channel.ilike(f"%{ch_like}%"),
                    Task.rtsp_url.ilike(f"%/{ch_like}%"),
                )
            )
        
        # RTSP基础地址搜索
        if rtsp_base_like:
            like_expr = f"%{rtsp_base_like.strip()}%"
            query = query.filter(Task.rtsp_url.ilike(like_expr))
        
        # 时间戳范围搜索
        if start_ts_gte is not None:
            query = query.filter(Task.start_ts >= start_ts_gte)
        if start_ts_lte is not None:
            query = query.filter(Task.start_ts <= start_ts_lte)
        if end_ts_gte is not None:
            query = query.filter(Task.end_ts >= end_ts_gte)
        if end_ts_lte is not None:
            query = query.filter(Task.end_ts <= end_ts_lte)
        
        # 操作时间范围搜索
        if operation_time_gte:
            try:
                op_time_gte = datetime.fromisoformat(operation_time_gte.replace('Z', '+00:00'))
                query = query.filter(Task.updated_at >= op_time_gte)
            except ValueError:
                pass
        if operation_time_lte:
            try:
                op_time_lte = datetime.fromisoformat(operation_time_lte.replace('Z', '+00:00'))
                query = query.filter(Task.updated_at <= op_time_lte)
            except ValueError:
                pass

        query = query.order_by(Task.date, Task.start_ts)
        rows = query.all()

        configs_dict = {}
        for r in rows:
            ip = r.ip
            if not ip:
                ip_match = re.search(r'@([\d.]+)(?::\d+)?/', r.rtsp_url)
                ip = ip_match.group(1) if ip_match else ""
            channel = r.channel
            if not channel:
                channel_match = re.search(r'/(c\d+)/', r.rtsp_url)
                channel = channel_match.group(1) if channel_match else ""
            # 通过 SQL 联表得到的摄像头名称（可能为 None）
            camera_name = (getattr(r, "camera_name", None) or "").strip()
            # 通过 SQL 联表得到的停车场名称（可能为 None）
            parking_name = (getattr(r, "parking_name", None) or "").strip()

            interval_minutes = (r.end_ts - r.start_ts) // 60 if r.end_ts > r.start_ts else 10

            config_key = (r.date, ip, channel, interval_minutes)

            if config_key not in configs_dict:
                configs_dict[config_key] = {
                    "date": r.date,
                    "ip": ip,
                    "parking_name": parking_name if parking_name else None,  # 停车场名称
                    "rtsp_base": f"rtsp://admin:admin123=@{ip}:554"
                    if ip
                    else r.rtsp_url.split("/c")[0]
                    if "/c" in r.rtsp_url
                    else r.rtsp_url,
                    # 接口返回的通道字段：通道编码 + 摄像头名称（如果查得到）
                    # 例如： "c1 高新四路36号枪机"
                    "channel": f"{channel} {camera_name}" if camera_name else channel,
                    "interval_minutes": interval_minutes,
                    "start_ts": r.start_ts,
                    "end_ts": r.end_ts,
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "pending": 0,
                    "playing": 0,
                    "operation_time": None,
                    "seen_tasks": set(),
                    "seen_completed_tasks": set(),
                }

            config = configs_dict[config_key]
            if r.id in config["seen_tasks"]:
                if r.shot_path and r.id not in config["seen_completed_tasks"]:
                    config["completed"] += 1
                    config["seen_completed_tasks"].add(r.id)
                continue

            config["seen_tasks"].add(r.id)
            config["total"] += 1
            config["start_ts"] = min(config["start_ts"], r.start_ts)
            config["end_ts"] = max(config["end_ts"], r.end_ts)
            if r.updated_at:
                if config["operation_time"] is None or r.updated_at > config["operation_time"]:
                    config["operation_time"] = r.updated_at

            if r.shot_path:
                config["completed"] += 1
                config["seen_completed_tasks"].add(r.id)
            elif r.status == "completed":
                config["completed"] += 1
            elif r.status == "screenshot_taken":
                config["completed"] += 1
            elif r.status == "failed":
                config["failed"] += 1
            elif r.status == "pending":
                config["pending"] += 1
            elif r.status == "playing":
                config["playing"] += 1
            else:
                config["pending"] += 1

        configs_list = []
        # 按操作时间降序排序，最新的在最前面（operation_time 为 None 的排在最后）
        sorted_configs = sorted(
            configs_dict.items(),
            key=lambda x: (x[1]["operation_time"] is None, -(x[1]["operation_time"].timestamp() if x[1]["operation_time"] else 0))
        )
        for idx, (key, config) in enumerate(sorted_configs, 1):
            if config["completed"] == config["total"]:
                status_text = "完成"
                status_detail = f"{config['completed']}/{config['total']}"
            elif config["failed"] > 0:
                status_text = "部分失败"
                status_detail = f"完成:{config['completed']} 失败:{config['failed']} 总计:{config['total']}"
            elif config["playing"] > 0 or (config["completed"] > 0 and config["completed"] < config["total"]):
                status_text = "运行中"
                status_detail = f"{config['completed']}/{config['total']}"
            elif config["pending"] == config["total"]:
                status_text = "待运行"
                status_detail = f"0/{config['total']}"
            else:
                status_text = "待运行"
                status_detail = f"{config['completed']}/{config['total']}"

            configs_list.append(
                {
                    "index": idx,
                    "date": config["date"],
                    "ip": config["ip"],
                    "parking_name": config.get("parking_name"),  # 停车场名称
                    "start_ts": config["start_ts"],
                    "end_ts": config["end_ts"],
                    "rtsp_base": config["rtsp_base"],
                    "channel": config["channel"],
                    "interval_minutes": config["interval_minutes"],
                    "status": status_text,
                    "status_detail": status_detail,
                    "total": config["total"],
                    "completed": config["completed"],
                    "failed": config["failed"],
                    "operation_time": config["operation_time"].isoformat() if config["operation_time"] else None,
                }
            )
        
        # 应用状态和间隔时间的过滤（在汇总后过滤）
        filtered_configs = configs_list
        if status:
            # status参数可以是中文状态或英文状态
            filtered_configs = [c for c in filtered_configs if c["status"] == status]
        elif status_in:
            status_list = [s.strip() for s in status_in.split(",") if s.strip()]
            if status_list:
                filtered_configs = [c for c in filtered_configs if c["status"] in status_list]
        
        if interval_minutes is not None:
            filtered_configs = [c for c in filtered_configs if c["interval_minutes"] == interval_minutes]
        if interval_minutes_gte is not None:
            filtered_configs = [c for c in filtered_configs if c["interval_minutes"] >= interval_minutes_gte]
        if interval_minutes_lte is not None:
            filtered_configs = [c for c in filtered_configs if c["interval_minutes"] <= interval_minutes_lte]
        
        configs_list = filtered_configs

        total = len(configs_list)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = configs_list[start_idx:end_idx]

        for idx, item in enumerate(paginated_items, start=start_idx + 1):
            item["index"] = idx

        return {
            "date": date,
            "page": page,
            "page_size": page_size,
            "total": total,
            "count": len(paginated_items),
            "items": paginated_items,
        }


@app.delete("/api/tasks/configs")
def delete_config_tasks(
    date: str = Query(..., description="任务日期"),
    rtsp_ip: str = Query(..., description="RTSP IP地址"),
    channel: str = Query(..., description="通道"),
):
    """
    删除指定配置下的所有任务及其关联数据。
    根据日期、IP地址、通道匹配任务并删除。
    """
    with SessionLocal() as db:
        # 查找匹配的任务
        query = db.query(Task).filter(Task.date == date)
        if rtsp_ip:
            like_expr = f"%{rtsp_ip}%"
            query = query.filter(Task.rtsp_url.ilike(like_expr))
        if channel:
            like_expr = f"%/{channel}/%" if not channel.startswith("/") else f"%{channel}%"
            query = query.filter(Task.rtsp_url.ilike(like_expr))
        
        tasks = query.all()
        if not tasks:
            raise HTTPException(status_code=404, detail="未找到匹配的任务")
        
        task_ids = [t.id for t in tasks]
        
        # 删除关联的截图记录，同时删除物理文件
        from models import Screenshot
        screenshots = db.query(Screenshot).filter(Screenshot.task_id.in_(task_ids)).all()
        screenshot_ids = [s.id for s in screenshots]
        
        # 删除物理文件
        for shot in screenshots:
            if shot.file_path:
                file_path = Path(shot.file_path)
                if not file_path.is_absolute():
                    file_path = SCREENSHOT_BASE / file_path
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except Exception as e:
                        print(f"[WARN] Failed to delete file {file_path}: {e}")
        
        # 删除数据库记录（OCR功能已移除，不再删除OCR记录）
        db.query(Screenshot).filter(Screenshot.task_id.in_(task_ids)).delete(synchronize_session=False)
        db.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)
        db.commit()
        
        return {
            "message": f"已删除 {len(tasks)} 个任务及其关联数据",
            "count": len(tasks),
            "date": date,
            "rtsp_ip": rtsp_ip,
            "channel": channel,
        }


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    """
    删除单个任务及其关联的截图、OCR结果和物理文件。
    """
    print(f"[INFO] 开始删除任务 - 任务ID: {task_id}")
    try:
        with SessionLocal() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                print(f"[WARN] 任务不存在 - 任务ID: {task_id}")
                raise HTTPException(status_code=404, detail="任务不存在")
            
            print(f"[INFO] 找到任务 - ID: {task_id}, 日期: {task.date}, RTSP: {task.rtsp_url}")
            
            # 删除关联的截图记录，同时删除物理文件
            from models import Screenshot
            screenshots = db.query(Screenshot).filter(Screenshot.task_id == task_id).all()
            screenshot_ids = [s.id for s in screenshots]
            print(f"[INFO] 找到 {len(screenshots)} 个关联的截图记录")
            
            # 删除物理文件
            deleted_files = 0
            for shot in screenshots:
                if shot.file_path:
                    file_path = Path(shot.file_path)
                    if not file_path.is_absolute():
                        file_path = SCREENSHOT_BASE / file_path
                    if file_path.exists():
                        try:
                            file_path.unlink()
                            deleted_files += 1
                        except Exception as e:
                            print(f"[WARN] 删除文件失败 {file_path}: {e}")
            print(f"[INFO] 已删除 {deleted_files} 个物理文件")
            
            # 删除数据库记录（OCR功能已移除，不再删除OCR记录）
            
            screenshot_count = db.query(Screenshot).filter(Screenshot.task_id == task_id).count()
            db.query(Screenshot).filter(Screenshot.task_id == task_id).delete(synchronize_session=False)
            print(f"[INFO] 已删除 {screenshot_count} 个截图记录")
            
            # 删除任务
            db.delete(task)
            db.commit()
            print(f"[INFO] 任务 {task_id} 及其关联数据已成功删除")
            
            return {"message": "任务及其关联数据已删除", "task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] 删除任务失败 - 任务ID: {task_id}, 错误: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")


@app.post("/api/tasks/{task_id}/rerun")
def rerun_task(task_id: int, background_tasks: BackgroundTasks):
    """
    重新运行单个任务：重新执行截图操作，更新任务状态和数据库。
    """
    with SessionLocal() as db:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 在后台重新运行
        background_tasks.add_task(_rerun_single_task, task_id)
        
        return {"message": "任务已加入重新运行队列", "task_id": task_id}


@app.get("/api/tasks/paged")
def get_tasks_paged(
    date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    task_id: Optional[int] = None,
    # 向后兼容的旧参数
    screenshot_name: Optional[str] = None,
    rtsp_ip: Optional[str] = None,
    channel: Optional[str] = None,
    # 新的搜索参数（FastAPI会将URL中的双下划线转换为单下划线，所以函数参数名使用单下划线，alias指定URL中的参数名）
    screenshot_name_eq: Optional[str] = Query(None, alias="screenshot_name__eq"),  # 精准搜索截图文件名
    screenshot_name_like: Optional[str] = Query(None, alias="screenshot_name__like"),  # 模糊搜索截图文件名
    rtsp_url_eq: Optional[str] = Query(None, alias="rtsp_url__eq"),  # 精准搜索RTSP地址
    rtsp_url_like: Optional[str] = Query(None, alias="rtsp_url__like"),  # 模糊搜索RTSP地址
    ip: Optional[str] = None,  # 精准搜索IP
    ip_like: Optional[str] = Query(None, alias="ip__like"),  # 模糊搜索IP
    channel_eq: Optional[str] = Query(None, alias="channel__eq"),  # 精准搜索通道
    channel_like: Optional[str] = Query(None, alias="channel__like"),  # 模糊搜索通道
    status: Optional[str] = None,  # 精准搜索状态
    status_in: Optional[str] = Query(None, alias="status__in", description="多选状态，逗号分隔，如: pending,playing"),  # 多选状态
    start_ts_gte: Optional[int] = Query(None, alias="start_ts__gte"),  # 开始时间戳 >=
    start_ts_lte: Optional[int] = Query(None, alias="start_ts__lte"),  # 开始时间戳 <=
    end_ts_gte: Optional[int] = Query(None, alias="end_ts__gte"),  # 结束时间戳 >=
    end_ts_lte: Optional[int] = Query(None, alias="end_ts__lte"),  # 结束时间戳 <=
    operation_time_gte: Optional[str] = Query(None, alias="operation_time__gte"),  # 操作时间 >= (ISO格式)
    operation_time_lte: Optional[str] = Query(None, alias="operation_time__lte"),  # 操作时间 <= (ISO格式)
    error_like: Optional[str] = Query(None, alias="error__like"),  # 模糊搜索错误信息
):
    """
    获取任务列表详情（分页），支持丰富的搜索条件。
    支持精准搜索、模糊搜索、范围查询、多选查询。
    """
    page = max(page, 1)
    page_size = max(min(page_size, 50), 10)  # 限制在10-50之间
    total = 0
    with SessionLocal() as db:
        from sqlalchemy import or_, and_

        # 纠正状态：有截图但状态非 completed 的，自动标为 completed
        _reconcile_task_status(db)

        # 按序号降序排序，最大序号在最前面
        # 这里通过 SQL 联表一次性查出摄像头名称（ChannelConfig.camera_name），
        # 便于将通道从 "c1" 显示为 "c1 高新四路36号枪机" 等
        query = (
            db.query(
                Task.id,
                Task.index,
                Task.start_ts,
                Task.end_ts,
                Task.rtsp_url,
                Task.status,
                Task.screenshot_path,
                Task.error,
                Task.date,
                Task.updated_at,
                Task.ip,
                Task.channel,
                ChannelConfig.camera_name.label("camera_name"),
                NvrConfig.parking_name.label("parking_name"),
            )
            .outerjoin(NvrConfig, NvrConfig.nvr_ip == Task.ip)
            .outerjoin(
                ChannelConfig,
                and_(
                    ChannelConfig.nvr_config_id == NvrConfig.id,
                    ChannelConfig.channel_code == Task.channel,
                ),
            )
        )
        # 如果提供了日期，则按日期筛选；否则显示所有日期的数据
        if date:
            query = query.filter(Task.date == date)
        query = query.order_by(Task.index.desc())

        # 如果指定 task_id，优先精确过滤
        if task_id:
            query = query.filter(Task.id == task_id)

        # 截图文件名搜索（向后兼容 + 新参数）
        screenshot_search = screenshot_name_like or screenshot_name  # 优先使用新参数
        if screenshot_search:
            like_expr = f"%{screenshot_search.strip()}%"
            query = query.filter(Task.screenshot_path.ilike(like_expr))
        elif screenshot_name_eq:
            query = query.filter(Task.screenshot_path == screenshot_name_eq.strip())
        
        # RTSP地址搜索
        if rtsp_url_eq:
            query = query.filter(Task.rtsp_url == rtsp_url_eq.strip())
        elif rtsp_url_like:
            like_expr = f"%{rtsp_url_like.strip()}%"
            query = query.filter(Task.rtsp_url.ilike(like_expr))
        
        # IP地址搜索（向后兼容 + 新参数）
        ip_search = ip or rtsp_ip  # 优先使用新参数
        if ip_search:
            ip_clean = ip_search.strip()
            query = query.filter(
                or_(
                    Task.ip == ip_clean,
                    and_(Task.ip.is_(None), Task.rtsp_url.ilike(f"%@{ip_clean}%")),
                )
            )
        elif ip_like:
            ip_like_val = ip_like.strip()
            query = query.filter(
                or_(
                    Task.ip.ilike(f"%{ip_like_val}%"),
                    Task.rtsp_url.ilike(f"%@{ip_like_val}%"),
                )
            )
        
        # 通道搜索（向后兼容 + 新参数）
        # 注意：channel_eq 和 channel 是互斥的，优先使用新参数
        # FastAPI 会将 URL 中的双下划线转换为单下划线，所以 channel__eq 会被解析为 channel_eq
        # 但使用 Query alias 可以保持 URL 中的双下划线格式
        # 支持 "通道+摄像头名称" 格式（如 "C1 高新四路9号枪机"），会自动解析出 channel_code（如 "c1"）
        if channel_eq is not None and str(channel_eq).strip():
            ch_display = str(channel_eq).strip()
            ch_clean = parse_channel_code_from_display(ch_display)
            if not ch_clean.startswith("c"):
                ch_clean = f"c{ch_clean}"
            if ch_clean.startswith("/"):
                ch_clean = ch_clean.strip("/")
            query = query.filter(
                or_(
                    Task.channel == ch_clean,
                    and_(Task.channel.is_(None), Task.rtsp_url.ilike(f"%/{ch_clean}/%")),
                )
            )
        elif channel is not None and str(channel).strip():
            ch_display = str(channel).strip()
            ch_clean = parse_channel_code_from_display(ch_display)
            if ch_clean:  # 确保不是空字符串
                if not ch_clean.startswith("c"):
                    ch_clean = f"c{ch_clean}"
                if ch_clean.startswith("/"):
                    ch_clean = ch_clean.strip("/")
                query = query.filter(
                    or_(
                        Task.channel == ch_clean,
                        and_(Task.channel.is_(None), Task.rtsp_url.ilike(f"%/{ch_clean}/%")),
                    )
                )
        elif channel_like is not None:
            ch_display = channel_like.strip()
            ch_like = parse_channel_code_from_display(ch_display)
            if not ch_like.startswith("c"):
                ch_like = f"c{ch_like}"
            query = query.filter(
                or_(
                    Task.channel.ilike(f"%{ch_like}%"),
                    Task.rtsp_url.ilike(f"%/{ch_like}%"),
                )
            )
        
        # 状态搜索
        if status:
            query = query.filter(Task.status == status.strip())
        elif status_in:
            status_list = [s.strip() for s in status_in.split(",") if s.strip()]
            if status_list:
                query = query.filter(Task.status.in_(status_list))
        
        # 时间戳范围搜索
        if start_ts_gte is not None:
            query = query.filter(Task.start_ts >= start_ts_gte)
        if start_ts_lte is not None:
            query = query.filter(Task.start_ts <= start_ts_lte)
        if end_ts_gte is not None:
            query = query.filter(Task.end_ts >= end_ts_gte)
        if end_ts_lte is not None:
            query = query.filter(Task.end_ts <= end_ts_lte)
        
        # 操作时间范围搜索
        if operation_time_gte:
            try:
                op_time_gte = datetime.fromisoformat(operation_time_gte.replace('Z', '+00:00'))
                query = query.filter(Task.updated_at >= op_time_gte)
            except ValueError:
                pass  # 忽略无效的时间格式
        if operation_time_lte:
            try:
                op_time_lte = datetime.fromisoformat(operation_time_lte.replace('Z', '+00:00'))
                query = query.filter(Task.updated_at <= op_time_lte)
            except ValueError:
                pass  # 忽略无效的时间格式
        
        # 错误信息搜索
        if error_like:
            like_expr = f"%{error_like.strip()}%"
            query = query.filter(Task.error.ilike(like_expr))
        
        total = query.count()
        rows = query.offset((page - 1) * page_size).limit(page_size).all()
        items = []
        for r in rows:
            channel_code = (r.channel or "").strip()
            camera_name = (getattr(r, "camera_name", None) or "").strip()
            parking_name = (getattr(r, "parking_name", None) or "").strip()
            if channel_code:
                channel_display = channel_code.upper()
                if camera_name:
                    channel_display = f"{channel_code} {camera_name}"
            else:
                channel_display = ""

            items.append(
            {
                "id": r.id,
                "index": r.index,
                "start_ts": r.start_ts,
                "end_ts": r.end_ts,
                "rtsp_url": r.rtsp_url,
                "status": r.status,
                "screenshot_path": r.screenshot_path,
                "error": r.error,
                "date": r.date,
                    "ip": r.ip,
                "parking_name": parking_name if parking_name else None,  # 停车场名称
                    "channel": channel_display,
                "operation_time": r.updated_at.isoformat() if r.updated_at else None,
            }
            )
    return {"date": date or "all", "page": page, "page_size": page_size, "total": total, "items": items}


def _rerun_single_task(task_id: int):
    """
    后台重新运行单个任务的函数。
    """
    print(f"[INFO] ===== 开始重新运行任务 {task_id} =====")
    try:
        with SessionLocal() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                print(f"[ERROR] 任务 {task_id} 不存在，无法重新运行")
                return
            
            print(f"[INFO] 任务信息 - ID: {task.id}, 日期: {task.date}, RTSP: {task.rtsp_url}, 当前状态: {task.status}")
            
            # 保存任务信息（在关闭会话前）
            task_date = task.date
            task_rtsp_url = task.rtsp_url
            task_index = task.index
            task_start_ts = task.start_ts
            task_end_ts = task.end_ts
            
            # 删除旧的截图记录和OCR结果，同时删除物理文件
            from models import Screenshot
            screenshots = db.query(Screenshot).filter(Screenshot.task_id == task_id).all()
            screenshot_ids = [s.id for s in screenshots]
            print(f"[INFO] 找到 {len(screenshots)} 个旧截图记录，开始清理")
            
            # 删除物理文件
            deleted_files = 0
            for shot in screenshots:
                if shot.file_path:
                    file_path = Path(shot.file_path)
                    if not file_path.is_absolute():
                        file_path = SCREENSHOT_BASE / file_path
                    if file_path.exists():
                        try:
                            file_path.unlink()
                            deleted_files += 1
                        except Exception as e:
                            print(f"[WARN] 删除文件失败 {file_path}: {e}")
            print(f"[INFO] 已删除 {deleted_files} 个物理截图文件")
            
            # 删除数据库记录（OCR功能已移除，不再删除OCR记录）
            screenshot_count = db.query(Screenshot).filter(Screenshot.task_id == task_id).count()
            db.query(Screenshot).filter(Screenshot.task_id == task_id).delete(synchronize_session=False)
            print(f"[INFO] 已删除 {screenshot_count} 个截图记录")
            
            # 重置任务状态并更新操作时间（保持playing状态，因为已经在rerun_config_tasks中设置为playing）
            task.status = "playing"  # 保持运行中状态
            task.screenshot_path = None
            task.error = None
            task.updated_at = datetime.utcnow()  # 显式更新操作时间
            db.commit()
            print(f"[INFO] 任务状态已重置为'运行中'")
        
        # 在数据库会话外执行截图操作，避免会话过期
        # 获取截图目录
        screenshot_base = SCREENSHOT_BASE
        screenshot_dir = screenshot_base / task_date
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] 截图目录: {screenshot_dir}")
        
        # 构建任务段
        from schemas.tasks import TaskSegment
        segment = TaskSegment(
            index=task_index,
            start_ts=task_start_ts,
            end_ts=task_end_ts,
            rtsp_url=task_rtsp_url,
            status="playing",
            screenshot_path=None,
            error=None,
        )
        
        print(f"[INFO] 开始执行截图操作 - RTSP: {task_rtsp_url}")
        # 重新执行截图，使用新的数据库会话
        with SessionLocal() as db:
            _process_single_segment(segment, screenshot_dir, None, db, task_date)
        
        # 检查重试后的状态，如果成功则清空重试时间
        with SessionLocal() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                if task.status == "completed":
                    task.next_retry_at = None  # 重试成功，清空重试时间
                    db.commit()
                    print(f"[INFO] 任务 {task_id} 重试成功，已清空重试时间")
        
        print(f"[INFO] ===== 任务 {task_id} 重新运行完成，最终状态: {segment.status} =====")
    except Exception as e:
        print(f"[ERROR] 重新运行任务 {task_id} 时发生错误: {e}")
        import traceback
        traceback.print_exc()
        # 更新任务状态为失败
        try:
            with SessionLocal() as db:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.status = "failed"
                    task.error = str(e)[:500]  # 限制错误信息长度
                    task.updated_at = datetime.utcnow()
                    # 如果重试次数未达上限，计算下次重试时间
                    if task.retry_count < 3:
                        next_retry_at = _calculate_next_retry_time(task.start_ts, task.end_ts)
                        task.next_retry_at = next_retry_at
                        print(f"[INFO] 任务 {task_id} 重试失败，已设置下次重试时间: {next_retry_at} (重试次数: {task.retry_count}/3)")
                    db.commit()
        except Exception as db_err:
            print(f"[ERROR] 更新任务状态失败: {db_err}")


def _submit_minute_screenshot(
    task_id: int,
    minute_index: int,
    start_ts: int,
    end_ts: int,
    rtsp_url: str,
    date: str,
    ip: str,
    channel: str,
):
    """提交每分钟截图任务到受限线程池，避免无限制创建线程。"""
    try:
        MINUTE_SCREENSHOT_EXECUTOR.submit(
            _generate_minute_screenshot,
            task_id,
            minute_index,
            start_ts,
            end_ts,
            rtsp_url,
            date,
            ip,
            channel,
        )
    except Exception as e:
        print(
            "[ERROR] 提交每分钟截图任务失败: "
            f"task_id={task_id}, minute_index={minute_index}, error={e}"
        )


def _submit_all_minute_screenshots(
    task_id: int,
    start_ts: int,
    end_ts: int,
    rtsp_url: str,
    date: str,
    ip: str,
    channel: str,
):
    """提交生成全量分钟截图的调度任务。"""
    try:
        MINUTE_SCREENSHOT_EXECUTOR.submit(
            _generate_all_minute_screenshots,
            task_id,
            start_ts,
            end_ts,
            rtsp_url,
            date,
            ip,
            channel,
        )
    except Exception as e:
        print(f"[ERROR] 提交分钟截图调度任务失败: task_id={task_id}, error={e}")


@app.get("/api/tasks/{task_id}/minute-screenshots")
def get_minute_screenshots(task_id: int, background_tasks: BackgroundTasks):
    """
    获取任务的每分钟截图列表，如果不存在则自动生成

    业务限制：
    - 只有当对应通道的“主任务批次”（task_batches）不再处于 pending/running 状态时，
      才允许生成/查看该明细任务的每分钟截图。
      这样可以保证：
      * 每10分钟的主截图任务（TaskBatch + Task）先跑完
      * 避免在主任务仍在运行或等待时，对同一时间段重复拉流、截图，增加系统负载
    """
    with SessionLocal() as db:
        # 获取任务信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 业务限制：仅当对应的“主任务批次”不再处于 pending/running 时，才允许查看/生成分钟截图
        # 这里的主任务批次是指 task_batches 表中的记录，即某天+某IP+某通道的一批 10 分钟截图任务
        main_batch_status = None
        if task.batch_id:
            # 优先使用任务关联的批次
            batch = task.batch
            if batch:
                main_batch_status = batch.status
        else:
            # 兜底：根据 date + ip + channel 查找最近的批次
            batch = (
                db.query(TaskBatch)
                .filter(TaskBatch.date == task.date)
                .filter(TaskBatch.ip == task.ip)
                .filter(TaskBatch.channel == task.channel)
                .order_by(TaskBatch.start_ts.desc())
                .first()
            )
            if batch:
                main_batch_status = batch.status

        # 若主任务批次仍为 pending/running，先尝试根据当前任务状态更新批次（修复历史未更新的批次）
        if main_batch_status in ("pending", "running") and batch:
            _update_batch_status_if_done(db, batch.id)
            db.refresh(batch)
            main_batch_status = batch.status
        # 若批次仍未结束，但当前任务本身已完成，也允许查看并触发生成该任务的每分钟截图（避免整批卡住导致永远看不了）
        if main_batch_status in ("pending", "running") and task.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=(
                    "当前通道的主任务仍在运行或等待中，暂不支持按分钟查看截图。\n"
                    "请等待该通道对应的每10分钟主任务全部执行完成后再重试。"
                ),
            )
        
        # 计算总分钟数
        total_duration = task.end_ts - task.start_ts
        total_minutes = int((total_duration + 59) / 60)  # 向上取整
        
        # 查询已存在的每分钟截图
        existing_screenshots = db.query(MinuteScreenshot).filter(
            MinuteScreenshot.task_id == task_id
        ).all()
        
        # 构建已存在截图的索引映射
        existing_map = {ms.minute_index: ms for ms in existing_screenshots}
        
        # 生成每一分钟的RTSP URL和截图信息
        minute_screenshots = []
        for minute_index in range(total_minutes):
            minute_start_ts = task.start_ts + minute_index * 60
            minute_end_ts = min(task.start_ts + (minute_index + 1) * 60, task.end_ts)
            
            # 生成该分钟的RTSP URL
            rtsp_url = task.rtsp_url.replace(
                f"/b{task.start_ts}/e{task.end_ts}/",
                f"/b{minute_start_ts}/e{minute_end_ts}/"
            )
            
            # 检查是否已存在；仅当 status=completed 且 file_path 存在时返回可访问的 image_url，避免前端请求到不存在的文件导致 404
            if minute_index in existing_map:
                ms = existing_map[minute_index]
                image_url = None
                if ms.status == "completed" and ms.file_path:
                    image_url = f"/shots/{ms.file_path}" if not ms.file_path.startswith("/") else ms.file_path
                minute_screenshots.append({
                    "minute_index": minute_index,
                    "start_ts": minute_start_ts,
                    "end_ts": minute_end_ts,
                    "file_path": ms.file_path,
                    "image_url": image_url,
                    "status": ms.status,
                    "error": ms.error,
                    "rtsp_url": rtsp_url,
                })
            else:
                # 不存在，需要生成
                minute_screenshots.append({
                    "minute_index": minute_index,
                    "start_ts": minute_start_ts,
                    "end_ts": minute_end_ts,
                    "file_path": None,
                    "image_url": None,
                    "status": "pending",
                    "error": None,
                    "rtsp_url": rtsp_url,
                })
                # 在后台生成截图
                background_tasks.add_task(
                    _submit_minute_screenshot,
                    task_id,
                    minute_index,
                    minute_start_ts,
                    minute_end_ts,
                    rtsp_url,
                    task.date,
                    task.ip,
                    task.channel,
                )
        
        return {
            "task_id": task_id,
            "total_minutes": total_minutes,
            "minute_screenshots": minute_screenshots
        }


def _check_main_batch_status(db, task_id: int, date: str, ip: str, channel: str) -> tuple[bool, Optional[str]]:
    """
    检查主任务批次状态，判断是否允许生成每分钟截图
    
    Returns:
        (is_allowed, batch_status): 
        - is_allowed: True 表示允许生成，False 表示不允许
        - batch_status: 主任务批次的状态（如果找到的话）
    """
    try:
        # 先通过 task_id 找到任务
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return False, None
        
        # 查找主任务批次
        main_batch_status = None
        if task.batch_id:
            batch = task.batch
            if batch:
                main_batch_status = batch.status
        else:
            # 兜底：根据 date + ip + channel 查找最近的批次
            batch = (
                db.query(TaskBatch)
                .filter(TaskBatch.date == date)
                .filter(TaskBatch.ip == ip)
                .filter(TaskBatch.channel == channel)
                .order_by(TaskBatch.start_ts.desc())
                .first()
            )
            if batch:
                main_batch_status = batch.status
        
        # 如果主任务批次仍在 pending/running，先尝试根据当前任务状态更新批次（修复历史未更新的批次）
        if main_batch_status in ("pending", "running") and batch:
            _update_batch_status_if_done(db, batch.id)
            db.refresh(batch)
            main_batch_status = batch.status
        if main_batch_status in ("pending", "running"):
            # 若当前任务本身已完成，仍允许生成该任务的每分钟截图（避免整批未结束时永远无法生成）
            if task.status == "completed":
                return True, main_batch_status
            print(f"[WARN] 主任务批次状态为 {main_batch_status}，跳过每分钟截图生成 - task_id={task_id}, date={date}, ip={ip}, channel={channel}")
            return False, main_batch_status
        
        return True, main_batch_status
    except Exception as e:
        print(f"[ERROR] 检查主任务批次状态失败: task_id={task_id}, error={e}")
        # 出错时保守处理：不允许生成
        return False, None


def _update_batch_status_if_done(db, batch_id: Optional[int]) -> None:
    """
    当批次内所有任务均已完成或失败时，将 TaskBatch.status 更新为 completed / failed / partial_failed，
    以便每分钟截图逻辑不再因「主任务批次仍为 pending」而跳过。
    """
    if not batch_id:
        return
    try:
        batch = db.query(TaskBatch).filter(TaskBatch.id == batch_id).first()
        if not batch:
            return
        from sqlalchemy import func
        counts = (
            db.query(Task.status, func.count(Task.id))
            .filter(Task.batch_id == batch_id)
            .group_by(Task.status)
            .all()
        )
        total = sum(c for _, c in counts)
        if total == 0:
            return
        completed = next((c for s, c in counts if s == "completed"), 0)
        failed = next((c for s, c in counts if s == "failed"), 0)
        terminal = completed + failed
        if terminal != total:
            return
        if completed == total:
            batch.status = "completed"
        elif failed == total:
            batch.status = "failed"
        else:
            batch.status = "partial_failed"
        db.commit()
        print(f"[INFO] 主任务批次 {batch_id} 已全部结束，状态更新为: {batch.status}")
    except Exception as e:
        print(f"[ERROR] 更新批次状态失败: batch_id={batch_id}, error={e}")


def _generate_all_minute_screenshots(task_id: int, start_ts: int, end_ts: int, rtsp_url: str, date: str, ip: str, channel: str):
    """
    在任务完成时自动生成所有分钟的截图（在后台线程中执行）
    
    业务限制：只有当主任务批次不再处于 pending/running 状态时，才生成每分钟截图
    """
    try:
        # 首先检查主任务批次状态
        with SessionLocal() as db:
            is_allowed, batch_status = _check_main_batch_status(db, task_id, date, ip, channel)
            if not is_allowed:
                print(f"[INFO] 跳过每分钟截图生成 - 主任务批次状态: {batch_status}, task_id={task_id}")
                return
        
        # 计算总分钟数
        total_duration = end_ts - start_ts
        total_minutes = int((total_duration + 59) / 60)  # 向上取整
        
        print(f"[INFO] 开始为任务 {task_id} 生成 {total_minutes} 分钟的截图")
        
        # 提交每一分钟的截图任务到受限线程池
        for minute_index in range(total_minutes):
            minute_start_ts = start_ts + minute_index * 60
            minute_end_ts = min(start_ts + (minute_index + 1) * 60, end_ts)
            
            # 生成该分钟的RTSP URL
            minute_rtsp_url = rtsp_url.replace(
                f"/b{start_ts}/e{end_ts}/",
                f"/b{minute_start_ts}/e{minute_end_ts}/"
            )
            
            _submit_minute_screenshot(
                task_id,
                minute_index,
                minute_start_ts,
                minute_end_ts,
                minute_rtsp_url,
                date,
                ip,
                channel,
            )
        
        print(f"[INFO] 已提交 {total_minutes} 个每分钟截图任务")
    except Exception as e:
        print(f"[ERROR] 启动每分钟截图生成失败: task_id={task_id}, error={e}")
        import traceback
        traceback.print_exc()


def _generate_minute_screenshot(task_id: int, minute_index: int, start_ts: int, end_ts: int, rtsp_url: str, date: str, ip: str, channel: str):
    """
    在后台生成每分钟的截图
    
    业务限制：只有当主任务批次不再处于 pending/running 状态时，才执行截图
    """
    minute_screenshot_id: Optional[int] = None
    try:
        # 第一次短会话：检查状态 + 标记 processing
        with SessionLocal() as db:
            is_allowed, batch_status = _check_main_batch_status(db, task_id, date, ip, channel)
            if not is_allowed:
                print(
                    "[INFO] 跳过每分钟截图生成 - "
                    f"主任务批次状态: {batch_status}, task_id={task_id}, minute_index={minute_index}"
                )
                return

            existing = (
                db.query(MinuteScreenshot)
                .filter(
                    MinuteScreenshot.task_id == task_id,
                    MinuteScreenshot.minute_index == minute_index,
                )
                .first()
            )

            if existing and existing.status == "completed":
                print(f"[INFO] 每分钟截图已存在: task_id={task_id}, minute_index={minute_index}")
                return

            if existing:
                existing.status = "processing"
                if existing.file_path is None:
                    existing.file_path = ""
                minute_screenshot_id = existing.id
            else:
                minute_screenshot = MinuteScreenshot(
                    task_id=task_id,
                    minute_index=minute_index,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    file_path="",
                    status="processing",
                )
                db.add(minute_screenshot)
                db.flush()
                minute_screenshot_id = minute_screenshot.id
            db.commit()

        # 生成截图（不持有数据库连接）
        ip_suffix = ip.replace(".", "_") if ip else "unknown"
        channel_suffix = channel.lower() if channel else "c"
        screenshot_dir = SCREENSHOT_BASE / date
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        output_path = screenshot_dir / f"{ip_suffix}_{start_ts}_{end_ts}_{channel_suffix}.jpg"

        success = capture_frame(
            rtsp_url=rtsp_url,
            output_path=output_path,
            db=None,
            task_id=None,
            to_rel=_to_rel,
        )

        # 第二次短会话：写回结果
        with SessionLocal() as db:
            minute_screenshot = None
            if minute_screenshot_id:
                minute_screenshot = (
                    db.query(MinuteScreenshot)
                    .filter(MinuteScreenshot.id == minute_screenshot_id)
                    .first()
                )
            if not minute_screenshot:
                minute_screenshot = (
                    db.query(MinuteScreenshot)
                    .filter(
                        MinuteScreenshot.task_id == task_id,
                        MinuteScreenshot.minute_index == minute_index,
                    )
                    .first()
                )
            if not minute_screenshot:
                print(
                    "[WARN] 未找到分钟截图记录，无法更新状态: "
                    f"task_id={task_id}, minute_index={minute_index}"
                )
                return

            if success:
                minute_screenshot.file_path = _to_rel(output_path)
                minute_screenshot.status = "completed"
                minute_screenshot.error = None
                print(
                    "[INFO] 每分钟截图生成成功: "
                    f"task_id={task_id}, minute_index={minute_index}, path={minute_screenshot.file_path}"
                )
            else:
                minute_screenshot.status = "failed"
                minute_screenshot.error = "截图生成失败"
                print(f"[ERROR] 每分钟截图生成失败: task_id={task_id}, minute_index={minute_index}")

            db.commit()

    except Exception as e:
        print(f"[ERROR] 生成每分钟截图时发生错误: task_id={task_id}, minute_index={minute_index}, error={e}")
        import traceback
        traceback.print_exc()
        try:
            with SessionLocal() as db:
                existing = (
                    db.query(MinuteScreenshot)
                    .filter(
                        MinuteScreenshot.task_id == task_id,
                        MinuteScreenshot.minute_index == minute_index,
                    )
                    .first()
                )
                if existing:
                    existing.status = "failed"
                    existing.error = str(e)
                    db.commit()
        except Exception:
            pass


@app.post("/api/tasks/{task_id}/rerun")
def rerun_task(task_id: int, background_tasks: BackgroundTasks):
    """
    重新运行单个任务：重新执行截图操作，更新任务状态和数据库。
    """
    with SessionLocal() as db:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 在后台重新运行
        background_tasks.add_task(_rerun_single_task, task_id)
        
        return {"message": "任务已加入重新运行队列", "task_id": task_id}




def _process_single_segment(
    segment: TaskSegment, screenshot_dir: Path, crop_box: Optional[list[int]], db, date: str
) -> TaskSegment:
    from sqlalchemy import or_, and_
    
    print(f"[INFO] 开始处理任务段 - RTSP: {segment.rtsp_url}, 时间: {segment.start_ts} - {segment.end_ts}")
    segment.status = "playing"

    # 精确匹配当前任务行（按日期、起止时间、IP、通道）
    channel_match = re.search(r"/(c\d+)/", segment.rtsp_url)
    channel = channel_match.group(1) if channel_match else None
    
    # 提取IP地址
    ip_match = re.search(r"@([\d.]+)(?::\d+)?", segment.rtsp_url)
    ip = ip_match.group(1) if ip_match else None
    
    # 验证RTSP URL中的通道信息（关键调试日志）
    print(f"[DEBUG] 任务段RTSP URL解析 - IP: {ip}, 通道: {channel}, 完整URL: {segment.rtsp_url}")
    if not channel:
        print(f"[WARN] RTSP URL中未找到通道信息: {segment.rtsp_url}")
    if not ip:
        print(f"[WARN] RTSP URL中未找到IP信息: {segment.rtsp_url}")

    # 文件名增加 IP 和通道，避免“不同 IP 同一时间段同一通道”之间互相覆盖
    # 形如：10_10_11_123_1765814400_1765814999_c1.jpg
    channel_suffix = channel if channel else "c"
    if ip:
        ip_suffix = ip.replace(".", "_")
    else:
        ip_suffix = "unknown"
    output_path = screenshot_dir / f"{ip_suffix}_{segment.start_ts}_{segment.end_ts}_{channel_suffix}.jpg"
    print(f"[INFO] 截图保存路径: {output_path}")
    
    # 优先使用IP+通道匹配（最精确）
    task_row = None
    if ip and channel:
        task_row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(
                or_(
                    and_(Task.ip == ip, Task.channel == channel),
                    and_(Task.ip.is_(None), Task.channel == channel, Task.rtsp_url.ilike(f"%@{ip}%")),
                    and_(Task.ip == ip, Task.channel.is_(None), Task.rtsp_url.ilike(f"%/{channel}/%")),
                )
            )
            .first()
        )
    
    # 如果未找到，使用通道匹配（向后兼容）
    if not task_row and channel:
        task_row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(Task.rtsp_url.ilike(f"%/{channel}/%"))
            .first()
        )
    
    # 如果仍未找到，使用RTSP URL精确匹配（必须包含通道信息）
    if not task_row and segment.rtsp_url:
        task_row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(Task.rtsp_url == segment.rtsp_url)  # 精确匹配RTSP URL
            .first()
        )
    
    # 如果仍未找到，使用IP匹配（向后兼容，但必须同时匹配通道）
    if not task_row and ip and channel:
        task_row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(
                and_(
                    or_(Task.ip == ip, Task.rtsp_url.ilike(f"%@{ip}%")),
                    or_(Task.channel == channel, Task.rtsp_url.ilike(f"%/{channel}/%"))
                )
            )
            .first()
        )
    
    # 如果仍未找到，记录警告但不使用错误的task_id（避免通道混淆）
    if not task_row:
        print(f"[WARN] 未找到匹配的任务 - RTSP: {segment.rtsp_url}, 时间: {segment.start_ts}-{segment.end_ts}, IP: {ip}, 通道: {channel}")
        print(f"[WARN] 截图将保存但不会关联到任务记录，文件名: {output_path.name}")
    
    task_id = task_row.id if task_row else None
    
    # 再次验证RTSP URL正确性（确保截图使用正确的通道URL）
    expected_channel_in_url = f"/{channel}/" if channel else None
    if expected_channel_in_url and expected_channel_in_url not in segment.rtsp_url:
        print(f"[ERROR] RTSP URL通道不匹配！期望通道: {channel}, URL: {segment.rtsp_url}")
        print(f"[ERROR] 这将导致截图画面与任务通道不一致！")
    
    print(f"[DEBUG] 准备截图 - 使用RTSP URL: {segment.rtsp_url}, 保存到: {output_path}")
    ok = capture_frame(
        segment.rtsp_url, output_path, db=db, task_id=task_id, to_rel=_to_rel
    )
    if ok:
        # 截图成功，任务完成
        segment.status = "completed"
        segment.screenshot_path = _to_rel(output_path)
        print(f"[INFO] [OK] 截图成功 - 文件: {output_path}")
        
        # 自动生成每一分钟的截图（在后台线程中执行，不阻塞主流程）
        if task_id:
            _submit_all_minute_screenshots(
                task_id,
                segment.start_ts,
                segment.end_ts,
                segment.rtsp_url,
                date,
                ip,
                channel,
            )
            print(f"[INFO] 已提交任务 {task_id} 的每分钟截图调度")
        
        # OCR功能已移除
    else:
        segment.status = "failed"
        segment.error = "capture failed"
        print(f"[ERROR] [FAIL] 截图失败 - RTSP: {segment.rtsp_url}")
    # 直接更新数据库任务行
    if task_row:
        task_row.status = segment.status
        task_row.screenshot_path = segment.screenshot_path
        task_row.error = segment.error
        task_row.updated_at = datetime.utcnow()
        
        # 如果任务失败且重试次数未达上限，计算下次重试时间
        if segment.status == "failed" and task_row.retry_count < 3:
            next_retry_at = _calculate_next_retry_time(task_row.start_ts, task_row.end_ts)
            task_row.next_retry_at = next_retry_at
            print(f"[INFO] 任务 {task_row.id} 失败，已设置下次重试时间: {next_retry_at} (当前重试次数: {task_row.retry_count})")
        try:
            db.commit()
            if task_row.batch_id:
                _update_batch_status_if_done(db, task_row.batch_id)
        except StaleDataError:
            db.rollback()
            print(f"[WARN] 任务已被删除或不存在，跳过提交: {task_row.id if task_row else '未知'}")
    else:
        _update_task_db(db, segment, date)
    print(f"[INFO] 任务段处理完成 - 最终状态: {segment.status}")
    return segment


def _get_task_id(db, segment: TaskSegment, date: str) -> Optional[int]:
    """
    根据日期和时间戳获取任务 ID。
    优先使用IP+通道匹配，确保不同IP的通道任务不会匹配到错误记录。
    如果任务不存在，返回 None（可能任务已被删除或尚未创建）。
    """
    from sqlalchemy import or_, and_
    
    channel_match = re.search(r"/(c\d+)/", segment.rtsp_url)
    channel = channel_match.group(1) if channel_match else None
    
    # 提取IP地址
    ip_match = re.search(r"@([\d.]+)(?::\d+)?", segment.rtsp_url)
    ip = ip_match.group(1) if ip_match else None
    
    # 优先使用IP+通道匹配（最精确）
    row = None
    if ip and channel:
        row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(
                or_(
                    and_(Task.ip == ip, Task.channel == channel),
                    and_(Task.ip.is_(None), Task.channel == channel, Task.rtsp_url.ilike(f"%@{ip}%")),
                    and_(Task.ip == ip, Task.channel.is_(None), Task.rtsp_url.ilike(f"%/{channel}/%")),
                )
            )
            .first()
        )
    
    # 如果未找到，使用通道匹配（向后兼容）
    if not row and channel:
        row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(Task.rtsp_url.ilike(f"%/{channel}/%"))
            .first()
        )
    
    # 如果仍未找到，使用RTSP URL精确匹配（必须包含通道信息）
    if not row and segment.rtsp_url:
        row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(Task.rtsp_url == segment.rtsp_url)  # 精确匹配RTSP URL
            .first()
        )
    
    # 如果仍未找到，使用IP+通道匹配（向后兼容，但必须同时匹配通道）
    if not row and ip and channel:
        row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(
                and_(
                    or_(Task.ip == ip, Task.rtsp_url.ilike(f"%@{ip}%")),
                    or_(Task.channel == channel, Task.rtsp_url.ilike(f"%/{channel}/%"))
                )
            )
            .first()
        )
    
    # 如果仍未找到，返回None（避免通道混淆）
    if not row:
        print(f"[WARN] _get_task_id: 未找到匹配的任务 - RTSP: {segment.rtsp_url}, 时间: {segment.start_ts}-{segment.end_ts}, IP: {ip}, 通道: {channel}")
    
    return row.id if row else None


def _calculate_next_retry_time(start_ts: int, end_ts: int) -> datetime:
    """
    计算任务的下次重试时间
    规则：
    - 如果当前时间还在任务时间段内：等时间段结束后+1小时
    - 如果任务时间段已过：当前时间+1小时
    """
    try:
        from zoneinfo import ZoneInfo
        beijing_tz = ZoneInfo("Asia/Shanghai")
    except ImportError:
        beijing_tz = None
    
    # 获取当前北京时间
    if beijing_tz:
        beijing_now = datetime.now(beijing_tz)
        current_ts = int(beijing_now.timestamp())
    else:
        now = datetime.utcnow()
        beijing_now = datetime.fromtimestamp(now.timestamp() + 8 * 3600)
        current_ts = int(beijing_now.timestamp())
    
    # 判断当前时间与任务时间段的关系
    if current_ts < end_ts:
        # 当前时间还在任务时间段内：等时间段结束后+1小时
        next_retry_ts = end_ts + 3600  # end_ts + 1小时
    else:
        # 任务时间段已过：当前时间+1小时
        next_retry_ts = current_ts + 3600  # 当前时间 + 1小时
    
    # 转换为UTC时间返回（数据库存储UTC时间）
    # next_retry_ts 是北京时间戳，需要转换为UTC时间戳（减去8小时）
    next_retry_utc_ts = next_retry_ts - 8 * 3600
    next_retry_datetime = datetime.utcfromtimestamp(next_retry_utc_ts)
    
    return next_retry_datetime


def _update_task_db(db, segment: TaskSegment, date: str):
    """
    更新任务状态。使用日期、时间戳、IP和通道精确匹配任务，避免更新错误的任务。
    优先使用IP+通道匹配，确保不同IP的通道任务不会互相干扰。
    """
    from sqlalchemy import or_, and_
    
    channel_match = re.search(r"/(c\d+)/", segment.rtsp_url)
    channel = channel_match.group(1) if channel_match else None
    
    # 提取IP地址
    ip_match = re.search(r"@([\d.]+)(?::\d+)?", segment.rtsp_url)
    ip = ip_match.group(1) if ip_match else None
    
    # 优先使用IP+通道匹配（最精确）
    row = None
    if ip and channel:
        row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(
                or_(
                    and_(Task.ip == ip, Task.channel == channel),
                    and_(Task.ip.is_(None), Task.channel == channel, Task.rtsp_url.ilike(f"%@{ip}%")),
                    and_(Task.ip == ip, Task.channel.is_(None), Task.rtsp_url.ilike(f"%/{channel}/%")),
                )
            )
            .first()
        )
    
    # 如果未找到，使用通道匹配（向后兼容）
    if not row and channel:
        row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(Task.rtsp_url.ilike(f"%/{channel}/%"))
            .first()
        )
    
    # 如果仍未找到，使用RTSP URL精确匹配（必须包含通道信息）
    if not row and segment.rtsp_url:
        row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(Task.rtsp_url == segment.rtsp_url)  # 精确匹配RTSP URL
            .first()
        )
    
    # 如果仍未找到，使用IP+通道匹配（向后兼容，但必须同时匹配通道）
    if not row and ip and channel:
        row = (
            db.query(Task)
            .filter(Task.date == date)
            .filter(Task.start_ts == segment.start_ts, Task.end_ts == segment.end_ts)
            .filter(
                and_(
                    or_(Task.ip == ip, Task.rtsp_url.ilike(f"%@{ip}%")),
                    or_(Task.channel == channel, Task.rtsp_url.ilike(f"%/{channel}/%"))
                )
            )
            .first()
        )
    
    # 如果仍未找到，记录警告并返回（避免通道混淆）
    if not row:
        print(f"[WARN] _update_task_db: 未找到需要更新的任务记录，可能已被删除或通道不匹配。")
        print(f"[WARN] date={date}, start={segment.start_ts}, end={segment.end_ts}, RTSP={segment.rtsp_url}, IP={ip}, 通道={channel}")
        return

    row.status = segment.status
    row.screenshot_path = _to_rel(Path(segment.screenshot_path)) if segment.screenshot_path else None
    row.error = segment.error
    row.updated_at = datetime.utcnow()  # 更新操作时间
    
    # 如果任务失败且重试次数未达上限，计算下次重试时间
    if segment.status == "failed" and row.retry_count < 3:
        next_retry_at = _calculate_next_retry_time(row.start_ts, row.end_ts)
        row.next_retry_at = next_retry_at
        print(f"[INFO] 任务 {row.id} 失败，已设置下次重试时间: {next_retry_at} (当前重试次数: {row.retry_count})")
    
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        print(f"[WARN] 提交任务更新失败，记录已不存在，跳过。task_id={row.id}")


def _process_single_segment_wrapper(seg: TaskSegment, screenshot_dir: Path, crop_box: Optional[list[int]], date: str):
    """
    包装函数，为每个任务段创建独立的数据库会话并处理。
    用于并行执行任务。
    """
    with SessionLocal() as db:
        return _process_single_segment(deepcopy(seg), screenshot_dir, crop_box, db, date)


def _process_run(req: RunTaskRequest):
    key = _make_task_key(req.date, req.base_rtsp, req.channel)
    if key not in TASK_STORE:
        # 优先从数据库加载已存在的任务，如果没有则重新生成
        loaded = _load_tasks_to_store_from_db(req.date, req.base_rtsp, req.channel)
        if not loaded:
            ensure_tasks(
                TaskCreateRequest(
                    date=req.date,
                    base_rtsp=req.base_rtsp,
                    channel=req.channel,
                    interval_minutes=req.interval_minutes,
                )
            )

    # 再次校验流可用性（失败仅警告，不阻塞）
    first_url = TASK_STORE[key][0].rtsp_url
    ok, err = check_rtsp(first_url)
    if not ok:
        print(f"[WARN] RTSP check before run failed, continue run. detail={err[:300]}")

    # 在数据库层面将该组合的任务状态置为运行中，便于前端实时显示
    try:
        with SessionLocal() as db:
            prefix = f"{req.base_rtsp.rstrip('/')}/{req.channel}/%"
            updated = (
                db.query(Task)
                .filter(Task.date == req.date)
                .filter(Task.rtsp_url.like(prefix))
                .update(
                    {"status": "playing", "updated_at": datetime.utcnow()},
                    synchronize_session=False,
                )
            )
            db.commit()
            print(f"[INFO] 已标记运行中: {updated} 条任务，组合: {key}")
    except Exception as e:
        print(f"[WARN] 标记运行中失败: {e}")

    tasks = TASK_STORE[key]
    
    # 验证TASK_STORE中的RTSP URL是否正确（关键调试）
    print(f"[DEBUG] 验证TASK_STORE中的任务RTSP URL - 期望通道: {req.channel}")
    expected_channel_in_url = f"/{req.channel}/"
    invalid_count = 0
    for idx, task in enumerate(tasks[:5]):  # 只检查前5个作为示例
        if expected_channel_in_url not in task.rtsp_url:
            invalid_count += 1
            print(f"[ERROR] 任务段 {idx} RTSP URL通道不匹配！期望: {expected_channel_in_url}, 实际: {task.rtsp_url}")
        else:
            print(f"[DEBUG] 任务段 {idx} RTSP URL验证通过: {task.rtsp_url}")
    if invalid_count > 0:
        print(f"[WARN] 发现 {invalid_count} 个任务段的RTSP URL通道不匹配，这可能导致截图画面与任务通道不一致！")
    
    screenshot_base = Path(req.screenshot_dir)
    if not screenshot_base.is_absolute():
        screenshot_base = PROJECT_ROOT / screenshot_base
    screenshot_dir = screenshot_base / req.date
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    crop_box = req.crop_ocr_box

    print(f"[INFO] 开始并行处理 {len(tasks)} 个任务段")
    
    # 使用线程池并行执行任务
    # 为避免数据库连接池耗尽，限制单组合并发（支持通过环境变量 MAX_WORKERS_PER_COMBO 配置）
    max_workers = min(MAX_WORKERS_PER_COMBO, len(tasks))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务到线程池
        future_to_segment = {
            executor.submit(_process_single_segment_wrapper, seg, screenshot_dir, crop_box, req.date): idx
            for idx, seg in enumerate(tasks)
        }
        
        # 收集完成的任务结果
        completed_count = 0
        for future in as_completed(future_to_segment):
            idx = future_to_segment[future]
            try:
                updated_segment = future.result()
                tasks[idx] = updated_segment
                completed_count += 1
                print(f"[INFO] 任务进度: {completed_count}/{len(tasks)} ({completed_count*100//len(tasks)}%)")
            except Exception as e:
                print(f"[ERROR] 任务段 {idx} 处理失败: {e}")
                import traceback
                traceback.print_exc()
                # 标记任务为失败
                tasks[idx].status = "failed"
                tasks[idx].error = str(e)[:500]
                # 更新数据库中的失败任务，设置重试时间
                try:
                    with SessionLocal() as db:
                        # 提取IP地址用于精确匹配
                        base_rtsp_ip = None
                        if req.base_rtsp:
                            ip_match = re.search(r'@([\d.]+)(?::\d+)?', req.base_rtsp)
                            if ip_match:
                                base_rtsp_ip = ip_match.group(1)
                        
                        # 优先使用IP+通道匹配（最精确）
                        task = None
                        if base_rtsp_ip and req.channel:
                            from sqlalchemy import or_
                            task = db.query(Task).filter(
                                Task.date == req.date,
                                Task.start_ts == tasks[idx].start_ts,
                                Task.end_ts == tasks[idx].end_ts,
                                Task.channel == req.channel,
                                or_(Task.ip == base_rtsp_ip, Task.rtsp_url.ilike(f"%@{base_rtsp_ip}%"))
                            ).first()
                        
                        # 如果未找到，使用通道匹配
                        if not task and req.channel:
                            task = db.query(Task).filter(
                                Task.date == req.date,
                                Task.start_ts == tasks[idx].start_ts,
                                Task.end_ts == tasks[idx].end_ts,
                                Task.channel == req.channel
                            ).first()
                        if task and task.status == "failed" and task.retry_count < 3:
                            next_retry_at = _calculate_next_retry_time(task.start_ts, task.end_ts)
                            task.next_retry_at = next_retry_at
                            db.commit()
                            print(f"[INFO] 任务 {task.id} 失败，已设置下次重试时间: {next_retry_at} (当前重试次数: {task.retry_count})")
                except Exception as db_err:
                    print(f"[WARN] 更新任务重试时间失败: {db_err}")
    
    print(f"[INFO] 所有任务段处理完成，共 {completed_count}/{len(tasks)} 个成功")
    
    # 去重逻辑暂时关闭（如需开启，请恢复 deduplicate_directory 调用）


def _clear_date_data(db, date: str, base_rtsp: Optional[str] = None, channel: Optional[str] = None):
    """删除指定日期的任务及其关联截图、OCR结果，避免外键约束错误。
    如果提供了base_rtsp和channel，则只清理匹配的任务；否则清理所有同日期的任务。
    """
    print(f"[INFO] 开始清理任务数据 - 日期: {date}, RTSP: {base_rtsp}, 通道: {channel}")
    
    # 构建查询条件
    query = db.query(Task.id).filter(Task.date == date)
    
    # 如果提供了base_rtsp和channel，则精确匹配
    if base_rtsp and channel:
        ip_match = re.search(r'@([\d.]+)(?::\d+)?', base_rtsp)
        base_ip = ip_match.group(1) if ip_match else None
        # 构建匹配的RTSP URL前缀：base_rtsp/channel/
        # 例如：rtsp://admin:admin123=@192.168.54.227:554/c1/
        # 确保base_rtsp没有尾随斜杠（与build_rtsp_url函数保持一致）
        base_rtsp_clean = base_rtsp.rstrip("/")
        match_prefix = f"{base_rtsp_clean}/{channel}/"
        
        # 使用更精确的匹配：确保通道在正确的位置
        # RTSP URL格式：rtsp://admin:admin123=@192.168.54.227:554/c1/b1762099200/e1762185599/replay/s0
        # 我们需要匹配：base_rtsp/channel/ 这个前缀
        # 优先使用冗余字段匹配
        if base_ip:
            query = query.filter(Task.ip == base_ip, Task.channel == channel)
        else:
            query = query.filter(Task.rtsp_url.like(f"{match_prefix}%"))
        print(f"[INFO] 精确匹配清理 - 前缀: {match_prefix}")
        
        # 额外验证：确保不会匹配到其他通道
        # 例如：如果channel是c1，不应该匹配到c10、c11等
        # 通过确保匹配前缀后紧跟的是数字或b来避免误匹配
        # 但like已经足够精确了，因为/c1/和/c10/是不同的
    elif base_rtsp:
        # 只匹配base_rtsp（包含IP和端口）
        # 提取完整的base_rtsp部分进行匹配
        ip_match = re.search(r'@([\d.]+)(?::\d+)?', base_rtsp)
        base_ip = ip_match.group(1) if ip_match else None
        match_prefix = base_rtsp
        if base_ip:
            query = query.filter(Task.ip == base_ip)
        else:
            query = query.filter(Task.rtsp_url.like(f"{match_prefix}%"))
        print(f"[INFO] 匹配RTSP地址清理 - 前缀: {match_prefix}")
    elif channel:
        # 只匹配通道
        query = query.filter(Task.channel == channel)
        print(f"[INFO] 匹配通道清理 - 通道: {channel}")
    else:
        # 清理所有同日期任务
        print(f"[INFO] 清理所有同日期任务 - 日期: {date}")
    
    # 找出匹配的 task id
    task_id_rows = query.all()
    task_ids = [r.id for r in task_id_rows]
    
    # 验证：查询匹配的任务详情，用于验证
    if task_ids:
        matching_tasks = db.query(Task.id, Task.rtsp_url).filter(Task.id.in_(task_ids)).all()
        print(f"[INFO] 找到 {len(task_ids)} 个匹配的任务需要清理，RTSP URLs:")
        for task_id, rtsp_url in matching_tasks[:5]:  # 只打印前5个
            print(f"  - 任务ID {task_id}: {rtsp_url}")
        if len(matching_tasks) > 5:
            print(f"  ... 还有 {len(matching_tasks) - 5} 个任务")
        
        # 验证：检查是否有其他通道的任务被误匹配
        if base_rtsp and channel:
            base_rtsp_clean = base_rtsp.rstrip("/")
            expected_prefix = f"{base_rtsp_clean}/{channel}/"
            mismatched = []
            for task_id, rtsp_url in matching_tasks:
                if not rtsp_url.startswith(expected_prefix):
                    mismatched.append((task_id, rtsp_url))
            
            if mismatched:
                print(f"[ERROR] 警告：发现 {len(mismatched)} 个不匹配的任务被误匹配！")
                for task_id, rtsp_url in mismatched[:3]:
                    print(f"  任务ID {task_id}: {rtsp_url}")
                    print(f"  预期前缀: {expected_prefix}")
                # 从task_ids中移除不匹配的任务
                task_ids = [tid for tid in task_ids if tid not in [m[0] for m in mismatched]]
                print(f"[INFO] 已从清理列表中移除 {len(mismatched)} 个不匹配的任务，实际清理 {len(task_ids)} 个任务")
    
    if not task_ids:
        print(f"[INFO] 没有找到需要清理的任务")
        return
    
    # OCR功能已移除，不再删除OCR记录
    
    # 删除截图（数据库+磁盘）
    shot_rows = db.query(Screenshot.id, Screenshot.file_path).filter(Screenshot.task_id.in_(task_ids)).all()
    for _, fp in shot_rows:
        try:
            p = Path(fp)
            if not p.is_absolute():
                p = SCREENSHOT_BASE / p
            if p.exists():
                p.unlink()
        except Exception as e:
            print(f"[WARN] 删除截图文件失败: {fp}, err={e}")
    screenshot_count = len(shot_rows)
    db.query(Screenshot).filter(Screenshot.task_id.in_(task_ids)).delete(synchronize_session=False)
    print(f"[INFO] 已删除 {screenshot_count} 个截图记录（含磁盘文件）")
    
    # 删除任务
    task_count = db.query(Task).filter(Task.id.in_(task_ids)).count()
    db.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)
    print(f"[INFO] 已删除 {task_count} 个任务记录")
    
    db.commit()
    print(f"[INFO] 清理完成 - 共清理 {len(task_ids)} 个任务及其关联数据")


@app.post("/api/tasks/run")
def run_tasks(req: RunTaskRequest, background_tasks: BackgroundTasks):
    """
    创建并后台运行指定日期的任务（按10分钟切片：拉流→截图→去重→OCR）。
    """
    background_tasks.add_task(_process_run, req)
    return {"message": "任务已启动", "date": req.date}


@app.post("/api/tasks/run_all")
def run_all_tasks(req: RunAllRequest, background_tasks: BackgroundTasks):
    """
    后台并行运行同一日期下所有基础RTSP+通道组合的任务。
    如果 TASK_STORE 中没有对应组合，先从数据库加载（存在则直接运行），若不存在则重新生成。
    """
    date = req.date
    # 获取该日期下所有 distinct 的 (base_rtsp, channel)
    with SessionLocal() as db:
        rows = (
            db.query(Task.rtsp_url)
            .filter(Task.date == date)
            .distinct()
            .all()
        )
    combos = []
    for (rtsp_url,) in rows:
        channel_match = re.search(r"/(c\d+)/", rtsp_url)
        if channel_match:
            channel = channel_match.group(1)
            base_rtsp = rtsp_url.split(f"/{channel}/")[0]
            combos.append((base_rtsp, channel))

    # 去重
    combos = list({(b, c) for b, c in combos})

    started = 0
    for base_rtsp, channel in combos:
        run_req = RunTaskRequest(
            date=date,
            base_rtsp=base_rtsp,
            channel=channel,
            interval_minutes=req.interval_minutes,
        )
        background_tasks.add_task(_process_run, run_req)
        started += 1

    return {"message": f"已启动 {started} 个通道的任务", "date": date, "count": started}


# OCR API接口已移除


@app.get("/api/images")
def list_images_all(
    date: Optional[str] = None,
    screenshot_dir: str = "screenshots",
    # 向后兼容的旧参数
    rtsp_ip: Optional[str] = None,
    channel: Optional[str] = None,
    # 新的搜索参数（FastAPI会将URL中的双下划线转换为单下划线，所以函数参数名使用单下划线，alias指定URL中的参数名）
    name_eq: Optional[str] = Query(None, alias="name__eq"),  # 精准搜索图片名称
    name_like: Optional[str] = Query(None, alias="name__like"),  # 模糊搜索图片名称
    task_ip: Optional[str] = None,  # 精准搜索任务IP
    task_ip_like: Optional[str] = Query(None, alias="task_ip__like"),  # 模糊搜索任务IP
    task_channel: Optional[str] = None,  # 精准搜索任务通道
    task_channel_like: Optional[str] = Query(None, alias="task_channel__like"),  # 模糊搜索任务通道
    task_status: Optional[str] = None,  # 精准搜索任务状态
    task_status_in: Optional[str] = Query(None, alias="task_status__in", description="多选任务状态，逗号分隔"),  # 多选任务状态
    status_label: Optional[str] = None,  # 精准搜索状态标签
    status_label_in: Optional[str] = Query(None, alias="status_label__in", description="多选状态标签，逗号分隔"),  # 多选状态标签
    task_start_ts_gte: Optional[int] = Query(None, alias="task_start_ts__gte"),  # 任务开始时间戳 >=
    task_start_ts_lte: Optional[int] = Query(None, alias="task_start_ts__lte"),  # 任务开始时间戳 <=
    task_end_ts_gte: Optional[int] = Query(None, alias="task_end_ts__gte"),  # 任务结束时间戳 >=
    task_end_ts_lte: Optional[int] = Query(None, alias="task_end_ts__lte"),  # 任务结束时间戳 <=
    missing: Optional[bool] = None,  # 是否缺失（true/false）
):
    """
    使用统一的 ImageService.list_images 逻辑返回图片列表（包含 OCR 字段、状态标签等）。
    说明：这里和 app.routers.images 中的实现保持一致，只是为了兼容旧路径仍保留在 main.py。
    """
    with SessionLocal() as db:
        service = ImageService(db)
        return service.list_images(
            date=date,
            screenshot_dir=screenshot_dir,
            rtsp_ip=rtsp_ip,
            channel=channel,
            name_eq=name_eq,
            name_like=name_like,
            task_ip=task_ip,
            task_ip_like=task_ip_like,
            task_channel=task_channel,
            task_channel_like=task_channel_like,
            task_status=task_status,
            task_status_in=task_status_in,
            status_label=status_label,
            status_label_in=status_label_in,
            task_start_ts_gte=task_start_ts_gte,
            task_start_ts_lte=task_start_ts_lte,
            task_end_ts_gte=task_end_ts_gte,
            task_end_ts_lte=task_end_ts_lte,
            missing=missing,
        )


@app.get("/api/images/{date}")
def list_images(
    date: str,
    screenshot_dir: str = "screenshots",
    # 向后兼容的旧参数
    rtsp_ip: Optional[str] = None,
    channel: Optional[str] = None,
    # 新的搜索参数（FastAPI会将URL中的双下划线转换为单下划线，所以函数参数名使用单下划线，alias指定URL中的参数名）
    name_eq: Optional[str] = Query(None, alias="name__eq"),  # 精准搜索图片名称
    name_like: Optional[str] = Query(None, alias="name__like"),  # 模糊搜索图片名称
    task_ip: Optional[str] = None,  # 精准搜索任务IP
    task_ip_like: Optional[str] = Query(None, alias="task_ip__like"),  # 模糊搜索任务IP
    task_channel: Optional[str] = None,  # 精准搜索任务通道
    task_channel_like: Optional[str] = Query(None, alias="task_channel__like"),  # 模糊搜索任务通道
    task_status: Optional[str] = None,  # 精准搜索任务状态
    task_status_in: Optional[str] = Query(None, alias="task_status__in", description="多选任务状态，逗号分隔"),  # 多选任务状态
    status_label: Optional[str] = None,  # 精准搜索状态标签
    status_label_in: Optional[str] = Query(None, alias="status_label__in", description="多选状态标签，逗号分隔"),  # 多选状态标签
    task_start_ts_gte: Optional[int] = Query(None, alias="task_start_ts__gte"),  # 任务开始时间戳 >=
    task_start_ts_lte: Optional[int] = Query(None, alias="task_start_ts__lte"),  # 任务开始时间戳 <=
    task_end_ts_gte: Optional[int] = Query(None, alias="task_end_ts__gte"),  # 任务结束时间戳 >=
    task_end_ts_lte: Optional[int] = Query(None, alias="task_end_ts__lte"),  # 任务结束时间戳 <=
    missing: Optional[bool] = None,  # 是否缺失（true/false）
):
    """
    使用 ImageService.list_images，且通过路径参数指定日期。
    """
    with SessionLocal() as db:
        service = ImageService(db)
        return service.list_images(
            date=date,
            screenshot_dir=screenshot_dir,
            rtsp_ip=rtsp_ip,
            channel=channel,
            name_eq=name_eq,
            name_like=name_like,
            task_ip=task_ip,
            task_ip_like=task_ip_like,
            task_channel=task_channel,
            task_channel_like=task_channel_like,
            task_status=task_status,
            task_status_in=task_status_in,
            status_label=status_label,
            status_label_in=status_label_in,
            task_start_ts_gte=task_start_ts_gte,
            task_start_ts_lte=task_start_ts_lte,
            task_end_ts_gte=task_end_ts_gte,
            task_end_ts_lte=task_end_ts_lte,
            missing=missing,
        )


@app.get("/api/images/available_dates")
def list_image_dates(screenshot_dir: str = "screenshots"):
    """
    返回有截图数据的日期列表（优先数据库，有则提供数量；无则扫描文件夹）。
    使用 ImageService.get_available_dates 与 /app/routers/images.py 保持一致。
    """
    with SessionLocal() as db:
        service = ImageService(db)
        data = service.get_available_dates(screenshot_dir=screenshot_dir)
    return data


def _build_image_url(p: Path):
    """
    构造图片可访问 URL；如果文件缺失，标记 missing。
    """
    # 若是相对路径，先补全到截图根目录
    if not p.is_absolute():
        p = SCREENSHOT_BASE / p

    # 如果文件不存在且可能是相对路径，尝试再次拼接
    missing = not p.exists()
    try:
        abs_path = p.resolve()
        rel = abs_path.relative_to(SCREENSHOT_BASE)
        return f"/shots/{rel.as_posix()}", missing
    except Exception:
        # 不在截图目录下，走代理端点
        return f"/api/image_proxy?path={p.as_posix()}", missing


def _to_rel(p: Path) -> str:
    """
    将路径转为相对于 SCREENSHOT_BASE 的相对路径字符串；否则返回绝对路径字符串。
    """
    try:
        abs_path = p.resolve()
        rel = abs_path.relative_to(SCREENSHOT_BASE)
        return rel.as_posix()
    except Exception:
        return str(p)


@app.get("/api/image_proxy")
def image_proxy(path: str):
    """
    代理返回任意存在的图片文件（来源于数据库记录）。
    """
    p = Path(path)
    if not p.is_absolute():
        p = SCREENSHOT_BASE / p
    if not p.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(p)


@app.get("/api/hls/start")
def start_hls_proxy(rtsp_url: str):
    """
    On-demand RTSP -> HLS conversion; returns m3u8 URL.
    """
    ok, err = probe_rtsp(rtsp_url)
    if not ok:
        # 尝试继续启动，但返回警告信息（方便调试）
        print(f"[HLS][warn] RTSP probe failed, continue start. detail={err[:500]}")

    key = str(uuid.uuid4())
    out_dir = HLS_BASE / key
    proc = start_hls(rtsp_url, out_dir, stream_name="index")
    if not proc:
        detail = "FFmpeg启动失败或未安装"
        if err:
            detail += f"；probe: {err[:300]}"
        raise HTTPException(status_code=500, detail=detail)

    # 等待 m3u8 文件生成，超时则认为启动失败
    m3u8_path = out_dir / "index.m3u8"
    wait_time = 20  # seconds, 给转码/生成m3u8更多时间
    poll_interval = 0.5
    elapsed = 0.0
    while elapsed < wait_time:
        if m3u8_path.exists():
            break
        if proc.poll() is not None:
            # ffmpeg 已退出
            proc.terminate()
            raise HTTPException(status_code=500, detail="FFmpeg启动后异常退出，未生成m3u8")
        time.sleep(poll_interval)
        elapsed += poll_interval

    if not m3u8_path.exists():
        try:
            proc.terminate()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="未生成m3u8，请检查RTSP源或FFmpeg输出（可能需要更长时间或流无数据）")

    HLS_PROCS[key] = proc
    m3u8_url = f"/hls/{key}/index.m3u8"
    warn = None if ok else f"RTSP探测失败，已尝试直接启动：{err[:200]}"
    return {"m3u8": m3u8_url, "warn": warn}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# ==================== 自动分配配置 API ====================

@app.get("/api/auto-schedule/rules")
def list_auto_rules():
    """获取所有自动分配规则"""
    with SessionLocal() as db:
        rules = db.query(AutoScheduleRule).order_by(AutoScheduleRule.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "use_today": r.use_today,
                "custom_date": r.custom_date,
                "base_rtsp": r.base_rtsp,
                "channel": r.channel,
                "interval_minutes": r.interval_minutes,
                "trigger_time": r.trigger_time,
                "is_enabled": r.is_enabled,
                "last_executed_at": (r.last_executed_at.isoformat() + "Z" if r.last_executed_at.tzinfo is None else r.last_executed_at.isoformat()) if r.last_executed_at else None,
                "execution_count": r.execution_count,
                "last_execution_status": r.last_execution_status,
                "last_execution_error": r.last_execution_error,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rules
        ]


@app.post("/api/auto-schedule/rules")
def create_auto_rule(rule_data: AutoScheduleRuleCreate):
    """创建自动分配规则"""
    # 验证日期选择
    if not rule_data.use_today and not rule_data.custom_date:
        raise HTTPException(status_code=400, detail="必须选择日期或勾选自动获取当日时间")
    
    if rule_data.use_today and rule_data.custom_date:
        raise HTTPException(status_code=400, detail="勾选自动获取当日时间后不能填写自定义日期")
    
    # 验证触发时间格式
    try:
        hour, minute = map(int, rule_data.trigger_time.split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
    except:
        raise HTTPException(status_code=400, detail="触发时间格式错误，应为HH:mm格式")
    
    # 验证RTSP地址格式
    if not rule_data.base_rtsp.startswith("rtsp://"):
        raise HTTPException(status_code=400, detail="RTSP地址格式错误，应以rtsp://开头")
    
    # 验证通道格式
    if not re.match(r"^c[1-9]\d*$", rule_data.channel.lower()):
        raise HTTPException(status_code=400, detail="通道格式错误，应为c1、c2、c3等格式")
    
    # 验证间隔分钟数
    if rule_data.interval_minutes <= 0 or rule_data.interval_minutes > 1440:
        raise HTTPException(status_code=400, detail="间隔分钟数应在1-1440之间")
    
    # 自动生成规则名称（如果未提供）
    rule_name = rule_data.name
    if not rule_name:
        # 从RTSP地址提取IP
        ip_match = re.search(r"@([\d.]+)(?::\d+)?", rule_data.base_rtsp)
        ip = ip_match.group(1) if ip_match else "unknown"
        rule_name = f"{ip}_{rule_data.channel}_{rule_data.trigger_time}"
    
    with SessionLocal() as db:
        rule = AutoScheduleRule(
            name=rule_name,
            use_today=rule_data.use_today,
            custom_date=rule_data.custom_date if not rule_data.use_today else None,
            base_rtsp=rule_data.base_rtsp,
            channel=rule_data.channel,
            interval_minutes=rule_data.interval_minutes,
            trigger_time=rule_data.trigger_time,
            is_enabled=True,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return {
            "id": rule.id,
            "message": "规则保存成功",
        }


@app.patch("/api/auto-schedule/rules/{rule_id}")
def update_auto_rule(rule_id: int, rule_data: AutoScheduleRuleUpdate):
    """更新规则启用状态"""
    with SessionLocal() as db:
        rule = db.query(AutoScheduleRule).filter(AutoScheduleRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")
        rule.is_enabled = rule_data.is_enabled
        rule.updated_at = datetime.utcnow()
        db.commit()
        return {"message": "规则更新成功"}


@app.delete("/api/auto-schedule/rules/{rule_id}")
def delete_auto_rule(rule_id: int):
    """删除自动分配规则"""
    with SessionLocal() as db:
        rule = db.query(AutoScheduleRule).filter(AutoScheduleRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")
        db.delete(rule)
        db.commit()
        return {"message": "规则删除成功"}


def execute_auto_rule(rule_id: int):
    """执行自动分配规则"""
    with SessionLocal() as db:
        rule = db.query(AutoScheduleRule).filter(AutoScheduleRule.id == rule_id).first()
        if not rule:
            print(f"[ERROR] 规则 {rule_id} 不存在")
            return
        
        print(f"[INFO] 开始执行自动规则 - ID: {rule.id}, RTSP: {rule.base_rtsp}, 通道: {rule.channel}")
        
        # 确定日期
        try:
            from zoneinfo import ZoneInfo
            beijing_tz = ZoneInfo("Asia/Shanghai")
        except ImportError:
            beijing_tz = None
        
        if rule.use_today:
            # 获取当前北京时间
            if beijing_tz:
                beijing_now = datetime.now(beijing_tz)
            else:
                now = datetime.utcnow()
                beijing_now = datetime.fromtimestamp(now.timestamp() + 8 * 3600)
            date = beijing_now.strftime("%Y-%m-%d")
        else:
            date = rule.custom_date
        
        if not date:
            error_msg = f"规则 {rule.id} 无法确定日期"
            print(f"[ERROR] {error_msg}")
            # 更新执行记录
            rule.last_executed_at = datetime.utcnow()
            rule.execution_count += 1
            rule.last_execution_status = "failed"
            rule.last_execution_error = error_msg
            db.commit()
            return
        
        print(f"[INFO] 规则 {rule.id} 使用日期: {date}")
        
        # 在开始执行时立即更新状态为"执行中"
        rule.last_executed_at = datetime.utcnow()
        rule.execution_count += 1
        rule.last_execution_status = "running"  # 执行中
        rule.last_execution_error = None
        db.commit()
        print(f"[INFO] 规则 {rule.id} 开始执行，状态已更新为执行中")
        
        try:
            # 生成任务
            req = TaskCreateRequest(
                date=date,
                base_rtsp=rule.base_rtsp,
                channel=rule.channel,
                interval_minutes=rule.interval_minutes,
            )
            ensure_tasks(req)
            
            # 运行任务
            run_req = RunTaskRequest(
                date=date,
                base_rtsp=rule.base_rtsp,
                channel=rule.channel,
                interval_minutes=rule.interval_minutes,
            )
            _process_run(run_req)
            
            # 更新执行记录（成功）- 只更新状态，不增加执行次数
            rule.last_executed_at = datetime.utcnow()
            rule.last_execution_status = "success"
            rule.last_execution_error = None
            db.commit()
            
            print(f"[INFO] 规则 {rule.id} 执行完成")
        except Exception as e:
            error_msg = str(e)[:500]  # 限制错误信息长度
            print(f"[ERROR] 规则 {rule.id} 执行失败: {error_msg}")
            import traceback
            traceback.print_exc()
            
            # 更新执行记录（失败）- 只更新状态，不增加执行次数（已在开始时增加）
            rule.last_executed_at = datetime.utcnow()
            rule.last_execution_status = "failed"
            rule.last_execution_error = error_msg
            db.commit()


def check_and_execute_rules():
    """检查并执行到期的规则"""
    try:
        try:
            from zoneinfo import ZoneInfo
            beijing_tz = ZoneInfo("Asia/Shanghai")
        except ImportError:
            # Python < 3.9 回退方案
            beijing_tz = None
        
        if beijing_tz:
            # 使用标准时区库
            beijing_now = datetime.now(beijing_tz)
        else:
            # 回退方案：手动计算UTC+8
            now = datetime.utcnow()
            beijing_now = datetime.fromtimestamp(now.timestamp() + 8 * 3600)
        
        current_time = beijing_now.strftime("%H:%M")
        current_date = beijing_now.strftime("%Y-%m-%d")
        
        with SessionLocal() as db:
            rules = db.query(AutoScheduleRule).filter(
                AutoScheduleRule.is_enabled == True
            ).all()
            
            for rule in rules:
                if rule.trigger_time == current_time:
                    # 检查是否今天已经执行过（防止重复执行）
                    if rule.last_executed_at:
                        last_executed_date = rule.last_executed_at.strftime("%Y-%m-%d")
                        if last_executed_date == current_date:
                            # 今天已执行过，跳过
                            continue
                    
                    print(f"[INFO] 触发规则 {rule.id} - 触发时间: {rule.trigger_time}, 日期: {current_date}")
                    # 在后台执行规则
                    thread = threading.Thread(target=execute_auto_rule, args=(rule.id,))
                    thread.daemon = True
                    thread.start()
    except Exception as e:
        print(f"[ERROR] 检查规则时发生错误: {e}")
        import traceback
        traceback.print_exc()


def check_and_retry_failed_tasks():
    """检查并自动重试失败的任务（每小时执行一次）"""
    try:
        try:
            from zoneinfo import ZoneInfo
            beijing_tz = ZoneInfo("Asia/Shanghai")
        except ImportError:
            beijing_tz = None
        
        # 获取当前UTC时间
        current_utc = datetime.utcnow()
        
        with SessionLocal() as db:
            # 查找需要重试的任务：
            # 1. 状态为 failed
            # 2. 重试次数 < 3
            # 3. (next_retry_at 不为空且 <= 当前时间) 或 (next_retry_at 为空，需要初始化)
            from sqlalchemy import or_
            
            # 查询条件1：next_retry_at已设置且已到时间的任务
            tasks_with_retry_time = (
                db.query(Task)
                .filter(Task.status == "failed")
                .filter(Task.retry_count < 3)
                .filter(Task.next_retry_at.isnot(None))
                .filter(Task.next_retry_at <= current_utc)
                .all()
            )
            
            # 查询条件2：next_retry_at为NULL的失败任务（可能是之前设置失败导致的）
            tasks_without_retry_time = (
                db.query(Task)
                .filter(Task.status == "failed")
                .filter(Task.retry_count < 3)
                .filter(Task.next_retry_at.is_(None))
                .all()
            )
            
            # 合并任务列表
            tasks_to_retry = list(tasks_with_retry_time) + list(tasks_without_retry_time)
            
            if not tasks_to_retry:
                return
            
            print(f"[INFO] 发现 {len(tasks_to_retry)} 个失败任务需要自动重试（其中 {len(tasks_without_retry_time)} 个需要初始化重试时间）")
            
            for task in tasks_to_retry:
                try:
                    # 如果next_retry_at为NULL，先设置它（使用当前时间+1小时）
                    if task.next_retry_at is None:
                        next_retry_at = _calculate_next_retry_time(task.start_ts, task.end_ts)
                        task.next_retry_at = next_retry_at
                        print(f"[INFO] 任务 {task.id} 的next_retry_at为NULL，已初始化为: {next_retry_at}")
                    
                    # 检查是否到了重试时间
                    if task.next_retry_at > current_utc:
                        print(f"[INFO] 任务 {task.id} 还未到重试时间，跳过（next_retry_at: {task.next_retry_at}）")
                        db.commit()
                        continue
                    
                    # 增加重试次数
                    task.retry_count += 1
                    task.next_retry_at = None  # 清空重试时间，重试后重新计算
                    task.status = "playing"  # 设置为运行中
                    task.updated_at = datetime.utcnow()
                    db.commit()
                    
                    print(f"[INFO] 开始自动重试任务 {task.id} (第 {task.retry_count} 次重试)")
                    
                    # 在后台线程中执行重试
                    thread = threading.Thread(target=_retry_failed_task, args=(task.id,))
                    thread.daemon = True
                    thread.start()
                    
                except Exception as e:
                    print(f"[ERROR] 重试任务 {task.id} 时发生错误: {e}")
                    import traceback
                    traceback.print_exc()
                    db.rollback()
                    
    except Exception as e:
        print(f"[ERROR] 检查失败任务重试时发生错误: {e}")
        import traceback
        traceback.print_exc()


def _retry_failed_task(task_id: int):
    """重试单个失败的任务"""
    try:
        # 重新运行任务（_rerun_single_task 内部会处理状态更新和重试时间）
        _rerun_single_task(task_id)
        
        # 检查重试后的最终状态
        with SessionLocal() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                print(f"[ERROR] 任务 {task_id} 不存在")
                return
            
            if task.status == "completed":
                # 重试成功，清空重试时间
                task.next_retry_at = None
                db.commit()
                print(f"[INFO] 任务 {task_id} 重试成功！")
            elif task.status == "failed" and task.retry_count >= 3:
                # 达到最大重试次数，清空重试时间，停止自动重试
                task.next_retry_at = None
                db.commit()
                print(f"[WARN] 任务 {task_id} 已达到最大重试次数(3次)，停止自动重试")
            # 如果重试失败但未达上限，_rerun_single_task 中已经设置了下次重试时间
                
    except Exception as e:
        print(f"[ERROR] 重试任务 {task_id} 时发生错误: {e}")
        import traceback
        traceback.print_exc()


def check_and_fill_missing_minute_screenshots() -> int:
    """
    自动补齐缺失的每分钟截图：查找「主任务已完成、批次允许、但存在缺失分钟截图」的任务，
    对其触发 _generate_all_minute_screenshots（内部会跳过已完成的分钟）。
    每轮最多处理 FILL_LIMIT 个任务，避免单次负载过大。
    先对仍为 pending/running 的批次尝试更新为已完成（修复历史未更新的批次），再查候选任务。
    """
    FILL_LIMIT = 50  # 每轮处理更多任务，加快补齐速度
    CANDIDATE_LIMIT = 200  # 扩大候选范围，确保不漏掉任务
    filled = 0
    with SessionLocal() as db:
        # 先修复：把所有「仍为 pending/running 但实际已全部结束」的批次更新为 completed/failed/partial_failed，
        # 否则下面查询会排除这些任务，导致从不触发生成每分钟截图
        pending_batches = (
            db.query(TaskBatch.id)
            .filter(TaskBatch.status.in_(["pending", "running"]))
            .all()
        )
        for (batch_id,) in pending_batches:
            _update_batch_status_if_done(db, batch_id)

        # 主任务已完成的都纳入候选；优先补齐最近一天（按 date 降序、再按 id 升序）
        candidates = (
            db.query(Task)
            .filter(Task.status == "completed")
            .order_by(Task.date.desc(), Task.id.asc())
            .limit(CANDIDATE_LIMIT)
            .all()
        )
        need_fill = []
        for task in candidates:
            total_minutes = int((task.end_ts - task.start_ts + 59) / 60)
            if total_minutes <= 0:
                continue
            completed_count = db.query(MinuteScreenshot).filter(
                MinuteScreenshot.task_id == task.id,
                MinuteScreenshot.status == "completed",
            ).count()
            if completed_count < total_minutes:
                need_fill.append(task)
        for task in need_fill[:FILL_LIMIT]:
            try:
                _submit_all_minute_screenshots(
                    task.id,
                    task.start_ts,
                    task.end_ts,
                    task.rtsp_url,
                    task.date,
                    task.ip,
                    task.channel,
                )
                filled += 1
            except Exception as e:
                print(f"[ERROR] 启动补齐每分钟截图失败 task_id={task.id}: {e}")
    if filled > 0:
        print(f"[INFO] 自动补齐每分钟截图：已为 {filled} 个任务触发生成")
    else:
        # 便于确认定时任务在运行（无补齐时也打一条，降低频率避免刷屏）
        if len(need_fill) == 0 and len(candidates) > 0:
            print(f"[INFO] 自动补齐检查: 候选 {len(candidates)} 个任务，无需补齐")
    return filled


# 启动定时任务检查器
def start_schedule_checker():
    """启动定时任务检查器，每分钟检查一次"""
    import threading
    import time
    
    def checker_loop():
        while True:
            try:
                check_and_execute_rules()
            except Exception as e:
                print(f"[ERROR] 定时任务检查器错误: {e}")
            time.sleep(60)  # 每分钟检查一次
    
    thread = threading.Thread(target=checker_loop)
    thread.daemon = True
    thread.start()


# 启动失败任务自动重试检查器
def start_failed_task_retry_checker():
    """启动失败任务自动重试检查器，每小时检查一次"""
    import threading
    import time
    
    def retry_checker_loop():
        while True:
            try:
                check_and_retry_failed_tasks()
            except Exception as e:
                print(f"[ERROR] 失败任务重试检查器错误: {e}")
            time.sleep(3600)  # 每小时检查一次（3600秒）
    
    thread = threading.Thread(target=retry_checker_loop)
    thread.daemon = True
    thread.start()


# 启动每分钟截图自动补齐检查器
def start_minute_screenshot_fill_checker():
    """启动每分钟截图自动补齐检查器，每 5 分钟检查一次并补齐缺失的每分钟截图"""
    import threading
    import time

    def fill_loop():
        # 启动时立即运行一次，不等待，确保用户打开弹窗前截图已自动生成
        try:
            check_and_fill_missing_minute_screenshots()
        except Exception as e:
            print(f"[ERROR] 每分钟截图自动补齐检查器首次运行错误: {e}")
        while True:
            try:
                check_and_fill_missing_minute_screenshots()
            except Exception as e:
                print(f"[ERROR] 每分钟截图自动补齐检查器错误: {e}")
            time.sleep(120)  # 每 2 分钟检查一次，加快补齐速度

    thread = threading.Thread(target=fill_loop)
    thread.daemon = True
    thread.start()


# 启动车位变化检测后台任务
def start_parking_change_detector():
    """启动车位变化检测后台任务，定期扫描待处理的截图并执行 YOLO 检测"""
    import threading
    import time
    from pathlib import Path
    from sqlalchemy import desc
    
    def detector_loop():
        # 延迟导入，确保模型已预加载
        time.sleep(3)  # 等待模型预加载完成
        
        try:
            # 直接在这里导入，避免循环依赖
            from app.background.parking_change_worker import process_pending_screenshots
        except ImportError as e:
            print(f"[WARN] 无法导入车位变化检测模块: {e}")
            print("[WARN] 车位变化检测功能将不可用")
            return
        
        print("[ParkingChangeDetector] 车位变化检测后台任务已启动，开始轮询待处理的截图...")
        
        while True:
            try:
                # 每轮先将一批历史未检测的截图标记为 pending，再处理待检测截图（自动补齐车位变化识别）
                try:
                    from app.services.utils_service import UtilsService
                    UtilsService().mark_screenshots_pending_for_parking_change(limit=50)
                except Exception as e:
                    print(f"[WARN] 车位变化补齐标记失败: {e}")
                count = process_pending_screenshots(batch_size=10)
                if count > 0:
                    print(f"[ParkingChangeDetector] 本次处理了 {count} 张截图的车位变化检测")
            except Exception as e:
                print(f"[ERROR] 车位变化检测任务错误: {e}")
                import traceback
                traceback.print_exc()
            time.sleep(5)  # 每5秒检查一次
    
    thread = threading.Thread(target=detector_loop)
    thread.daemon = True
    thread.start()


@app.get("/", include_in_schema=False)
def index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "static page not found"}


# ==================== NVR配置 API ====================


def build_base_rtsp_from_nvr(config: NvrConfig) -> str:
    """
    根据 NvrConfig 构造 RTSP 基础地址。
    注意：不要对用户名/密码做 URL 编码，保持与前端参数设置中使用的格式完全一致。
    """
    username = config.nvr_username or ""
    password = config.nvr_password or ""
    ip = config.nvr_ip or ""
    port = config.nvr_port or 554
    return f"rtsp://{username}:{password}@{ip}:{port}"


def build_channel_view(nvr: NvrConfig, ch: ChannelConfig) -> ChannelView:
    """将 NvrConfig + ChannelConfig 组合为通道统一视图对象"""
    return ChannelView(
        id=ch.id,
        nvr_id=nvr.id,
        nvr_ip=nvr.nvr_ip,
        parking_name=nvr.parking_name,
        base_rtsp=build_base_rtsp_from_nvr(nvr),
        channel_code=ch.channel_code,
        camera_ip=ch.camera_ip,
        camera_name=ch.camera_name,
        camera_sn=ch.camera_sn,
    )


@app.get("/api/channels", response_model=list[ChannelView])
def list_channels(nvr_id: int | None = None, base_rtsp: str | None = None):
    """
    获取通道统一视图列表。

    - 可选按 nvr_id 过滤
    - 可选按 base_rtsp 过滤（与前端参数设置中显示的 RTSP 基础地址完全一致）
    """
    with SessionLocal() as db:
        query = db.query(NvrConfig).order_by(NvrConfig.id.asc())
        if nvr_id is not None:
            query = query.filter(NvrConfig.id == nvr_id)

        nvrs = query.all()
        result: list[ChannelView] = []

        # 如果按 base_rtsp 过滤，则仅保留与该 base_rtsp 精确匹配的 NVR
        if base_rtsp:
            filtered_nvrs = []
            for nvr in nvrs:
                if build_base_rtsp_from_nvr(nvr) == base_rtsp:
                    filtered_nvrs.append(nvr)
            nvrs = filtered_nvrs

        for nvr in nvrs:
            for ch in nvr.channels:
                result.append(build_channel_view(nvr, ch))

        return result


@app.get("/api/channels/by-base-rtsp", response_model=list[ChannelView])
def list_channels_by_base_rtsp(base_rtsp: str = Query(..., description="RTSP 基础地址")):
    """
    根据 RTSP 基础地址获取对应 NVR 下的所有通道。

    该接口主要用于：
    - 基础参数配置 Tab 的通道选择
    - 自动分配配置 Tab 的通道选择
    """
    return list_channels(base_rtsp=base_rtsp)


@app.get("/api/nvr-configs")
def list_nvr_configs():
    """获取所有NVR配置"""
    with SessionLocal() as db:
        configs = db.query(NvrConfig).order_by(NvrConfig.created_at.desc()).all()
        result = []
        for config in configs:
            channels = []
            for ch in config.channels:
                parking_spaces = convert_parking_spaces_to_response(ch.parking_spaces_rel) if ch.parking_spaces_rel else None
                channels.append(ChannelConfigResponse(
                    id=ch.id,
                    nvr_config_id=ch.nvr_config_id,
                    channel_code=ch.channel_code,
                    camera_ip=ch.camera_ip,
                    camera_name=ch.camera_name,
                    camera_sn=ch.camera_sn,
                    track_space=ch.track_space,
                    parking_spaces=parking_spaces,
                    created_at=ch.created_at.isoformat() if ch.created_at else None,
                    updated_at=ch.updated_at.isoformat() if ch.updated_at else None,
                ))
            result.append(NvrConfigResponse(
                id=config.id,
                nvr_ip=config.nvr_ip,
                parking_name=config.parking_name,
                nvr_username=config.nvr_username,
                nvr_password=config.nvr_password,
                nvr_port=config.nvr_port,
                db_host=config.db_host,
                db_user=config.db_user,
                db_password=config.db_password,
                db_port=config.db_port,
                db_name=config.db_name,
                channels=channels,
                created_at=config.created_at.isoformat() if config.created_at else None,
                updated_at=config.updated_at.isoformat() if config.updated_at else None,
            ))
        return result


@app.get("/api/nvr-configs/{config_id}", response_model=NvrConfigResponse)
def get_nvr_config(config_id: int):
    """获取单个NVR配置"""
    with SessionLocal() as db:
        config = db.query(NvrConfig).filter(NvrConfig.id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="NVR配置不存在")
        
        channels = []
        for ch in config.channels:
            parking_spaces = convert_parking_spaces_to_response(ch.parking_spaces_rel) if ch.parking_spaces_rel else None
            channels.append(ChannelConfigResponse(
                id=ch.id,
                nvr_config_id=ch.nvr_config_id,
                channel_code=ch.channel_code,
                camera_ip=ch.camera_ip,
                camera_name=ch.camera_name,
                camera_sn=ch.camera_sn,
                track_space=ch.track_space,
                parking_spaces=parking_spaces,
                created_at=ch.created_at.isoformat() if ch.created_at else None,
                updated_at=ch.updated_at.isoformat() if ch.updated_at else None,
            ))
        
        return NvrConfigResponse(
            id=config.id,
            nvr_ip=config.nvr_ip,
            parking_name=config.parking_name,
            nvr_username=config.nvr_username,
            nvr_password=config.nvr_password,
            nvr_port=config.nvr_port,
            db_host=config.db_host,
            db_user=config.db_user,
            db_password=config.db_password,
            db_port=config.db_port,
            db_name=config.db_name,
            channels=channels,
            created_at=config.created_at.isoformat() if config.created_at else None,
            updated_at=config.updated_at.isoformat() if config.updated_at else None,
        )


def convert_parking_spaces_to_response(parking_spaces_db: list) -> list:
    """将数据库中的ParkingSpace记录转换为ParkingSpaceInfo列表"""
    from schemas.nvr_config import ParkingSpaceInfo
    result = []
    for ps in parking_spaces_db:
        result.append(ParkingSpaceInfo(
            space_id=str(ps.id),
            space_name=ps.space_name,
            bbox=[ps.bbox_x1, ps.bbox_y1, ps.bbox_x2, ps.bbox_y2]
        ))
    return result


def save_parking_spaces_to_db(db, channel_id: int, parking_spaces_info: list):
    """将ParkingSpaceInfo列表保存到数据库"""
    if not parking_spaces_info:
        return
    
    for ps_info in parking_spaces_info:
        if len(ps_info.bbox) != 4:
            continue  # 跳过无效的bbox
        parking_space = ParkingSpace(
            channel_config_id=channel_id,
            space_name=ps_info.space_name,
            bbox_x1=ps_info.bbox[0],
            bbox_y1=ps_info.bbox[1],
            bbox_x2=ps_info.bbox[2],
            bbox_y2=ps_info.bbox[3],
        )
        db.add(parking_space)


@app.post("/api/nvr-configs", response_model=NvrConfigResponse)
def create_nvr_config(config_data: NvrConfigCreate):
    """创建NVR配置"""
    import json
    with SessionLocal() as db:
        # 检查IP是否已存在
        existing = db.query(NvrConfig).filter(NvrConfig.nvr_ip == config_data.nvr_ip).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"NVR IP {config_data.nvr_ip} 已存在")
        
        # 创建NVR配置
        nvr_config = NvrConfig(
            nvr_ip=config_data.nvr_ip,
            parking_name=config_data.parking_name,
            nvr_username=config_data.nvr_username,
            nvr_password=config_data.nvr_password,
            nvr_port=config_data.nvr_port,
            db_host=config_data.db_host,
            db_user=config_data.db_user,
            db_password=config_data.db_password,
            db_port=config_data.db_port,
            db_name=config_data.db_name,
        )
        db.add(nvr_config)
        db.commit()
        db.refresh(nvr_config)
        
        # 创建通道配置
        if config_data.channels:
            for ch_data in config_data.channels:
                channel = ChannelConfig(
                    nvr_config_id=nvr_config.id,
                    channel_code=ch_data.channel_code,
                    camera_ip=ch_data.camera_ip,
                    camera_name=ch_data.camera_name,
                    camera_sn=ch_data.camera_sn,
                    track_space=ch_data.track_space,
                )
                db.add(channel)
                db.flush()  # 获取channel.id
                
                # 保存车位信息到关联表
                if ch_data.parking_spaces:
                    save_parking_spaces_to_db(db, channel.id, ch_data.parking_spaces)
        
        db.commit()
        db.refresh(nvr_config)
        
        # 返回完整配置
        channels = []
        for ch in nvr_config.channels:
            parking_spaces = convert_parking_spaces_to_response(ch.parking_spaces_rel) if ch.parking_spaces_rel else None
            channels.append(ChannelConfigResponse(
                id=ch.id,
                nvr_config_id=ch.nvr_config_id,
                channel_code=ch.channel_code,
                camera_ip=ch.camera_ip,
                camera_name=ch.camera_name,
                camera_sn=ch.camera_sn,
                track_space=ch.track_space,
                parking_spaces=parking_spaces,
                created_at=ch.created_at.isoformat() if ch.created_at else None,
                updated_at=ch.updated_at.isoformat() if ch.updated_at else None,
            ))
        
        return NvrConfigResponse(
            id=nvr_config.id,
            nvr_ip=nvr_config.nvr_ip,
            parking_name=nvr_config.parking_name,
            nvr_username=nvr_config.nvr_username,
            nvr_password=nvr_config.nvr_password,
            nvr_port=nvr_config.nvr_port,
            db_host=nvr_config.db_host,
            db_user=nvr_config.db_user,
            db_password=nvr_config.db_password,
            db_port=nvr_config.db_port,
            db_name=nvr_config.db_name,
            channels=channels,
            created_at=nvr_config.created_at.isoformat() if nvr_config.created_at else None,
            updated_at=nvr_config.updated_at.isoformat() if nvr_config.updated_at else None,
        )


@app.put("/api/nvr-configs/{config_id}", response_model=NvrConfigResponse)
def update_nvr_config(config_id: int, config_data: NvrConfigUpdate):
    """更新NVR配置"""
    with SessionLocal() as db:
        config = db.query(NvrConfig).filter(NvrConfig.id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="NVR配置不存在")
        
        # 更新字段
        if config_data.parking_name is not None:
            config.parking_name = config_data.parking_name
        if config_data.nvr_username is not None:
            config.nvr_username = config_data.nvr_username
        if config_data.nvr_password is not None:
            config.nvr_password = config_data.nvr_password
        if config_data.nvr_port is not None:
            config.nvr_port = config_data.nvr_port
        if config_data.db_host is not None:
            config.db_host = config_data.db_host
        if config_data.db_user is not None:
            config.db_user = config_data.db_user
        if config_data.db_password is not None:
            config.db_password = config_data.db_password
        if config_data.db_port is not None:
            config.db_port = config_data.db_port
        if config_data.db_name is not None:
            config.db_name = config_data.db_name
        
        config.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(config)
        
        # 返回完整配置
        channels = []
        for ch in config.channels:
            parking_spaces = convert_parking_spaces_to_response(ch.parking_spaces_rel) if ch.parking_spaces_rel else None
            channels.append(ChannelConfigResponse(
                id=ch.id,
                nvr_config_id=ch.nvr_config_id,
                channel_code=ch.channel_code,
                camera_ip=ch.camera_ip,
                camera_name=ch.camera_name,
                camera_sn=ch.camera_sn,
                track_space=ch.track_space,
                parking_spaces=parking_spaces,
                created_at=ch.created_at.isoformat() if ch.created_at else None,
                updated_at=ch.updated_at.isoformat() if ch.updated_at else None,
            ))
        
        return NvrConfigResponse(
            id=config.id,
            nvr_ip=config.nvr_ip,
            parking_name=config.parking_name,
            nvr_username=config.nvr_username,
            nvr_password=config.nvr_password,
            nvr_port=config.nvr_port,
            db_host=config.db_host,
            db_user=config.db_user,
            db_password=config.db_password,
            db_port=config.db_port,
            db_name=config.db_name,
            channels=channels,
            created_at=config.created_at.isoformat() if config.created_at else None,
            updated_at=config.updated_at.isoformat() if config.updated_at else None,
        )


@app.delete("/api/nvr-configs/{config_id}")
def delete_nvr_config(config_id: int):
    """删除NVR配置"""
    with SessionLocal() as db:
        config = db.query(NvrConfig).filter(NvrConfig.id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="NVR配置不存在")
        
        db.delete(config)
        db.commit()
        return {"message": "NVR配置已删除"}


@app.post("/api/nvr-configs/{config_id}/channels", response_model=ChannelConfigResponse)
def create_channel_config(config_id: int, channel_data: ChannelConfigCreate):
    """为NVR配置添加通道"""
    with SessionLocal() as db:
        nvr_config = db.query(NvrConfig).filter(NvrConfig.id == config_id).first()
        if not nvr_config:
            raise HTTPException(status_code=404, detail="NVR配置不存在")
        
        channel = ChannelConfig(
            nvr_config_id=config_id,
            channel_code=channel_data.channel_code,
            camera_ip=channel_data.camera_ip,
            camera_name=channel_data.camera_name,
            camera_sn=channel_data.camera_sn,
            track_space=channel_data.track_space,
        )
        db.add(channel)
        db.flush()  # 获取channel.id
        
        # 保存车位信息到关联表
        if channel_data.parking_spaces:
            save_parking_spaces_to_db(db, channel.id, channel_data.parking_spaces)
        
        db.commit()
        db.refresh(channel)
        
        parking_spaces = convert_parking_spaces_to_response(channel.parking_spaces_rel) if channel.parking_spaces_rel else None
        
        return ChannelConfigResponse(
            id=channel.id,
            nvr_config_id=channel.nvr_config_id,
            channel_code=channel.channel_code,
            camera_ip=channel.camera_ip,
            camera_name=channel.camera_name,
            camera_sn=channel.camera_sn,
            track_space=channel.track_space,
            parking_spaces=parking_spaces,
            created_at=channel.created_at.isoformat() if channel.created_at else None,
            updated_at=channel.updated_at.isoformat() if channel.updated_at else None,
        )


@app.put("/api/nvr-configs/{config_id}/channels/{channel_id}", response_model=ChannelConfigResponse)
def update_channel_config(config_id: int, channel_id: int, channel_data: ChannelConfigUpdate):
    """更新通道配置"""
    import json
    with SessionLocal() as db:
        channel = db.query(ChannelConfig).filter(
            ChannelConfig.id == channel_id,
            ChannelConfig.nvr_config_id == config_id
        ).first()
        if not channel:
            raise HTTPException(status_code=404, detail="通道配置不存在")
        
        if channel_data.channel_code is not None:
            channel.channel_code = channel_data.channel_code
        if channel_data.camera_ip is not None:
            channel.camera_ip = channel_data.camera_ip
        if channel_data.camera_name is not None:
            channel.camera_name = channel_data.camera_name
        if channel_data.camera_sn is not None:
            channel.camera_sn = channel_data.camera_sn
        if channel_data.track_space is not None:
            channel.track_space = channel_data.track_space
        if channel_data.parking_spaces is not None:
            # 删除旧的车位记录
            db.query(ParkingSpace).filter(ParkingSpace.channel_config_id == channel_id).delete()
            # 保存新的车位信息到关联表
            save_parking_spaces_to_db(db, channel_id, channel_data.parking_spaces)
        
        channel.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(channel)
        
        parking_spaces = convert_parking_spaces_to_response(channel.parking_spaces_rel) if channel.parking_spaces_rel else None
        
        return ChannelConfigResponse(
            id=channel.id,
            nvr_config_id=channel.nvr_config_id,
            channel_code=channel.channel_code,
            camera_ip=channel.camera_ip,
            camera_name=channel.camera_name,
            camera_sn=channel.camera_sn,
            track_space=channel.track_space,
            parking_spaces=parking_spaces,
            created_at=channel.created_at.isoformat() if channel.created_at else None,
            updated_at=channel.updated_at.isoformat() if channel.updated_at else None,
        )


@app.delete("/api/nvr-configs/{config_id}/channels/{channel_id}")
def delete_channel_config(config_id: int, channel_id: int):
    """删除通道配置"""
    with SessionLocal() as db:
        channel = db.query(ChannelConfig).filter(
            ChannelConfig.id == channel_id,
            ChannelConfig.nvr_config_id == config_id
        ).first()
        if not channel:
            raise HTTPException(status_code=404, detail="通道配置不存在")
        
        db.delete(channel)
        db.commit()
        return {"message": "通道配置已删除"}


@app.post("/api/nvr-configs/{config_id}/channels/{channel_id}/fetch-parking-spaces")
def fetch_parking_spaces(config_id: int, channel_id: int):
    """根据摄像头SN从外部数据库查询车位坐标

    说明：
    - 外部表 parking_space_info_tbl.space_annotation_info 中存的是 parking_points 多边形坐标，
      结构形如：
      [
        {
          "vehicle_bbox": [...],
          "gun_camera_sn": "GXSLqj000030",
          "parking_points": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
          ...
        }
      ]
    - 这里通过 JSON_TABLE + JSON_EXTRACT 先取出 parking_points，再在 Python 里计算矩形 bbox，
      以兼容现有 ParkingSpaceInfo(bbox=[x1,y1,x2,y2]) 与前端绘制逻辑。
    """
    import json
    import pymysql
    
    with SessionLocal() as db:
        channel = db.query(ChannelConfig).filter(
            ChannelConfig.id == channel_id,
            ChannelConfig.nvr_config_id == config_id
        ).first()
        if not channel:
            raise HTTPException(status_code=404, detail="通道配置不存在")
        
        if not channel.camera_sn:
            raise HTTPException(status_code=400, detail="通道配置中未设置摄像头SN")
        
        nvr_config = db.query(NvrConfig).filter(NvrConfig.id == config_id).first()
        if not nvr_config:
            raise HTTPException(status_code=404, detail="NVR配置不存在")
        
        if not all([nvr_config.db_host, nvr_config.db_user, nvr_config.db_password, nvr_config.db_name]):
            raise HTTPException(status_code=400, detail="NVR配置中未设置数据库连接信息")
        
        try:
            # 连接外部数据库
            conn = pymysql.connect(
                host=nvr_config.db_host,
                user=nvr_config.db_user,
                password=nvr_config.db_password,
                port=nvr_config.db_port or 3306,
                database=nvr_config.db_name,
                charset='utf8mb4'
            )
            
            cursor = conn.cursor()
            
            # 执行查询：根据 SN 展开 space_annotation_info，并取出 parking_points 多边形
            sql = """
            SELECT 
                id,
                name,
                JSON_EXTRACT(
                    space_annotation_info,
                    CONCAT('$[', idx - 1, '].parking_points')
                ) AS parking_points
            FROM (
                SELECT 
                    id,
                    name,
                    space_annotation_info,
                    idx
                FROM parking_space_info_tbl
                JOIN JSON_TABLE(
                    space_annotation_info,
                    '$[*]' COLUMNS (
                        idx FOR ORDINALITY,
                        gun_camera_sn VARCHAR(64) PATH '$.gun_camera_sn'
                    )
                ) AS jt
                WHERE jt.gun_camera_sn = %s
            ) AS matched;
            """
            
            cursor.execute(sql, (channel.camera_sn,))
            results = cursor.fetchall()
            
            # 转换为ParkingSpaceInfo格式
            parking_spaces = []
            for row in results:
                space_id, space_name, parking_points_json = row
                if not parking_points_json:
                    continue
                try:
                    points = json.loads(parking_points_json)
                    # 期望 points 为 [[x,y], ...] 的数组
                    if not isinstance(points, list) or not points:
                        continue
                    xs = []
                    ys = []
                    for pt in points:
                        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                            xs.append(float(pt[0]))
                            ys.append(float(pt[1]))
                    if not xs or not ys:
                        continue
                    x1, y1 = min(xs), min(ys)
                    x2, y2 = max(xs), max(ys)
                    # 注意：ParkingSpace.bbox_x2 / bbox_y2 在当前项目中语义为 width / height，
                    # 参见 parking_change_worker._detect_space_occupancy 中的说明。
                    w = max(1, int(round(x2 - x1)))
                    h = max(1, int(round(y2 - y1)))
                    bbox = [int(x1), int(y1), w, h]
                    parking_spaces.append(ParkingSpaceInfo(
                        space_id=str(space_id),
                        space_name=space_name,
                        bbox=bbox
                    ))
                except Exception:
                    # 单条解析失败不影响整体
                    continue
            
            cursor.close()
            conn.close()
            
            # 删除旧的车位记录
            db.query(ParkingSpace).filter(ParkingSpace.channel_config_id == channel_id).delete()
            
            # 保存新的车位信息到关联表
            if parking_spaces:
                save_parking_spaces_to_db(db, channel_id, parking_spaces)
            
            channel.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                "message": f"成功查询到 {len(parking_spaces)} 个车位",
                "parking_spaces": parking_spaces
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"查询车位坐标失败: {str(e)}")


@app.post("/api/nvr-configs/fetch-parking-spaces-by-sn")
def fetch_parking_spaces_by_sn(
    camera_sn: Annotated[str, Query(description="摄像头SN")],
    db_host: Annotated[str, Query(description="数据库地址")],
    db_user: Annotated[str, Query(description="数据库账号")],
    db_password: Annotated[str, Query(description="数据库密码")],
    db_name: Annotated[str, Query(description="数据库名称")],
    db_port: Annotated[int, Query(description="数据库端口")] = 3306
):
    """根据摄像头SN从外部数据库查询车位坐标（保存前使用）

    说明：
    - 与 fetch_parking_spaces 类似，这里同样从 space_annotation_info 中读取 parking_points，
      在 Python 中计算 bbox，返回给前端用于预览/自动填充。
    """
    import json
    import pymysql
    
    if not camera_sn or not camera_sn.strip():
        raise HTTPException(status_code=400, detail="摄像头SN不能为空")
    
    if not all([db_host, db_user, db_password, db_name]):
        raise HTTPException(status_code=400, detail="数据库连接信息不完整")
    
    try:
        # 连接外部数据库
        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            port=db_port or 3306,
            database=db_name,
            charset='utf8mb4'
        )
        
        cursor = conn.cursor()
        
        # 执行查询：根据 SN 展开 space_annotation_info，并取出 parking_points 多边形
        sql = """
        SELECT 
            id,
            name,
            JSON_EXTRACT(
                space_annotation_info,
                CONCAT('$[', idx - 1, '].parking_points')
            ) AS parking_points
        FROM (
            SELECT 
                id,
                name,
                space_annotation_info,
                idx
            FROM parking_space_info_tbl
            JOIN JSON_TABLE(
                space_annotation_info,
                '$[*]' COLUMNS (
                    idx FOR ORDINALITY,
                    gun_camera_sn VARCHAR(64) PATH '$.gun_camera_sn'
                )
            ) AS jt
            WHERE jt.gun_camera_sn = %s
        ) AS matched;
        """
        
        cursor.execute(sql, (camera_sn.strip(),))
        results = cursor.fetchall()
        
        # 转换为ParkingSpaceInfo格式
        parking_spaces = []
        for row in results:
            space_id, space_name, parking_points_json = row
            if not parking_points_json:
                continue
            try:
                points = json.loads(parking_points_json)
                if not isinstance(points, list) or not points:
                    continue
                xs = []
                ys = []
                for pt in points:
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        xs.append(float(pt[0]))
                        ys.append(float(pt[1]))
                if not xs or not ys:
                    continue
                x1, y1 = min(xs), min(ys)
                x2, y2 = max(xs), max(ys)
                w = max(1, int(round(x2 - x1)))
                h = max(1, int(round(y2 - y1)))
                bbox = [int(x1), int(y1), w, h]
                parking_spaces.append(ParkingSpaceInfo(
                    space_id=str(space_id),
                    space_name=space_name,
                    bbox=bbox
                ))
            except Exception:
                continue
        
        cursor.close()
        conn.close()
        
        return {
            "message": f"成功查询到 {len(parking_spaces)} 个车位",
            "parking_spaces": parking_spaces
        }
        
    except pymysql.Error as e:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询车位坐标失败: {str(e)}")


@app.post("/api/nvr-configs/fetch-track-space-by-sn")
def fetch_track_space_by_sn(
    camera_sn: Annotated[str, Query(description="摄像头SN")],
    db_host: Annotated[str, Query(description="数据库地址")],
    db_user: Annotated[str, Query(description="数据库账号")],
    db_password: Annotated[str, Query(description="数据库密码")],
    db_name: Annotated[str, Query(description="数据库名称")],
    db_port: Annotated[int, Query(description="数据库端口")] = 3306,
):
    """根据摄像头SN从外部数据库查询识别停车区域坐标(track_space)，用于保存前预览/自动填写"""
    import pymysql

    if not camera_sn or not camera_sn.strip():
        raise HTTPException(status_code=400, detail="摄像头SN不能为空")

    if not all([db_host, db_user, db_password, db_name]):
        raise HTTPException(status_code=400, detail="数据库连接信息不完整")

    try:
        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            port=db_port or 3306,
            database=db_name,
            charset="utf8mb4",
        )
        cursor = conn.cursor()
        sql = """
        SELECT track_space
        FROM parking_space_mng_unit_info_tbl 
        WHERE gun_camera_sn = %s
        """
        cursor.execute(sql, (camera_sn.strip(),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        track_space_value = None
        if rows:
            # 如果有多条记录，优先取第一条非空
            for (ts,) in rows:
                if ts:
                    track_space_value = ts
                    break
            if track_space_value is None:
                track_space_value = rows[0][0]

        return {
            "message": "查询成功" if track_space_value is not None else "未查询到识别区域坐标",
            "track_space": track_space_value,
        }
    except pymysql.Error as e:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询识别区域坐标失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)

