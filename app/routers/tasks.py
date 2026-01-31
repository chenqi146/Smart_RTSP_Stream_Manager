"""任务管理路由模块"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from schemas.tasks import (
    TaskCreateRequest,
    TaskCreateResponse,
    RunTaskRequest,
    RunAllRequest,
    RerunConfigRequest,
)
from app.dependencies import get_db
from app.services.task_service import TaskService
from app.core.constants import (
    DEFAULT_PAGE_SIZE,
    MIN_PAGE_SIZE,
    MAX_PAGE_SIZE,
    TASKS_PREFIX,
)

router = APIRouter(prefix=TASKS_PREFIX, tags=["任务管理"])


# ==================== 任务创建 ====================

@router.post("/create", response_model=TaskCreateResponse)
def create_tasks(
    req: TaskCreateRequest,
    db: Session = Depends(get_db)
):
    """
    生成指定日期的10分钟分片任务列表（默认144个片段）。
    """
    service = TaskService(db)
    res = service.ensure_tasks(req)
    
    # 生成后自动尝试运行对应组合（后台任务）
    # 注意：这里暂时保持原有逻辑，后续可以移到后台任务模块
    from utils.task_utils import make_task_key
    from app.background.task_runners import run_combo_async
    import threading
    
    run_req = RunTaskRequest(
        date=req.date,
        base_rtsp=req.base_rtsp,
        channel=req.channel,
        interval_minutes=req.interval_minutes,
    )
    threading.Thread(target=run_combo_async, args=(run_req,), daemon=True).start()
    
    return res


# ==================== 任务查询（辅助数据） ====================

@router.get("/available_dates")
def list_task_dates(db: Session = Depends(get_db)):
    """
    从任务表的 start_ts 字段提取所有唯一的日期（YYYY-MM-DD 格式），用于填充日期搜索下拉框。
    """
    service = TaskService(db)
    dates = service.get_available_dates()
    return {"dates": dates}


@router.get("/available_ips")
def list_task_ips(db: Session = Depends(get_db)):
    """
    从任务表的 rtsp_url 字段提取所有唯一的 IP 地址，用于填充 IP 搜索下拉框。
    """
    service = TaskService(db)
    ips = service.get_available_ips()
    return {"ips": ips}


@router.get("/available_channels")
def list_task_channels(db: Session = Depends(get_db)):
    """
    从任务表的 rtsp_url 字段提取所有唯一的通道，用于填充通道搜索下拉框。
    """
    service = TaskService(db)
    channels = service.get_available_channels()
    return {"channels": channels}


# ==================== 任务配置列表 ====================

@router.get("/configs")
def list_task_configs(
    date: Optional[str] = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    # 搜索参数
    date_like: Optional[str] = Query(None, alias="date__like"),
    ip: Optional[str] = None,
    ip_like: Optional[str] = Query(None, alias="ip__like"),
    channel: Optional[str] = None,
    channel_like: Optional[str] = Query(None, alias="channel__like"),
    rtsp_base_like: Optional[str] = Query(None, alias="rtsp_base__like"),
    status: Optional[str] = None,
    status_in: Optional[str] = Query(None, alias="status__in"),
    start_ts_gte: Optional[int] = Query(None, alias="start_ts__gte"),
    start_ts_lte: Optional[int] = Query(None, alias="start_ts__lte"),
    end_ts_gte: Optional[int] = Query(None, alias="end_ts__gte"),
    end_ts_lte: Optional[int] = Query(None, alias="end_ts__lte"),
    interval_minutes: Optional[int] = None,
    interval_minutes_gte: Optional[int] = Query(None, alias="interval_minutes__gte"),
    interval_minutes_lte: Optional[int] = Query(None, alias="interval_minutes__lte"),
    operation_time_gte: Optional[str] = Query(None, alias="operation_time__gte"),
    operation_time_lte: Optional[str] = Query(None, alias="operation_time__lte"),
    db: Session = Depends(get_db)
):
    """
    获取任务配置汇总列表，按日期、RTSP地址、通道、间隔分组。
    返回每个配置的汇总信息，包括任务状态统计。
    支持丰富的搜索条件和分页。
    """
    # 注意：这个端点逻辑较复杂，暂时保持原有实现
    # 后续可以重构到 service 层
    from app.main import list_task_configs as original_list_task_configs
    return original_list_task_configs(
        date=date,
        page=page,
        page_size=page_size,
        date_like=date_like,
        ip=ip,
        ip_like=ip_like,
        channel=channel,
        channel_like=channel_like,
        rtsp_base_like=rtsp_base_like,
        status=status,
        status_in=status_in,
        start_ts_gte=start_ts_gte,
        start_ts_lte=start_ts_lte,
        end_ts_gte=end_ts_gte,
        end_ts_lte=end_ts_lte,
        interval_minutes=interval_minutes,
        interval_minutes_gte=interval_minutes_gte,
        interval_minutes_lte=interval_minutes_lte,
        operation_time_gte=operation_time_gte,
        operation_time_lte=operation_time_lte,
    )


# ==================== 任务详情（分页） ====================

@router.get("/paged")
def get_tasks_paged(
    date: Optional[str] = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    task_id: Optional[int] = None,
    # 向后兼容的旧参数
    screenshot_name: Optional[str] = None,
    rtsp_ip: Optional[str] = None,
    channel: Optional[str] = None,
    # 新的搜索参数
    screenshot_name_eq: Optional[str] = Query(None, alias="screenshot_name__eq"),
    screenshot_name_like: Optional[str] = Query(None, alias="screenshot_name__like"),
    rtsp_url_eq: Optional[str] = Query(None, alias="rtsp_url__eq"),
    rtsp_url_like: Optional[str] = Query(None, alias="rtsp_url__like"),
    ip: Optional[str] = None,
    ip_like: Optional[str] = Query(None, alias="ip__like"),
    channel_eq: Optional[str] = Query(None, alias="channel__eq"),
    channel_like: Optional[str] = Query(None, alias="channel__like"),
    status: Optional[str] = None,
    status_in: Optional[str] = Query(None, alias="status__in"),
    start_ts_gte: Optional[int] = Query(None, alias="start_ts__gte"),
    start_ts_lte: Optional[int] = Query(None, alias="start_ts__lte"),
    end_ts_gte: Optional[int] = Query(None, alias="end_ts__gte"),
    end_ts_lte: Optional[int] = Query(None, alias="end_ts__lte"),
    operation_time_gte: Optional[str] = Query(None, alias="operation_time__gte"),
    operation_time_lte: Optional[str] = Query(None, alias="operation_time__lte"),
    error_like: Optional[str] = Query(None, alias="error__like"),
    db: Session = Depends(get_db)
):
    """
    获取任务列表详情（分页），支持丰富的搜索条件。
    """
    service = TaskService(db)
    
    # 构建过滤条件
    filters = {}
    if task_id:
        filters["task_id"] = task_id
    if ip or rtsp_ip:
        filters["ip"] = ip or rtsp_ip
    if channel or channel_eq:
        filters["channel"] = channel or channel_eq
    if channel_like:
        filters["channel_like"] = channel_like
    if status:
        filters["status"] = status
    if status_in:
        filters["status_in"] = status_in
    if screenshot_name or screenshot_name_like:
        filters["screenshot_name_like"] = screenshot_name or screenshot_name_like
    if rtsp_url_like:
        filters["rtsp_url_like"] = rtsp_url_like
    if start_ts_gte is not None:
        filters["start_ts_gte"] = start_ts_gte
    if start_ts_lte is not None:
        filters["start_ts_lte"] = start_ts_lte
    if end_ts_gte is not None:
        filters["end_ts_gte"] = end_ts_gte
    if end_ts_lte is not None:
        filters["end_ts_lte"] = end_ts_lte
    
    return service.get_tasks_paged(
        date=date,
        page=page,
        page_size=page_size,
        **filters
    )


# ==================== 任务删除 ====================

@router.delete("/configs")
def delete_config_tasks(
    date: str = Query(..., description="任务日期"),
    rtsp_ip: str = Query(..., description="RTSP IP地址"),
    channel: str = Query(..., description="通道"),
    db: Session = Depends(get_db)
):
    """
    删除指定配置下的所有任务及其关联数据。
    根据日期、IP地址、通道匹配任务并删除。
    """
    service = TaskService(db)
    return service.delete_config_tasks(date, rtsp_ip, channel)


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """
    删除单个任务及其关联的截图、OCR结果和物理文件。
    """
    service = TaskService(db)
    success = service.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"message": "任务及其关联数据已删除", "task_id": task_id}


# ==================== 任务重新运行 ====================

@router.post("/configs/rerun")
def rerun_config_tasks(
    request: RerunConfigRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    重新运行指定配置下的所有任务。
    根据日期、IP地址、通道匹配任务并重新运行。
    """
    # 注意：这个端点逻辑较复杂，暂时保持原有实现
    from app.main import rerun_config_tasks as original_rerun_config_tasks
    return original_rerun_config_tasks(request, background_tasks)


@router.post("/{task_id}/rerun")
def rerun_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    重新运行单个任务：重新执行截图操作，更新任务状态和数据库。
    """
    # 注意：这个端点逻辑较复杂，暂时保持原有实现
    from app.main import rerun_task as original_rerun_task
    return original_rerun_task(task_id, background_tasks)


# ==================== 任务执行 ====================

@router.post("/run")
def run_tasks(
    req: RunTaskRequest,
    background_tasks: BackgroundTasks
):
    """
    创建并后台运行指定日期的任务（按10分钟切片：拉流→截图→去重→OCR）。
    """
    # 注意：这个端点逻辑较复杂，暂时保持原有实现
    from app.main import run_tasks as original_run_tasks
    return original_run_tasks(req, background_tasks)


@router.post("/run_all")
def run_all_tasks(
    req: RunAllRequest,
    background_tasks: BackgroundTasks
):
    """
    后台并行运行同一日期下所有基础RTSP+通道组合的任务。
    """
    # 注意：这个端点逻辑较复杂，暂时保持原有实现
    from app.main import run_all_tasks as original_run_all_tasks
    return original_run_all_tasks(req, background_tasks)

