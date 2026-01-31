"""图片管理路由模块"""
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.image_service import ImageService
from app.core.config import SCREENSHOT_BASE

router = APIRouter(prefix="/api/images", tags=["图片管理"])


# ==================== 图片查询 ====================

@router.get("")
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
    db: Session = Depends(get_db),
):
    """
    每个任务只返回一张截图（最新的一张），保证"任务数 = 图片数"，不多不少。
    若任务没有截图，也会返回一条记录，标记 missing=True，便于排查缺图。
    """
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


@router.get("/{date}")
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
    db: Session = Depends(get_db),
):
    """
    每个任务只返回一张截图（最新的一张），保证"任务数 = 图片数"，不多不少。
    若任务没有截图，也会返回一条记录，标记 missing=True，便于排查缺图。
    向后兼容：支持通过路径参数指定日期。
    """
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


@router.get("/available_dates")
def list_image_dates(
    screenshot_dir: str = "screenshots",
    db: Session = Depends(get_db),
):
    """
    返回有截图数据的日期列表（优先数据库，有则提供数量；无则扫描文件夹）。
    """
    service = ImageService(db)
    return service.get_available_dates(screenshot_dir=screenshot_dir)


# ==================== OCR 结果查询 ====================

@router.get("/task/{task_id}/ocr")
def get_task_ocr(
    task_id: int,
    db: Session = Depends(get_db),
):
    """根据任务 ID 获取该任务最新截图及其 OCR 时间结果。"""
    service = ImageService(db)
    data = service.get_task_ocr(task_id)
    # 如果既没有截图也没有 OCR，则返回 404，更直观一些
    if not data["has_screenshot"]:
        raise HTTPException(status_code=404, detail="任务暂无截图或不存在")
    return data


# 注意：image_proxy 路由需要在主应用中单独注册，因为它的路径是 /api/image_proxy
# 而不是 /api/images/proxy，以保持向后兼容

