"""车位变化业务服务层"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.repositories.parking_change_repository import ParkingChangeRepository
from app.core.config import SCREENSHOT_BASE
from models import Screenshot, Task
from pathlib import Path


def _build_image_url(file_path: str, prefer_detected: bool = True) -> str:
    """构造截图访问 URL（复用 /shots 静态挂载规则）。
    
    参数:
        file_path: 原始截图文件路径
        prefer_detected: 如果为 True，优先返回 _detected.jpg 的URL（如果存在）
    
    返回:
        图片URL（如果 _detected.jpg 不存在，回退到原始图片）
    """
    p = Path(file_path)
    if not p.is_absolute():
        p = SCREENSHOT_BASE / p
    
    # 如果优先使用 _detected.jpg，先检查是否存在
    original_path = p
    if prefer_detected:
        detected_path = p.parent / f"{p.stem}_detected{p.suffix}"
        if detected_path.exists():
            p = detected_path
        # 如果 _detected.jpg 不存在，使用原始图片
    
    # 确保文件存在，如果都不存在，返回原始路径的URL
    if not p.exists():
        p = original_path
    
    try:
        rel = p.resolve().relative_to(SCREENSHOT_BASE)
        # 添加版本号避免缓存
        version = int(p.stat().st_mtime) if p.exists() else 0
        url = f"/shots/{rel.as_posix()}"
        if version:
            url = f"{url}?v={version}"
        return url
    except Exception:
        # 回退到原始路径
        return f"/shots/{p.name}"


class ParkingChangeService:
    """封装车位变化查询的业务逻辑。"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = ParkingChangeRepository(db)

    def list_snapshots(
        self,
        date: Optional[str] = None,
        ip: Optional[str] = None,
        ip_like: Optional[str] = None,
        channel: Optional[str] = None,
        channel_like: Optional[str] = None,
        parking_name: Optional[str] = None,
        task_status: Optional[str] = None,
        task_status_in: Optional[str] = None,
        task_start_ts_gte: Optional[int] = None,
        task_start_ts_lte: Optional[int] = None,
        task_end_ts_gte: Optional[int] = None,
        task_end_ts_lte: Optional[int] = None,
        space_name: Optional[str] = None,
        change_type: Optional[str] = None,
        name_eq: Optional[str] = None,
        name_like: Optional[str] = None,
        status_label: Optional[str] = None,
        status_label_in: Optional[str] = None,
        missing: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        offset = max(0, (page - 1) * page_size)
        limit = max(1, min(page_size, 100))

        # 处理 task_status_in（逗号分隔的字符串）
        task_status_list = None
        if task_status_in:
            task_status_list = [s.strip() for s in task_status_in.split(",") if s.strip()]

        # 处理 status_label_in（逗号分隔的字符串）
        status_label_list = None
        if status_label_in:
            status_label_list = [s.strip() for s in status_label_in.split(",") if s.strip()]

        # 检查是否有需要在 service 层过滤的条件
        # 这些条件需要检查文件系统，无法在数据库层面过滤
        needs_service_filter = bool(name_eq or name_like or status_label or status_label_list or missing is not None)
        
        # 如果有 service 层过滤条件，需要获取所有符合基础条件的数据进行过滤
        # 否则使用正常的分页查询
        if needs_service_filter:
            # 获取所有符合基础条件的数据（使用较大的 limit）
            snapshots, db_total = self.repo.list_snapshots(
                date=date,
                ip=ip,
                ip_like=ip_like,
                channel=channel,
                channel_like=channel_like,
                parking_name=parking_name,
                task_status=task_status,
                task_status_in=task_status_list,
                task_start_ts_gte=task_start_ts_gte,
                task_start_ts_lte=task_start_ts_lte,
                task_end_ts_gte=task_end_ts_gte,
                task_end_ts_lte=task_end_ts_lte,
                space_name=space_name,
                change_type=change_type,
                name_eq=None,  # repository 层不使用这些参数
                name_like=None,
                status_label=None,
                status_label_in=None,
                missing=None,
                offset=0,
                limit=10000,  # 获取足够多的数据
            )
        else:
            # 没有 service 层过滤条件，使用正常分页
            snapshots, db_total = self.repo.list_snapshots(
                date=date,
                ip=ip,
                ip_like=ip_like,
                channel=channel,
                channel_like=channel_like,
                parking_name=parking_name,
                task_status=task_status,
                task_status_in=task_status_list,
                task_start_ts_gte=task_start_ts_gte,
                task_start_ts_lte=task_start_ts_lte,
                task_end_ts_gte=task_end_ts_gte,
                task_end_ts_lte=task_end_ts_lte,
                space_name=space_name,
                change_type=change_type,
                name_eq=None,  # repository 层不使用这些参数
                name_like=None,
                status_label=None,
                status_label_in=None,
                missing=None,
                offset=offset,
                limit=limit,
            )

        items: List[Dict[str, Any]] = []
        for snap in snapshots:
            try:
                shot: Optional[Screenshot] = None
                if snap.screenshot_id:
                    shot = (
                        self.db.query(Screenshot).filter(Screenshot.id == snap.screenshot_id).first()
                    )
                
                task: Optional[Task] = None
                if snap.task_id:
                    task = (
                        self.db.query(Task).filter(Task.id == snap.task_id).first()
                    )
                
                # 获取图片名称（用于名称过滤）
                image_name = ""
                if shot and shot.file_path:
                    image_name = Path(shot.file_path).name
                
                # 应用图片名称过滤
                if name_eq and image_name != name_eq.strip():
                    continue
                if name_like and name_like.strip() and name_like.strip() not in image_name:
                    continue
                
                # 获取状态标签（用于状态标签过滤）
                status_label_val, status_label_display = self.get_status_label(task, shot)
                
                # 应用状态标签过滤
                if status_label and status_label_display != status_label:
                    continue
                if status_label_list and status_label_display and status_label_display not in status_label_list:
                    continue
                
                # 检查缺失状态（用于缺失状态过滤）
                missing_val = False
                if shot and shot.file_path:
                    try:
                        p = Path(shot.file_path)
                        file_path = SCREENSHOT_BASE / p if not p.is_absolute() else p
                        missing_val = not file_path.exists()
                    except Exception:
                        missing_val = True  # 如果路径处理出错，视为缺失
                else:
                    missing_val = True  # 没有截图记录视为缺失
                
                # 应用缺失状态过滤
                if missing is not None:
                    if missing != missing_val:
                        continue
                else:
                    # 默认（前端"是否缺失=全部"但没有显式勾选缺失时），只展示"有真实截图文件"的记录
                    if missing_val:
                        continue
                
                image_url = _build_image_url(shot.file_path, prefer_detected=True) if shot and shot.file_path else ""
                
                # 获取变化详情（车位名称和变化类型）
                changes = self.repo.get_changes_by_snapshot_id(snap.id)
                change_details = []
                for change in changes:
                    if change.change_type in ("arrive", "leave"):
                        change_details.append({
                            "space_name": change.space_name or f"车位{change.space_id}",
                            "change_type": change.change_type,
                        })
                
                items.append(
                    {
                        "id": snap.id,
                        "task_id": snap.task_id,
                        "screenshot_id": snap.screenshot_id,
                        "image_url": image_url,
                        "ip": snap.ip if snap.ip else None,
                        "channel": snap.channel_code if snap.channel_code else None,
                        "parking_name": snap.parking_name if snap.parking_name else None,
                        "change_count": snap.change_count if snap.change_count else 0,
                        "detected_at": snap.detected_at.isoformat() if snap.detected_at else None,
                        "task_date": task.date if task and task.date else None,
                        "change_details": change_details,  # 新增：变化详情列表
                    }
                )
            except Exception as e:
                # 记录错误但继续处理其他记录
                import logging
                logging.warning(f"处理车位变化快照 {snap.id if snap else 'unknown'} 时出错: {e}")
                continue

        # 如果有 service 层过滤，需要重新分页
        if needs_service_filter:
            total_filtered = len(items)
            # 应用分页
            items = items[offset:offset + limit]
            return {
                "total": total_filtered,
                "page": page,
                "page_size": limit,
                "items": items,
            }
        else:
            # 没有 service 层过滤，使用 repository 返回的 total
            return {
                "total": db_total,
                "page": page,
                "page_size": limit,
                "items": items,
            }

    def get_snapshot_detail(self, snapshot_id: int) -> Dict[str, Any]:
        """获取某个快照下的所有车位变化详情，包括上一张截图信息和绘制坐标数据。"""
        from models import ParkingChangeSnapshot, ChannelConfig, ParkingSpace  # 避免循环导入

        snap: Optional[ParkingChangeSnapshot] = (
            self.db.query(ParkingChangeSnapshot).filter(ParkingChangeSnapshot.id == snapshot_id).first()
        )
        if not snap:
            return {}

        shot: Optional[Screenshot] = (
            self.db.query(Screenshot).filter(Screenshot.id == snap.screenshot_id).first()
        )
        task: Optional[Task] = (
            self.db.query(Task).filter(Task.id == snap.task_id).first()
        )
        changes = self.repo.get_changes_by_snapshot_id(snapshot_id)

        # 当前截图信息（优先使用 _detected.jpg）
        image_url = _build_image_url(shot.file_path, prefer_detected=True) if shot else ""
        
        # 查找上一张截图（同一通道、同一任务）
        prev_screenshot = self.repo.get_prev_screenshot_for_snapshot(snapshot_id)
        prev_image_url = None
        prev_screenshot_id = None
        if prev_screenshot:
            prev_image_url = _build_image_url(prev_screenshot.file_path, prefer_detected=True)
            prev_screenshot_id = prev_screenshot.id
        
        # 获取通道配置和停车位坐标（用于绘制）
        channel_config: Optional[ChannelConfig] = None
        track_space = None
        parking_spaces_data = []
        
        if snap.channel_config_id:
            channel_config = (
                self.db.query(ChannelConfig)
                .filter(ChannelConfig.id == snap.channel_config_id)
                .first()
            )
            if channel_config:
                track_space = channel_config.track_space
                # 获取该通道下的所有停车位
                parking_spaces = (
                    self.db.query(ParkingSpace)
                    .filter(ParkingSpace.channel_config_id == channel_config.id)
                    .all()
                )
                for ps in parking_spaces:
                    parking_spaces_data.append({
                        "id": ps.id,
                        "space_name": ps.space_name,
                        "bbox_x1": ps.bbox_x1,
                        "bbox_y1": ps.bbox_y1,
                        "bbox_x2": ps.bbox_x2,
                        "bbox_y2": ps.bbox_y2,
                    })
        
        change_items: List[Dict[str, Any]] = []
        for c in changes:
            change_items.append(
                {
                    "space_id": c.space_id,
                    "space_name": c.space_name,
                    "prev_occupied": c.prev_occupied,
                    "curr_occupied": c.curr_occupied,
                    "change_type": c.change_type,
                    "detected_at": c.detected_at.isoformat() if c.detected_at else None,
                }
            )

        return {
            "snapshot": {
                "id": snap.id,
                "task_id": snap.task_id,
                "screenshot_id": snap.screenshot_id,
                "ip": snap.ip,
                "channel": snap.channel_code,
                "parking_name": snap.parking_name,
                "change_count": snap.change_count,
                "detected_at": snap.detected_at.isoformat() if snap.detected_at else None,
                "task_date": task.date if task else None,
                "image_url": image_url,
            },
            "prev_screenshot": {
                "id": prev_screenshot_id,
                "image_url": prev_image_url,
            } if prev_screenshot_id else None,
            "drawing_data": {
                "track_space": track_space,  # 跟踪区域坐标（JSON字符串）
                "parking_spaces": parking_spaces_data,  # 停车位坐标列表
            },
            "changes": change_items,
        }
    
    def list_snapshots_grouped_by_channel(
        self,
        date: Optional[str] = None,
        ip: Optional[str] = None,
        ip_like: Optional[str] = None,
        channel: Optional[str] = None,
        channel_like: Optional[str] = None,
        parking_name: Optional[str] = None,
        task_status: Optional[str] = None,
        task_status_in: Optional[str] = None,
        task_start_ts_gte: Optional[int] = None,
        task_start_ts_lte: Optional[int] = None,
        task_end_ts_gte: Optional[int] = None,
        task_end_ts_lte: Optional[int] = None,
        space_name: Optional[str] = None,
        change_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取所有快照，按通道分组，每个通道内按时间顺序排序（最早的在前）。
        
        返回格式:
        {
            "channels": [
                {
                    "channel_key": "10.10.11.123|c1",
                    "ip": "10.10.11.123",
                    "channel": "c1",
                    "parking_name": "车场名称",
                    "snapshots": [
                        {
                            "id": 1,
                            "screenshot_id": 100,
                            "image_url": "...",
                            "prev_image_url": "...",  # 上一张对比图
                            "detected_at": "...",
                            "change_count": 2,
                            "change_details": [...]
                        },
                        ...
                    ]
                },
                ...
            ]
        }
        """
        from models import Screenshot, Task
        
        # 处理 task_status_in
        task_status_list = None
        if task_status_in:
            task_status_list = [s.strip() for s in task_status_in.split(",") if s.strip()]
        
        # 获取按通道分组的快照
        grouped = self.repo.list_snapshots_by_channel_grouped(
            date=date,
            ip=ip,
            ip_like=ip_like,
            channel=channel,
            channel_like=channel_like,
            parking_name=parking_name,
            task_status=task_status,
            task_status_in=task_status_list,
            task_start_ts_gte=task_start_ts_gte,
            task_start_ts_lte=task_start_ts_lte,
            task_end_ts_gte=task_end_ts_gte,
            task_end_ts_lte=task_end_ts_lte,
            space_name=space_name,
            change_type=change_type,
        )
        
        channels_data = []
        for channel_key, snapshots in grouped.items():
            ip_val, channel_val = channel_key.split("|", 1) if "|" in channel_key else ("", "")
            
            snapshots_data = []
            for snap in snapshots:
                shot: Optional[Screenshot] = (
                    self.db.query(Screenshot).filter(Screenshot.id == snap.screenshot_id).first()
                )
                task: Optional[Task] = (
                    self.db.query(Task).filter(Task.id == snap.task_id).first()
                )
                
                # 当前截图URL
                image_url = _build_image_url(shot.file_path, prefer_detected=True) if shot and shot.file_path else ""
                
                # 获取上一张截图（按时间顺序）
                prev_screenshot = self.repo.get_prev_screenshot_for_snapshot(snap.id)
                prev_image_url = None
                if prev_screenshot:
                    prev_image_url = _build_image_url(prev_screenshot.file_path, prefer_detected=True)
                
                # 获取变化详情
                changes = self.repo.get_changes_by_snapshot_id(snap.id)
                change_details = []
                for change in changes:
                    if change.change_type in ("arrive", "leave"):
                        change_details.append({
                            "space_name": change.space_name or f"车位{change.space_id}",
                            "change_type": change.change_type,
                        })
                
                # 使用任务时间段（start_ts和end_ts），而不是detected_at
                task_time_range = None
                if task:
                    task_time_range = {
                        "start_ts": task.start_ts,
                        "end_ts": task.end_ts,
                    }
                
                snapshots_data.append({
                    "id": snap.id,
                    "screenshot_id": snap.screenshot_id,
                    "image_url": image_url,
                    "prev_image_url": prev_image_url,
                    "detected_at": snap.detected_at.isoformat() if snap.detected_at else None,  # 保留用于兼容
                    "task_time_range": task_time_range,  # 新增：任务时间段
                    "change_count": snap.change_count or 0,
                    "change_details": change_details,
                    "task_date": task.date if task else None,
                })
            
            # 获取通道的第一个快照的停车场名称和channel_config_id
            parking_name_val = snapshots[0].parking_name if snapshots else None
            channel_config_id = snapshots[0].channel_config_id if snapshots and snapshots[0].channel_config_id else None
            
            channels_data.append({
                "channel_key": channel_key,
                "ip": ip_val,
                "channel": channel_val,
                "parking_name": parking_name_val,
                "channel_config_id": channel_config_id,
                "snapshots": snapshots_data,
            })
        
        # 按通道排序（IP + 通道编码）
        channels_data.sort(key=lambda x: (x["ip"], x["channel"]))
        
        return {
            "channels": channels_data,
        }

    def list_changes_grouped_by_space(
        self,
        date: Optional[str] = None,
        ip: Optional[str] = None,
        ip_like: Optional[str] = None,
        channel: Optional[str] = None,
        channel_like: Optional[str] = None,
        parking_name: Optional[str] = None,
        task_status: Optional[str] = None,
        task_status_in: Optional[str] = None,
        task_start_ts_gte: Optional[int] = None,
        task_start_ts_lte: Optional[int] = None,
        task_end_ts_gte: Optional[int] = None,
        task_end_ts_lte: Optional[int] = None,
        space_name: Optional[str] = None,
        change_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取所有车位变化记录，按车位分组，每个车位内按时间顺序排序（最早的在前）。
        
        返回格式:
        {
            "spaces": [
                {
                    "space_id": 1,
                    "space_name": "GXSL001",
                    "channel": "c1",
                    "ip": "10.10.11.123",
                    "parking_name": "车场名称",
                    "changes": [
                        {
                            "id": 1,
                            "screenshot_id": 100,
                            "change_type": "arrive",
                            "prev_occupied": false,
                            "curr_occupied": true,
                            "detection_confidence": 0.95,
                            "detected_at": "...",
                            "image_url": "...",
                            "prev_image_url": "...",
                        },
                        ...
                    ]
                },
                ...
            ]
        }
        """
        from models import ParkingChange, Screenshot, Task, ParkingChangeSnapshot
        
        # 处理 task_status_in
        task_status_list = None
        if task_status_in:
            task_status_list = [s.strip() for s in task_status_in.split(",") if s.strip()]
        
        # 构建查询
        q = self.db.query(ParkingChange).join(
            Screenshot, ParkingChange.screenshot_id == Screenshot.id
        ).join(
            Task, Screenshot.task_id == Task.id
        )
        
        # 应用过滤条件
        if date:
            q = q.filter(Task.date == date)
        if ip:
            q = q.filter(Task.ip == ip)
        if ip_like:
            q = q.filter(Task.ip.like(f"%{ip_like}%"))
        if channel:
            q = q.filter(Task.channel == channel)
        if channel_like:
            q = q.filter(Task.channel.like(f"%{channel_like}%"))
        if parking_name:
            # parking_name 需要通过 ParkingChangeSnapshot 来获取
            from models import ParkingChangeSnapshot
            q = q.join(
                ParkingChangeSnapshot, 
                ParkingChangeSnapshot.screenshot_id == ParkingChange.screenshot_id
            ).filter(ParkingChangeSnapshot.parking_name.like(f"%{parking_name}%"))
        if task_status:
            q = q.filter(Task.status == task_status)
        if task_status_list:
            q = q.filter(Task.status.in_(task_status_list))
        if task_start_ts_gte:
            q = q.filter(Task.start_ts >= task_start_ts_gte)
        if task_start_ts_lte:
            q = q.filter(Task.start_ts <= task_start_ts_lte)
        if task_end_ts_gte:
            q = q.filter(Task.end_ts >= task_end_ts_gte)
        if task_end_ts_lte:
            q = q.filter(Task.end_ts <= task_end_ts_lte)
        if space_name:
            q = q.filter(ParkingChange.space_name.like(f"%{space_name}%"))
        if change_type:
            q = q.filter(ParkingChange.change_type == change_type)
        
        # 只获取有实际变化的记录（arrive 或 leave）
        q = q.filter(ParkingChange.change_type.in_(["arrive", "leave"]))
        
        # 按时间顺序排序
        changes = q.order_by(Screenshot.created_at.asc()).all()
        
        # 按车位分组
        grouped: Dict[str, List] = {}
        for change in changes:
            space_key = f"{change.space_id}|{change.space_name or ''}"
            if space_key not in grouped:
                grouped[space_key] = []
            grouped[space_key].append(change)
        
        spaces_data = []
        for space_key, space_changes in grouped.items():
            space_id_str, space_name_val = space_key.split("|", 1)
            space_id = int(space_id_str) if space_id_str.isdigit() else None
            
            # 获取第一个变化的通道信息（通过 Task 和 ParkingChangeSnapshot）
            first_change = space_changes[0]
            first_shot: Optional[Screenshot] = (
                self.db.query(Screenshot).filter(Screenshot.id == first_change.screenshot_id).first()
            )
            first_task: Optional[Task] = (
                self.db.query(Task).filter(Task.id == first_shot.task_id).first() if first_shot else None
            )
            # 获取 parking_name 和 channel_code 从 ParkingChangeSnapshot
            from models import ParkingChangeSnapshot
            first_snapshot: Optional[ParkingChangeSnapshot] = (
                self.db.query(ParkingChangeSnapshot)
                .filter(ParkingChangeSnapshot.screenshot_id == first_change.screenshot_id)
                .first()
            )
            
            changes_data = []
            for change in space_changes:
                shot: Optional[Screenshot] = (
                    self.db.query(Screenshot).filter(Screenshot.id == change.screenshot_id).first()
                )
                task: Optional[Task] = (
                    self.db.query(Task).filter(Task.id == shot.task_id).first() if shot else None
                )
                
                # 当前截图URL
                image_url = _build_image_url(shot.file_path, prefer_detected=True) if shot and shot.file_path else ""
                
                # 获取上一张截图（同一通道、同一IP）
                prev_screenshot = None
                if shot and task:
                    prev_shot = (
                        self.db.query(Screenshot)
                        .join(Task, Screenshot.task_id == Task.id)
                        .filter(
                            Task.channel == task.channel,
                            Task.ip == task.ip,
                            Screenshot.created_at < shot.created_at
                        )
                        .order_by(Screenshot.created_at.desc())
                        .first()
                    )
                    if prev_shot:
                        prev_screenshot = prev_shot
                
                prev_image_url = None
                if prev_screenshot:
                    prev_image_url = _build_image_url(prev_screenshot.file_path, prefer_detected=True)
                
                changes_data.append({
                    "id": change.id,
                    "screenshot_id": change.screenshot_id,
                    "change_type": change.change_type,
                    "prev_occupied": change.prev_occupied,
                    "curr_occupied": change.curr_occupied,
                    "detection_confidence": float(change.detection_confidence) if change.detection_confidence else None,
                    "detected_at": shot.created_at.isoformat() if shot and shot.created_at else None,
                    "image_url": image_url,
                    "prev_image_url": prev_image_url,
                    "task_date": task.date if task else None,
                })
            
            spaces_data.append({
                "space_id": space_id,
                "space_name": space_name_val or f"车位{space_id}",
                "channel": first_task.channel if first_task else (first_snapshot.channel_code if first_snapshot else None),
                "ip": first_task.ip if first_task else (first_snapshot.ip if first_snapshot else None),
                "parking_name": first_snapshot.parking_name if first_snapshot else None,
                "changes": changes_data,
            })
        
        # 按车位名称排序
        spaces_data.sort(key=lambda x: x["space_name"])
        
        return {
            "spaces": spaces_data,
        }
    
    def list_changes_grouped_by_channel_and_space(
        self,
        date: Optional[str] = None,
        ip: Optional[str] = None,
        ip_like: Optional[str] = None,
        channel: Optional[str] = None,
        channel_like: Optional[str] = None,
        parking_name: Optional[str] = None,
        task_status: Optional[str] = None,
        task_status_in: Optional[str] = None,
        task_start_ts_gte: Optional[int] = None,
        task_start_ts_lte: Optional[int] = None,
        task_end_ts_gte: Optional[int] = None,
        task_end_ts_lte: Optional[int] = None,
        space_name: Optional[str] = None,
        change_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """按通道分组，每个通道下显示所有车位及其在不同时间段的状态。
        
        返回格式:
        {
            "channels": [
                {
                    "channel": "c1",
                    "ip": "10.10.11.123",
                    "parking_name": "车场名称",
                    "spaces": [
                        {
                            "space_id": 1,
                            "space_name": "GXSL001",
                            "status_timeline": [
                                {
                                    "time": "2025-12-20T16:03:45",
                                    "occupied": true,
                                    "change_type": "arrive",
                                    "confidence": 0.95,
                                    "screenshot_id": 100,
                                    "image_url": "..."
                                },
                                ...
                            ]
                        },
                        ...
                    ]
                },
                ...
            ]
        }
        """
        from models import ParkingChange, Screenshot, Task, ParkingChangeSnapshot
        
        # 处理 task_status_in
        task_status_list = None
        if task_status_in:
            task_status_list = [s.strip() for s in task_status_in.split(",") if s.strip()]
        
        # 构建基础查询
        q = (
            self.db.query(ParkingChange)
            .join(Screenshot, ParkingChange.screenshot_id == Screenshot.id)
            .join(Task, Screenshot.task_id == Task.id)
        )
        
        # 应用过滤条件
        if date:
            q = q.filter(Task.date == date)
        if ip:
            q = q.filter(Task.ip == ip)
        if ip_like:
            q = q.filter(Task.ip.like(f"%{ip_like}%"))
        if channel:
            q = q.filter(Task.channel == channel)
        if channel_like:
            q = q.filter(Task.channel.like(f"%{channel_like}%"))
        if parking_name:
            from models import ParkingChangeSnapshot
            q = q.join(
                ParkingChangeSnapshot, 
                ParkingChangeSnapshot.screenshot_id == ParkingChange.screenshot_id
            ).filter(ParkingChangeSnapshot.parking_name.like(f"%{parking_name}%"))
        if task_status:
            q = q.filter(Task.status == task_status)
        if task_status_list:
            q = q.filter(Task.status.in_(task_status_list))
        if task_start_ts_gte:
            q = q.filter(Task.start_ts >= task_start_ts_gte)
        if task_start_ts_lte:
            q = q.filter(Task.start_ts <= task_start_ts_lte)
        if task_end_ts_gte:
            q = q.filter(Task.end_ts >= task_end_ts_gte)
        if task_end_ts_lte:
            q = q.filter(Task.end_ts <= task_end_ts_lte)
        if space_name:
            q = q.filter(ParkingChange.space_name.like(f"%{space_name}%"))
        if change_type:
            q = q.filter(ParkingChange.change_type == change_type)
        
        # 获取所有变化记录（包括所有状态，不仅仅是arrive/leave）
        changes = q.order_by(Screenshot.created_at.asc()).all()
        
        # 按通道分组，然后按车位分组
        # 结构: {channel_key: {space_key: [changes]}}
        channels_grouped: Dict[str, Dict[str, List]] = {}
        
        for change in changes:
            shot: Optional[Screenshot] = (
                self.db.query(Screenshot).filter(Screenshot.id == change.screenshot_id).first()
            )
            task: Optional[Task] = (
                self.db.query(Task).filter(Task.id == shot.task_id).first() if shot else None
            )
            
            if not task:
                continue
            
            # 通道键：IP + 通道
            channel_key = f"{task.ip}|{task.channel}"
            
            # 车位键：space_id + space_name
            space_key = f"{change.space_id}|{change.space_name or ''}"
            
            if channel_key not in channels_grouped:
                channels_grouped[channel_key] = {}
            
            if space_key not in channels_grouped[channel_key]:
                channels_grouped[channel_key][space_key] = []
            
            channels_grouped[channel_key][space_key].append(change)
        
        # 构建返回数据
        channels_data = []
        
        for channel_key, spaces_dict in channels_grouped.items():
            ip_val, channel_val = channel_key.split("|", 1)
            
            # 获取第一个变化记录的信息（用于获取parking_name等）
            first_space_key = list(spaces_dict.keys())[0] if spaces_dict else None
            first_change = spaces_dict[first_space_key][0] if first_space_key else None
            
            parking_name_val = None
            if first_change:
                first_snapshot: Optional[ParkingChangeSnapshot] = (
                    self.db.query(ParkingChangeSnapshot)
                    .filter(ParkingChangeSnapshot.screenshot_id == first_change.screenshot_id)
                    .first()
                )
                if first_snapshot:
                    parking_name_val = first_snapshot.parking_name
            
            spaces_data = []
            
            # 获取该通道下的所有任务（用于填充无变化的时间段）
            # 确定日期：优先使用传入的date参数，否则从第一个变化记录中获取
            task_date = date
            if not task_date and first_change:
                first_shot = (
                    self.db.query(Screenshot).filter(Screenshot.id == first_change.screenshot_id).first()
                )
                if first_shot:
                    first_task = (
                        self.db.query(Task).filter(Task.id == first_shot.task_id).first()
                    )
                    if first_task:
                        task_date = first_task.date
            
            all_tasks_query = self.db.query(Task)
            if task_date:
                all_tasks_query = all_tasks_query.filter(Task.date == task_date)
            if ip_val:
                all_tasks_query = all_tasks_query.filter(Task.ip == ip_val)
            if channel_val:
                all_tasks_query = all_tasks_query.filter(Task.channel == channel_val)
            if task_status:
                all_tasks_query = all_tasks_query.filter(Task.status == task_status)
            if task_status_list:
                all_tasks_query = all_tasks_query.filter(Task.status.in_(task_status_list))
            all_tasks = all_tasks_query.order_by(Task.start_ts.asc()).all()
            
            # 构建任务时间段映射 {task_key: task}
            tasks_map = {}
            for task in all_tasks:
                task_key = f"{task.start_ts}_{task.end_ts}"
                tasks_map[task_key] = task
            
            for space_key, space_changes in spaces_dict.items():
                space_id_str, space_name_val = space_key.split("|", 1)
                space_id = int(space_id_str) if space_id_str.isdigit() else None
                
                # 构建变化记录的时间段映射 {task_key: change}
                changes_by_task = {}
                for change in space_changes:
                    shot: Optional[Screenshot] = (
                        self.db.query(Screenshot).filter(Screenshot.id == change.screenshot_id).first()
                    )
                    if not shot:
                        continue
                    task: Optional[Task] = (
                        self.db.query(Task).filter(Task.id == shot.task_id).first() if shot.task_id else None
                    )
                    if task:
                        task_key = f"{task.start_ts}_{task.end_ts}"
                        changes_by_task[task_key] = {
                            "change": change,
                            "shot": shot,
                            "task": task,
                        }
                
                # 构建完整的时间线（包括有变化和无变化的时间段）
                status_timeline = []
                
                # 遍历所有任务时间段
                for task in all_tasks:
                    task_key = f"{task.start_ts}_{task.end_ts}"
                    change_info = changes_by_task.get(task_key)
                    
                    if change_info:
                        # 找到了该时间段的状态记录
                        change = change_info["change"]
                        shot = change_info["shot"]
                        image_url = _build_image_url(shot.file_path, prefer_detected=True) if shot and shot.file_path else ""
                        
                        # 只有当 change_type 不为 None 时，才表示有变化
                        # change_type 为 None 表示无变化（状态未改变或第一张图）
                        has_change = change.change_type is not None and change.change_type in ("arrive", "leave", "unknown")
                        
                        status_timeline.append({
                            "time": {
                                "start_ts": task.start_ts,
                                "end_ts": task.end_ts,
                            },
                            "occupied": change.curr_occupied,
                            "prev_occupied": change.prev_occupied,  # 添加前一个状态
                            "change_type": change.change_type,
                            "confidence": float(change.detection_confidence) if change.detection_confidence else None,
                            "screenshot_id": change.screenshot_id,
                            "image_url": image_url,
                            "has_change": has_change,  # 根据 change_type 判断是否有变化
                        })
                    else:
                        # 无变化的时间段 - 需要获取该时间段的状态
                        # 查找该时间段是否有截图，如果有，获取该车位的状态
                        shot = (
                            self.db.query(Screenshot)
                            .filter(Screenshot.task_id == task.id)
                            .first()
                        )
                        
                        if shot:
                            # 查找该截图下该车位的状态（可能没有变化记录，但有状态记录）
                            space_status = (
                                self.db.query(ParkingChange)
                                .filter(
                                    ParkingChange.screenshot_id == shot.id,
                                    ParkingChange.space_id == space_id
                                )
                                .first()
                            )
                            
                            if space_status:
                                # 有状态记录，但无变化
                                image_url = _build_image_url(shot.file_path, prefer_detected=True) if shot.file_path else ""
                                status_timeline.append({
                                    "time": {
                                        "start_ts": task.start_ts,
                                        "end_ts": task.end_ts,
                                    },
                                    "occupied": space_status.curr_occupied,
                                    "prev_occupied": space_status.prev_occupied,  # 添加前一个状态
                                    "change_type": None,  # 无变化
                                    "confidence": float(space_status.detection_confidence) if space_status.detection_confidence else None,
                                    "screenshot_id": shot.id,
                                    "image_url": image_url,
                                    "has_change": False,  # 标记无变化
                                })
                            else:
                                # 没有状态记录，可能是该时间段没有截图或未检测
                                status_timeline.append({
                                    "time": {
                                        "start_ts": task.start_ts,
                                        "end_ts": task.end_ts,
                                    },
                                    "occupied": None,
                                    "change_type": None,
                                    "confidence": None,
                                    "screenshot_id": None,
                                    "image_url": None,
                                    "has_change": False,
                                })
                        else:
                            # 没有截图
                            status_timeline.append({
                                "time": {
                                    "start_ts": task.start_ts,
                                    "end_ts": task.end_ts,
                                },
                                "occupied": None,
                                "change_type": None,
                                "confidence": None,
                                "screenshot_id": None,
                                "image_url": None,
                                "has_change": False,
                            })
                
                spaces_data.append({
                    "space_id": space_id,
                    "space_name": space_name_val or f"车位{space_id}",
                    "status_timeline": status_timeline,
                })
            
            # 按车位名称排序
            spaces_data.sort(key=lambda x: x["space_name"])
            
            channels_data.append({
                "channel": channel_val,
                "ip": ip_val,
                "parking_name": parking_name_val,
                "spaces": spaces_data,
            })
        
        # 按通道排序（IP + 通道编码）
        channels_data.sort(key=lambda x: (x["ip"], x["channel"]))
        
        return {
            "channels": channels_data,
        }
    
    def get_channel_analysis_report(
        self,
        channel_config_id: int,
        date: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """生成通道的详细对比分析报告。
        
        返回格式：
        {
            "channel_info": {...},
            "time_sequence": [...],
            "space_layout": [...],
            "comparison_table": [...],
            "event_timeline": [...],
            "statistics": {...},
            "conclusion": "..."
        }
        """
        from models import (
            ParkingChangeSnapshot, Screenshot, Task, ChannelConfig, ParkingSpace, ParkingChange
        )
        from sqlalchemy import and_
        
        # 获取通道信息
        channel_config = (
            self.db.query(ChannelConfig)
            .filter(ChannelConfig.id == channel_config_id)
            .first()
        )
        if not channel_config:
            return {}
        
        # 获取所有车位
        spaces = (
            self.db.query(ParkingSpace)
            .filter(ParkingSpace.channel_config_id == channel_config_id)
            .order_by(ParkingSpace.space_name.asc())
            .all()
        )
        
        # 获取该通道的所有快照（按时间排序）
        query = (
            self.db.query(ParkingChangeSnapshot)
            .filter(ParkingChangeSnapshot.channel_config_id == channel_config_id)
        )
        
        if date:
            query = query.join(Task, ParkingChangeSnapshot.task_id == Task.id).filter(Task.date == date)
        
        snapshots = (
            query.join(Screenshot, ParkingChangeSnapshot.screenshot_id == Screenshot.id)
            .order_by(Screenshot.created_at.asc())
            .limit(limit)
            .all()
        )
        
        if not snapshots:
            return {
                "channel_info": {
                    "id": channel_config.id,
                    "channel_code": channel_config.channel_code,
                    "parking_name": channel_config.parking_name if hasattr(channel_config, 'parking_name') else None,
                },
                "time_sequence": [],
                "space_layout": [],
                "comparison_table": [],
                "event_timeline": [],
                "statistics": {
                    "total_spaces": len(spaces),
                    "total_snapshots": 0,
                    "spaces_with_changes": 0,
                    "total_entries": 0,
                    "total_exits": 0,
                },
                "conclusion": "暂无数据",
            }
        
        # 构建时间序列
        time_sequence = []
        for idx, snap in enumerate(snapshots):
            shot = self.db.query(Screenshot).filter(Screenshot.id == snap.screenshot_id).first()
            if shot and shot.created_at:
                time_sequence.append({
                    "frame_label": f"Frame {chr(65 + idx)}",  # A, B, C, ...
                    "timestamp": shot.created_at.isoformat(),
                    "display_time": shot.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "snapshot_id": snap.id,
                    "screenshot_id": snap.screenshot_id,
                })
        
        # 构建车位布局
        space_layout = [
            {
                "space_id": space.id,
                "space_name": space.space_name,
                "position": idx + 1,
            }
            for idx, space in enumerate(spaces)
        ]
        
        # 构建对比表：每个车位在每个时间点的状态
        # 注意：这里只使用有快照的截图（有变化的），但对比逻辑应该包含所有被处理过的截图
        # 为了完整展示，我们需要获取所有被处理过的截图（不仅仅是快照）
        comparison_table = []
        for space in spaces:
            space_row = {
                "space_id": space.id,
                "space_name": space.space_name,
                "frames": [],
            }
            
            # 获取该车位在所有快照中的状态
            for snap in snapshots:
                # 获取该快照下该车位的变化记录
                change = (
                    self.db.query(ParkingChange)
                    .filter(
                        ParkingChange.screenshot_id == snap.screenshot_id,
                        ParkingChange.space_id == space.id,
                    )
                    .first()
                )
                
                if change:
                    occupied = change.curr_occupied
                    change_type = change.change_type
                    confidence = change.detection_confidence
                else:
                    # 如果没有变化记录，说明该快照时该车位没有变化
                    # 需要查找该快照对应的截图，然后查找该截图下该车位的状态
                    shot = self.db.query(Screenshot).filter(Screenshot.id == snap.screenshot_id).first()
                    if shot:
                        # 查找该截图下该车位的所有变化记录（可能没有变化，所以没有快照）
                        all_changes = (
                            self.db.query(ParkingChange)
                            .filter(
                                ParkingChange.screenshot_id == shot.id,
                                ParkingChange.space_id == space.id,
                            )
                            .all()
                        )
                        if all_changes:
                            # 找到记录，使用最新的
                            change = all_changes[0]
                            occupied = change.curr_occupied
                            change_type = change.change_type
                            confidence = change.detection_confidence
                        else:
                            # 没有记录，可能该截图还未处理，标记为未知
                            occupied = None
                            change_type = None
                            confidence = None
                    else:
                        occupied = None
                        change_type = None
                        confidence = None
                
                space_row["frames"].append({
                    "snapshot_id": snap.id,
                    "occupied": occupied,
                    "change_type": change_type,
                    "confidence": confidence,
                })
            
            comparison_table.append(space_row)
        
        # 构建事件时间线
        # 注意：只对比相邻的快照，确保时间顺序（不能跳过中间的截图）
        event_timeline = []
        for i in range(len(snapshots) - 1):
            prev_snap = snapshots[i]
            curr_snap = snapshots[i + 1]
            
            prev_shot = self.db.query(Screenshot).filter(Screenshot.id == prev_snap.screenshot_id).first()
            curr_shot = self.db.query(Screenshot).filter(Screenshot.id == curr_snap.screenshot_id).first()
            
            if not prev_shot or not curr_shot or not prev_shot.created_at or not curr_shot.created_at:
                continue
            
            # 检查时间间隔（确保不跳过中间的截图）
            time_gap = (curr_shot.created_at - prev_shot.created_at).total_seconds()
            if time_gap > 900:  # 超过15分钟，说明跳过了中间的截图
                # 跳过这个时间窗口，不记录事件
                print(f"[ParkingChangeService] 警告: 快照时间间隔过大 ({time_gap:.0f}秒 > 900秒)，跳过事件时间线。从: {prev_shot.created_at}, 到: {curr_shot.created_at}")
                continue
            
            time_window = {
                "from": prev_shot.created_at.isoformat(),
                "to": curr_shot.created_at.isoformat(),
                "from_display": prev_shot.created_at.strftime("%H:%M:%S"),
                "to_display": curr_shot.created_at.strftime("%H:%M:%S"),
                "events": [],
            }
            
            # 查找这个时间段内的所有变化
            for space in spaces:
                prev_change = (
                    self.db.query(ParkingChange)
                    .filter(
                        ParkingChange.screenshot_id == prev_snap.screenshot_id,
                        ParkingChange.space_id == space.id,
                    )
                    .first()
                )
                curr_change = (
                    self.db.query(ParkingChange)
                    .filter(
                        ParkingChange.screenshot_id == curr_snap.screenshot_id,
                        ParkingChange.space_id == space.id,
                    )
                    .first()
                )
                
                prev_occupied = prev_change.curr_occupied if prev_change else None
                curr_occupied = curr_change.curr_occupied if curr_change else None
                
                if prev_occupied is not None and curr_occupied is not None:
                    if prev_occupied != curr_occupied:
                        event_type = "entry" if not prev_occupied and curr_occupied else "exit"
                        time_window["events"].append({
                            "space_id": space.id,
                            "space_name": space.space_name,
                            "event_type": event_type,
                            "from_state": "空位" if not prev_occupied else "有车",
                            "to_state": "有车" if curr_occupied else "空位",
                        })
            
            if time_window["events"]:
                event_timeline.append(time_window)
        
        # 统计信息
        total_entries = sum(
            1 for timeline in event_timeline
            for event in timeline["events"]
            if event["event_type"] == "entry"
        )
        total_exits = sum(
            1 for timeline in event_timeline
            for event in timeline["events"]
            if event["event_type"] == "exit"
        )
        
        spaces_with_changes = len([
            row for row in comparison_table
            if any(frame.get("change_type") in ("arrive", "leave") for frame in row["frames"])
        ])
        
        # 生成结论
        conclusion_parts = []
        if len(snapshots) > 0:
            conclusion_parts.append(f"在 {len(snapshots)} 张截图覆盖的时间段内：")
        if spaces_with_changes > 0:
            conclusion_parts.append(f"共有 {spaces_with_changes} 个车位发生了车辆变化；")
        if total_entries > 0:
            conclusion_parts.append(f"车辆入场 {total_entries} 次；")
        if total_exits > 0:
            conclusion_parts.append(f"车辆离场 {total_exits} 次。")
        if spaces_with_changes == 0:
            conclusion_parts.append("所有车位均无变化。")
        
        conclusion = " ".join(conclusion_parts) if conclusion_parts else "暂无变化数据。"
        
        return {
            "channel_info": {
                "id": channel_config.id,
                "channel_code": channel_config.channel_code,
                "parking_name": getattr(channel_config, 'parking_name', None),
            },
            "time_sequence": time_sequence,
            "space_layout": space_layout,
            "comparison_table": comparison_table,
            "event_timeline": event_timeline,
            "statistics": {
                "total_spaces": len(spaces),
                "total_snapshots": len(snapshots),
                "spaces_with_changes": spaces_with_changes,
                "total_entries": total_entries,
                "total_exits": total_exits,
            },
            "conclusion": conclusion,
        }
    
    def get_status_label(self, task: Optional[Task], shot: Optional[Screenshot]) -> Tuple[Optional[str], Optional[str]]:
        """
        根据任务状态和截图情况确定显示状态标签（与图片列表保持一致）
        
        返回: (status_label, status_label_display)
        status_label: None=正常显示, "pending"=待截图, "playing"=截图中, "missing"=文件缺失, "failed"=截图失败
        status_label_display: 中文显示文本
        """
        if not task:
            return None, None
        
        task_status = task.status or "pending"
        status_label = None
        status_label_display = None
        
        if shot:
            # 有截图记录
            p = Path(shot.file_path)
            missing = not (SCREENSHOT_BASE / p if not p.is_absolute() else p).exists()
            if missing:
                status_label = "missing"
                status_label_display = "文件缺失"
        else:
            # 没有截图记录，根据任务状态判断
            if task_status == "pending":
                status_label = "pending"
                status_label_display = "待截图"
            elif task_status == "playing":
                status_label = "playing"
                status_label_display = "截图中"
            elif task_status == "failed":
                # 任务失败但没有任何截图记录，更合理地视为"暂无截图/缺失"
                status_label = "missing"
                status_label_display = "文件缺失"
        
        return status_label, status_label_display

