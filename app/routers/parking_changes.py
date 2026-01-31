"""车位变化查询 API 路由"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.parking_change_service import ParkingChangeService


router = APIRouter(prefix="/api/parking_changes", tags=["车位变化"])


@router.get("")
def list_parking_change_snapshots(
    date: Optional[str] = Query(None, description="任务日期，格式 YYYY-MM-DD"),
    # IP 搜索（精准/模糊）
    ip: Optional[str] = Query(None, description="摄像机 IP（精准匹配）"),
    ip_like: Optional[str] = Query(None, alias="ip__like", description="摄像机 IP（模糊匹配）"),
    # 通道搜索（精准/模糊）
    channel: Optional[str] = Query(None, description="通道编码（精准匹配），如 c1/c2"),
    channel_like: Optional[str] = Query(None, alias="channel__like", description="通道编码（模糊匹配）"),
    # 车场名称
    parking_name: Optional[str] = Query(None, description="车场名称（模糊匹配）"),
    # 任务状态
    task_status: Optional[str] = Query(None, description="任务状态（精准匹配）"),
    task_status_in: Optional[str] = Query(None, alias="task_status__in", description="任务状态（多选，逗号分隔）"),
    # 时间戳范围
    task_start_ts_gte: Optional[int] = Query(None, alias="task_start_ts__gte", description="任务开始时间戳 >="),
    task_start_ts_lte: Optional[int] = Query(None, alias="task_start_ts__lte", description="任务开始时间戳 <="),
    task_end_ts_gte: Optional[int] = Query(None, alias="task_end_ts__gte", description="任务结束时间戳 >="),
    task_end_ts_lte: Optional[int] = Query(None, alias="task_end_ts__lte", description="任务结束时间戳 <="),
    # 车位相关
    space_name: Optional[str] = Query(None, description="车位编号（模糊匹配）"),
    change_type: Optional[str] = Query(None, description="变化类型：arrive/leave/unknown"),
    # 图片名称搜索（与图片列表保持一致）
    name_eq: Optional[str] = Query(None, alias="name__eq", description="精准搜索图片名称"),
    name_like: Optional[str] = Query(None, alias="name__like", description="模糊搜索图片名称"),
    # 状态标签搜索（与图片列表保持一致）
    status_label: Optional[str] = Query(None, description="精准搜索状态标签"),
    status_label_in: Optional[str] = Query(None, alias="status_label__in", description="多选状态标签，逗号分隔"),
    # 缺失状态搜索（与图片列表保持一致）
    missing: Optional[bool] = Query(None, description="是否缺失（true/false）"),
    # 分页
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页数量"),
    db: Session = Depends(get_db),
):
    """分页获取“有车位变化”的截图快照列表（支持与图片列表类似的搜索条件）。"""
    service = ParkingChangeService(db)
    return service.list_snapshots(
        date=date,
        ip=ip,
        ip_like=ip_like,
        channel=channel,
        channel_like=channel_like,
        parking_name=parking_name,
        task_status=task_status,
        task_status_in=task_status_in,
        task_start_ts_gte=task_start_ts_gte,
        task_start_ts_lte=task_start_ts_lte,
        task_end_ts_gte=task_end_ts_gte,
        task_end_ts_lte=task_end_ts_lte,
        space_name=space_name,
        change_type=change_type,
        name_eq=name_eq,
        name_like=name_like,
        status_label=status_label,
        status_label_in=status_label_in,
        missing=missing,
        page=page,
        page_size=page_size,
    )


@router.get("/grouped")
def list_parking_changes_grouped_by_channel(
    date: Optional[str] = Query(None, description="任务日期，格式 YYYY-MM-DD"),
    ip: Optional[str] = Query(None, description="摄像机 IP（精准匹配）"),
    ip_like: Optional[str] = Query(None, alias="ip__like", description="摄像机 IP（模糊匹配）"),
    channel: Optional[str] = Query(None, description="通道编码（精准匹配），如 c1/c2"),
    channel_like: Optional[str] = Query(None, alias="channel__like", description="通道编码（模糊匹配）"),
    parking_name: Optional[str] = Query(None, description="车场名称（模糊匹配）"),
    task_status: Optional[str] = Query(None, description="任务状态（精准匹配）"),
    task_status_in: Optional[str] = Query(None, alias="task_status__in", description="任务状态（多选，逗号分隔）"),
    task_start_ts_gte: Optional[int] = Query(None, alias="task_start_ts__gte", description="任务开始时间戳 >="),
    task_start_ts_lte: Optional[int] = Query(None, alias="task_start_ts__lte", description="任务开始时间戳 <="),
    task_end_ts_gte: Optional[int] = Query(None, alias="task_end_ts__gte", description="任务结束时间戳 >="),
    task_end_ts_lte: Optional[int] = Query(None, alias="task_end_ts__lte", description="任务结束时间戳 <="),
    space_name: Optional[str] = Query(None, description="车位编号（模糊匹配）"),
    change_type: Optional[str] = Query(None, description="变化类型：arrive/leave/unknown"),
    db: Session = Depends(get_db),
):
    """按通道分组获取所有车位变化快照，每个通道内按时间顺序排序（最早的在前）。
    
    返回格式：按通道分组，每个通道内的快照按时间顺序排列，每个快照包含当前图和上一张对比图。
    """
    service = ParkingChangeService(db)
    return service.list_snapshots_grouped_by_channel(
        date=date,
        ip=ip,
        ip_like=ip_like,
        channel=channel,
        channel_like=channel_like,
        parking_name=parking_name,
        task_status=task_status,
        task_status_in=task_status_in,
        task_start_ts_gte=task_start_ts_gte,
        task_start_ts_lte=task_start_ts_lte,
        task_end_ts_gte=task_end_ts_gte,
        task_end_ts_lte=task_end_ts_lte,
        space_name=space_name,
        change_type=change_type,
    )


@router.get("/grouped-by-space")
def list_parking_changes_grouped_by_space(
    date: Optional[str] = Query(None, description="任务日期，格式 YYYY-MM-DD"),
    ip: Optional[str] = Query(None, description="摄像机 IP（精准匹配）"),
    ip_like: Optional[str] = Query(None, alias="ip__like", description="摄像机 IP（模糊匹配）"),
    channel: Optional[str] = Query(None, description="通道编码（精准匹配），如 c1/c2"),
    channel_like: Optional[str] = Query(None, alias="channel__like", description="通道编码（模糊匹配）"),
    parking_name: Optional[str] = Query(None, description="车场名称（模糊匹配）"),
    task_status: Optional[str] = Query(None, description="任务状态（精准匹配）"),
    task_status_in: Optional[str] = Query(None, alias="task_status__in", description="任务状态（多选，逗号分隔）"),
    task_start_ts_gte: Optional[int] = Query(None, alias="task_start_ts__gte", description="任务开始时间戳 >="),
    task_start_ts_lte: Optional[int] = Query(None, alias="task_start_ts__lte", description="任务开始时间戳 <="),
    task_end_ts_gte: Optional[int] = Query(None, alias="task_end_ts__gte", description="任务结束时间戳 >="),
    task_end_ts_lte: Optional[int] = Query(None, alias="task_end_ts__lte", description="任务结束时间戳 <="),
    space_name: Optional[str] = Query(None, description="车位编号（模糊匹配）"),
    change_type: Optional[str] = Query(None, description="变化类型：arrive/leave/unknown"),
    db: Session = Depends(get_db),
):
    """按车位分组获取所有车位变化记录，每个车位内按时间顺序排序（最早的在前）。
    
    返回格式：按车位分组，每个车位内的变化按时间顺序排列。
    """
    service = ParkingChangeService(db)
    return service.list_changes_grouped_by_space(
        date=date,
        ip=ip,
        ip_like=ip_like,
        channel=channel,
        channel_like=channel_like,
        parking_name=parking_name,
        task_status=task_status,
        task_status_in=task_status_in,
        task_start_ts_gte=task_start_ts_gte,
        task_start_ts_lte=task_start_ts_lte,
        task_end_ts_gte=task_end_ts_gte,
        task_end_ts_lte=task_end_ts_lte,
        space_name=space_name,
        change_type=change_type,
    )


@router.get("/grouped-by-channel-and-space")
def list_parking_changes_grouped_by_channel_and_space(
    date: Optional[str] = Query(None, description="任务日期，格式 YYYY-MM-DD"),
    ip: Optional[str] = Query(None, description="摄像机 IP（精准匹配）"),
    ip_like: Optional[str] = Query(None, alias="ip__like", description="摄像机 IP（模糊匹配）"),
    channel: Optional[str] = Query(None, description="通道编码（精准匹配），如 c1/c2"),
    channel_like: Optional[str] = Query(None, alias="channel__like", description="通道编码（模糊匹配）"),
    parking_name: Optional[str] = Query(None, description="车场名称（模糊匹配）"),
    task_status: Optional[str] = Query(None, description="任务状态（精准匹配）"),
    task_status_in: Optional[str] = Query(None, alias="task_status__in", description="任务状态（多选，逗号分隔）"),
    task_start_ts_gte: Optional[int] = Query(None, alias="task_start_ts__gte", description="任务开始时间戳 >="),
    task_start_ts_lte: Optional[int] = Query(None, alias="task_start_ts__lte", description="任务开始时间戳 <="),
    task_end_ts_gte: Optional[int] = Query(None, alias="task_end_ts__gte", description="任务结束时间戳 >="),
    task_end_ts_lte: Optional[int] = Query(None, alias="task_end_ts__lte", description="任务结束时间戳 <="),
    space_name: Optional[str] = Query(None, description="车位编号（模糊匹配）"),
    change_type: Optional[str] = Query(None, description="变化类型：arrive/leave/unknown"),
    db: Session = Depends(get_db),
):
    """按通道分组，每个通道下显示所有车位及其在不同时间段的状态。
    
    返回格式：按通道分组，每个通道下的车位按名称排序，每个车位包含时间线状态。
    """
    service = ParkingChangeService(db)
    return service.list_changes_grouped_by_channel_and_space(
        date=date,
        ip=ip,
        ip_like=ip_like,
        channel=channel,
        channel_like=channel_like,
        parking_name=parking_name,
        task_status=task_status,
        task_status_in=task_status_in,
        task_start_ts_gte=task_start_ts_gte,
        task_start_ts_lte=task_start_ts_lte,
        task_end_ts_gte=task_end_ts_gte,
        task_end_ts_lte=task_end_ts_lte,
        space_name=space_name,
        change_type=change_type,
    )


@router.get("/analysis/{channel_config_id}")
def get_channel_analysis_report(
    channel_config_id: int,
    date: Optional[str] = Query(None, description="任务日期，格式 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500, description="最多分析的快照数量"),
    db: Session = Depends(get_db),
):
    """获取通道的详细对比分析报告，包括时间序列、车位状态对比表、事件时间线等。"""
    service = ParkingChangeService(db)
    data = service.get_channel_analysis_report(
        channel_config_id=channel_config_id,
        date=date,
        limit=limit,
    )
    if not data:
        raise HTTPException(status_code=404, detail="通道配置不存在或无数据")
    return data


@router.get("/{snapshot_id}")
def get_parking_change_snapshot_detail(
    snapshot_id: int,
    db: Session = Depends(get_db),
):
    """获取某次车位变化快照的明细，包括具体哪些车位发生了变化。"""
    service = ParkingChangeService(db)
    data = service.get_snapshot_detail(snapshot_id)
    if not data:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return data

