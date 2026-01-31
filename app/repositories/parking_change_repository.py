"""车位变化数据访问层（Repository）"""

from __future__ import annotations

from typing import List, Optional, Tuple, Dict

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from models import ParkingChangeSnapshot, ParkingChange


class ParkingChangeRepository:
    """车位变化相关数据库操作"""

    def __init__(self, db: Session):
        self.db = db

    def list_snapshots(
        self,
        date: Optional[str] = None,
        ip: Optional[str] = None,
        ip_like: Optional[str] = None,
        channel: Optional[str] = None,
        channel_like: Optional[str] = None,
        parking_name: Optional[str] = None,
        task_status: Optional[str] = None,
        task_status_in: Optional[List[str]] = None,
        task_start_ts_gte: Optional[int] = None,
        task_start_ts_lte: Optional[int] = None,
        task_end_ts_gte: Optional[int] = None,
        task_end_ts_lte: Optional[int] = None,
        space_name: Optional[str] = None,
        change_type: Optional[str] = None,
        name_eq: Optional[str] = None,
        name_like: Optional[str] = None,
        status_label: Optional[str] = None,
        status_label_in: Optional[List[str]] = None,
        missing: Optional[bool] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ParkingChangeSnapshot], int]:
        """分页查询变化快照列表（支持与图片列表类似的搜索条件）。"""
        from models import Task  # 避免循环导入
        from sqlalchemy import or_, and_
        
        # 基础查询：通过 Task 关联查询
        q = self.db.query(ParkingChangeSnapshot).join(Task, Task.id == ParkingChangeSnapshot.task_id)

        # 日期过滤
        if date:
            q = q.filter(Task.date == date)

        # IP 过滤（精准/模糊）
        if ip:
            q = q.filter(ParkingChangeSnapshot.ip == ip.strip())
        elif ip_like:
            q = q.filter(ParkingChangeSnapshot.ip.like(f"%{ip_like.strip()}%"))

        # 通道过滤（精准/模糊）
        if channel:
            ch = channel.strip().lower()
            if not ch.startswith("c"):
                ch = f"c{ch}"
            q = q.filter(ParkingChangeSnapshot.channel_code == ch)
        elif channel_like:
            ch_like = channel_like.strip().lower()
            if not ch_like.startswith("c"):
                ch_like = f"c{ch_like}"
            q = q.filter(ParkingChangeSnapshot.channel_code.like(f"%{ch_like}%"))

        # 车场名称过滤
        if parking_name:
            q = q.filter(ParkingChangeSnapshot.parking_name.like(f"%{parking_name.strip()}%"))

        # 任务状态过滤
        if task_status:
            q = q.filter(Task.status == task_status.strip())
        elif task_status_in:
            q = q.filter(Task.status.in_(task_status_in))

        # 任务时间戳范围过滤
        if task_start_ts_gte is not None:
            q = q.filter(Task.start_ts >= task_start_ts_gte)
        if task_start_ts_lte is not None:
            q = q.filter(Task.start_ts <= task_start_ts_lte)
        if task_end_ts_gte is not None:
            q = q.filter(Task.end_ts >= task_end_ts_gte)
        if task_end_ts_lte is not None:
            q = q.filter(Task.end_ts <= task_end_ts_lte)

        # 车位名称过滤（需要通过 ParkingChange 关联）
        if space_name:
            from sqlalchemy import exists
            q = q.filter(
                exists().where(
                    and_(
                        ParkingChange.screenshot_id == ParkingChangeSnapshot.screenshot_id,
                        ParkingChange.space_name.like(f"%{space_name.strip()}%")
                    )
                )
            )

        # 变化类型过滤（需要通过 ParkingChange 关联）
        if change_type:
            from sqlalchemy import exists
            q = q.filter(
                exists().where(
                    and_(
                        ParkingChange.screenshot_id == ParkingChangeSnapshot.screenshot_id,
                        ParkingChange.change_type == change_type.strip()
                    )
                )
            )

        total = q.count()
        items = (
            q.order_by(desc(ParkingChangeSnapshot.detected_at))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def get_changes_by_snapshot_id(self, snapshot_id: int) -> List[ParkingChange]:
        """获取某次快照下的所有车位变化记录。"""
        # 先通过 snapshot_id 获取对应的 screenshot_id
        snapshot = (
            self.db.query(ParkingChangeSnapshot)
            .filter(ParkingChangeSnapshot.id == snapshot_id)
            .first()
        )
        if not snapshot:
            return []
        
        # 通过 screenshot_id 查询所有相关的车位变化记录
        return (
            self.db.query(ParkingChange)
            .filter(ParkingChange.screenshot_id == snapshot.screenshot_id)
            .all()
        )
    
    def get_prev_screenshot_for_snapshot(self, snapshot_id: int, max_time_gap_seconds: int = 900):
        """获取某个快照对应的上一张截图（同一通道，按截图时间连续比较，不能跳过中间的截图）。

        逻辑说明：
        - 严格按照时间顺序查找上一张截图，不能跳过中间的截图
        - 如果时间间隔超过 max_time_gap_seconds（默认15分钟），返回 None
        - 这样可以确保：10:00对比10:10，10:10对比10:20，10:20对比10:30
        - 不会出现10:00直接对比10:30的情况（中间跳过了10:10和10:20）

        返回: Screenshot 对象或 None
        """
        from models import Screenshot  # 避免循环导入

        # 当前快照
        snapshot = (
            self.db.query(ParkingChangeSnapshot)
            .filter(ParkingChangeSnapshot.id == snapshot_id)
            .first()
        )
        if not snapshot:
            return None

        current_screenshot_id = snapshot.screenshot_id
        channel_config_id = snapshot.channel_config_id

        # 获取当前截图的时间（必须）
        current_screenshot = (
            self.db.query(Screenshot)
            .filter(Screenshot.id == current_screenshot_id)
            .first()
        )
        if not current_screenshot or not current_screenshot.created_at:
            return None
        
        current_screenshot_time = current_screenshot.created_at
        
        # 方法1：优先查找上一条快照（如果有变化，会生成快照）
        # 按时间顺序查找：找到当前截图时间之前最近的一张快照
        prev_snapshot = (
            self.db.query(ParkingChangeSnapshot)
            .join(Screenshot, ParkingChangeSnapshot.screenshot_id == Screenshot.id)
            .filter(
                ParkingChangeSnapshot.channel_config_id == channel_config_id,
                Screenshot.created_at < current_screenshot_time,
            )
            .order_by(desc(Screenshot.created_at))
            .first()
        )
        
        if prev_snapshot:
            # 检查时间间隔
            prev_screenshot = (
                self.db.query(Screenshot)
                .filter(Screenshot.id == prev_snapshot.screenshot_id)
                .first()
            )
            if prev_screenshot and prev_screenshot.created_at:
                time_gap = (current_screenshot_time - prev_screenshot.created_at).total_seconds()
                if time_gap <= max_time_gap_seconds:
                    return prev_screenshot
                else:
                    # 时间间隔过大，跳过
                    print(f"[ParkingChangeRepository] 警告: 快照时间间隔过大 ({time_gap:.0f}秒 > {max_time_gap_seconds}秒)，跳过对比。当前: {current_screenshot_time}, 上一张: {prev_screenshot.created_at}")
                    return None

        # 方法2：如果找不到上一条快照，通过 ParkingChange 表查找上一张截图
        # （即使上一张截图没有变化、未生成快照，只要被处理过就会有 ParkingChange 记录）
        # 按时间顺序查找：找到当前截图时间之前最近的一张截图
        prev_change = (
            self.db.query(ParkingChange)
            .join(Screenshot, ParkingChange.screenshot_id == Screenshot.id)
            .filter(
                ParkingChange.channel_config_id == channel_config_id,
                Screenshot.created_at < current_screenshot_time,
            )
            .order_by(desc(Screenshot.created_at))
            .first()
        )
        
        if prev_change:
            prev_screenshot = (
                self.db.query(Screenshot)
                .filter(Screenshot.id == prev_change.screenshot_id)
                .first()
            )
            if prev_screenshot and prev_screenshot.created_at:
                # 检查时间间隔
                time_gap = (current_screenshot_time - prev_screenshot.created_at).total_seconds()
                if time_gap <= max_time_gap_seconds:
                    return prev_screenshot
                else:
                    # 时间间隔过大，跳过
                    print(f"[ParkingChangeRepository] 警告: 截图时间间隔过大 ({time_gap:.0f}秒 > {max_time_gap_seconds}秒)，跳过对比。当前: {current_screenshot_time}, 上一张: {prev_screenshot.created_at}")
                    return None

        # 如果都找不到，说明这是第一张截图
        return None
    
    def list_snapshots_by_channel_grouped(
        self,
        date: Optional[str] = None,
        ip: Optional[str] = None,
        ip_like: Optional[str] = None,
        channel: Optional[str] = None,
        channel_like: Optional[str] = None,
        parking_name: Optional[str] = None,
        task_status: Optional[str] = None,
        task_status_in: Optional[List[str]] = None,
        task_start_ts_gte: Optional[int] = None,
        task_start_ts_lte: Optional[int] = None,
        task_end_ts_gte: Optional[int] = None,
        task_end_ts_lte: Optional[int] = None,
        space_name: Optional[str] = None,
        change_type: Optional[str] = None,
    ) -> Dict[str, List[ParkingChangeSnapshot]]:
        """获取所有快照，按通道分组，每个通道内按时间顺序排序（最早的在前）。
        
        返回: {channel_key: [snapshot1, snapshot2, ...]}
        channel_key 格式: "{ip}|{channel_code}"
        """
        from models import ParkingChangeSnapshot, Screenshot, Task
        
        q = self.db.query(ParkingChangeSnapshot)
        
        # 应用过滤条件（与 list_snapshots 类似）
        if date:
            q = q.join(Task, ParkingChangeSnapshot.task_id == Task.id).filter(Task.date == date)
        
        if ip:
            q = q.filter(ParkingChangeSnapshot.ip == ip)
        if ip_like:
            q = q.filter(ParkingChangeSnapshot.ip.like(f"%{ip_like}%"))
        
        if channel:
            q = q.filter(ParkingChangeSnapshot.channel_code == channel.strip().lower())
        if channel_like:
            q = q.filter(ParkingChangeSnapshot.channel_code.like(f"%{channel_like.strip().lower()}%"))
        
        if parking_name:
            q = q.filter(ParkingChangeSnapshot.parking_name.like(f"%{parking_name}%"))
        
        if task_status:
            q = q.join(Task, ParkingChangeSnapshot.task_id == Task.id).filter(Task.status == task_status)
        if task_status_in:
            q = q.join(Task, ParkingChangeSnapshot.task_id == Task.id).filter(Task.status.in_(task_status_in))
        
        if task_start_ts_gte:
            q = q.join(Task, ParkingChangeSnapshot.task_id == Task.id).filter(Task.start_ts >= task_start_ts_gte)
        if task_start_ts_lte:
            q = q.join(Task, ParkingChangeSnapshot.task_id == Task.id).filter(Task.start_ts <= task_start_ts_lte)
        if task_end_ts_gte:
            q = q.join(Task, ParkingChangeSnapshot.task_id == Task.id).filter(Task.end_ts >= task_end_ts_gte)
        if task_end_ts_lte:
            q = q.join(Task, ParkingChangeSnapshot.task_id == Task.id).filter(Task.end_ts <= task_end_ts_lte)
        
        if change_type:
            from sqlalchemy import exists
            q = q.filter(
                exists().where(
                    and_(
                        ParkingChange.screenshot_id == ParkingChangeSnapshot.screenshot_id,
                        ParkingChange.change_type == change_type.strip()
                    )
                )
            )
        
        # 按时间顺序排序（最早的在前）
        snapshots = (
            q.join(Screenshot, ParkingChangeSnapshot.screenshot_id == Screenshot.id)
            .order_by(Screenshot.created_at.asc())
            .all()
        )
        
        # 按通道分组
        grouped: Dict[str, List[ParkingChangeSnapshot]] = {}
        for snap in snapshots:
            ip_val = snap.ip or ""
            channel_val = snap.channel_code or ""
            channel_key = f"{ip_val}|{channel_val}"
            
            if channel_key not in grouped:
                grouped[channel_key] = []
            grouped[channel_key].append(snap)
        
        return grouped

