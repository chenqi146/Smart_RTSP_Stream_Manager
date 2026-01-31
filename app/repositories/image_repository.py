"""图片数据访问层（Repository Pattern）"""
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from pathlib import Path

from models import Task, Screenshot


class ImageRepository:
    """图片数据访问仓库"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== 基础查询操作 ====================
    
    def get_latest_screenshot_by_task_id(self, task_id: int) -> Optional[Screenshot]:
        """获取任务的最新截图"""
        return (
            self.db.query(Screenshot)
            .filter(Screenshot.task_id == task_id)
            .order_by(Screenshot.id.desc())
            .first()
        )
    
    def get_screenshots_by_task_ids(self, task_ids: List[int]) -> List[Screenshot]:
        """批量获取任务的截图"""
        return (
            self.db.query(Screenshot)
            .filter(Screenshot.task_id.in_(task_ids))
            .all()
        )
    
    def get_available_dates_from_db(self) -> Dict[str, int]:
        """
        从数据库获取有截图的日期列表及其数量
        返回: {date: count}
        """
        dates: Dict[str, int] = {}
        rows = (
            self.db.query(Task.date, Screenshot.id)
            .join(Screenshot, Screenshot.task_id == Task.id)
            .all()
        )
        for date, _ in rows:
            dates[date] = dates.get(date, 0) + 1
        return dates
    
    def get_tasks_with_filters(
        self,
        date: Optional[str] = None,
        task_ip: Optional[str] = None,
        task_ip_like: Optional[str] = None,
        task_channel: Optional[str] = None,
        task_channel_like: Optional[str] = None,
        task_status: Optional[str] = None,
        task_status_in: Optional[List[str]] = None,
        task_start_ts_gte: Optional[int] = None,
        task_start_ts_lte: Optional[int] = None,
        task_end_ts_gte: Optional[int] = None,
        task_end_ts_lte: Optional[int] = None,
    ) -> List[Task]:
        """
        根据过滤条件获取任务列表
        用于图片查询的场景
        """
        query = self.db.query(Task)
        
        # 日期过滤
        if date:
            query = query.filter(Task.date == date)
        
        # IP地址搜索
        if task_ip:
            ip_clean = task_ip.strip()
            query = query.filter(
                or_(
                    Task.ip == ip_clean,
                    and_(Task.ip.is_(None), Task.rtsp_url.ilike(f"%@{ip_clean}%")),
                )
            )
        elif task_ip_like:
            ip_like_val = task_ip_like.strip()
            query = query.filter(
                or_(
                    Task.ip.ilike(f"%{ip_like_val}%"),
                    Task.rtsp_url.ilike(f"%@{ip_like_val}%"),
                )
            )
        
        # 通道搜索（支持"通道+摄像头名称"格式，如 "C1 高新四路9号枪机"）
        if task_channel:
            import re
            ch_display = task_channel.strip()
            # 从显示名称中解析出 channel_code（如从 "C1 高新四路9号枪机" 解析出 "c1"）
            match = re.match(r'^([cC]\d+)', ch_display)
            channel_clean = match.group(1).lower() if match else ch_display.lower()
            if not channel_clean.startswith("c"):
                channel_clean = f"c{channel_clean}"
            if channel_clean.startswith("/"):
                channel_clean = channel_clean.strip("/")
            query = query.filter(
                or_(
                    Task.channel == channel_clean,
                    and_(Task.channel.is_(None), Task.rtsp_url.ilike(f"%/{channel_clean}/%")),
                )
            )
        elif task_channel_like:
            import re
            ch_display = task_channel_like.strip()
            # 从显示名称中解析出 channel_code
            match = re.match(r'^([cC]\d+)', ch_display)
            ch_like = match.group(1).lower() if match else ch_display.lower()
            if not ch_like.startswith("c"):
                ch_like = f"c{ch_like}"
            query = query.filter(
                or_(
                    Task.channel.ilike(f"%{ch_like}%"),
                    Task.rtsp_url.ilike(f"%/{ch_like}%"),
                )
            )
        
        # 任务状态搜索
        if task_status:
            query = query.filter(Task.status == task_status.strip())
        elif task_status_in:
            if task_status_in:
                query = query.filter(Task.status.in_(task_status_in))
        
        # 时间戳范围搜索
        if task_start_ts_gte is not None:
            query = query.filter(Task.start_ts >= task_start_ts_gte)
        if task_start_ts_lte is not None:
            query = query.filter(Task.start_ts <= task_start_ts_lte)
        if task_end_ts_gte is not None:
            query = query.filter(Task.end_ts >= task_end_ts_gte)
        if task_end_ts_lte is not None:
            query = query.filter(Task.end_ts <= task_end_ts_lte)
        
        return query.order_by(Task.index).all()
    
    def get_screenshot_dict_by_task_ids(self, task_ids: List[int]) -> Dict[int, Screenshot]:
        """
        批量获取任务的截图，返回 {task_id: latest_screenshot}
        """
        screenshots = self.get_screenshots_by_task_ids(task_ids)
        result: Dict[int, Screenshot] = {}
        # 只保留每个任务的最新截图
        for shot in screenshots:
            if shot.task_id not in result or shot.id > result[shot.task_id].id:
                result[shot.task_id] = shot
        return result

    # ==================== OCR 相关查询 ====================

    # OCR功能已移除，get_ocr_dict_by_screenshot_ids方法已废弃

    def get_latest_screenshot_with_ocr_by_task_id(
        self, task_id: int
    ) -> Optional[Tuple[Screenshot, None]]:
        """获取指定任务最新的一张截图及其 OCR 结果（如果有）。"""
        # OCR功能已移除，只返回截图记录
        row = (
            self.db.query(Screenshot)
            .filter(Screenshot.task_id == task_id)
            .order_by(Screenshot.id.desc())
            .first()
        )
        if not row:
            return None
        return row, None


