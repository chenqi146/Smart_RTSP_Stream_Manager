"""任务数据访问层（Repository Pattern）"""
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import datetime
import re

from models import Task, Screenshot
from schemas.tasks import TaskSegment


class TaskRepository:
    """任务数据访问仓库"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== 基础 CRUD 操作 ====================
    
    def get_by_id(self, task_id: int) -> Optional[Task]:
        """根据 ID 获取任务"""
        return self.db.query(Task).filter(Task.id == task_id).first()
    
    def get_by_date_and_timestamps(
        self, 
        date: str, 
        start_ts: int, 
        end_ts: int, 
        channel: Optional[str] = None,
        ip: Optional[str] = None
    ) -> Optional[Task]:
        """
        根据日期和时间戳获取任务（支持多种匹配策略）
        
        匹配优先级：
        1. date + start_ts + end_ts + channel
        2. date + start_ts + end_ts + ip
        3. date + start_ts + end_ts
        """
        query = self.db.query(Task).filter(
            Task.date == date,
            Task.start_ts == start_ts,
            Task.end_ts == end_ts
        )
        
        if channel:
            query = query.filter(
                or_(
                    Task.channel == channel,
                    and_(Task.channel.is_(None), Task.rtsp_url.ilike(f"%/{channel}/%"))
                )
            )
            result = query.first()
            if result:
                return result
        
        if ip:
            query = self.db.query(Task).filter(
                Task.date == date,
                Task.start_ts == start_ts,
                Task.end_ts == end_ts,
                or_(
                    Task.ip == ip,
                    and_(Task.ip.is_(None), Task.rtsp_url.ilike(f"%@{ip}%"))
                )
            )
            result = query.first()
            if result:
                return result
        
        # 如果channel和ip都提供了但都没匹配到，不应该返回没有过滤的结果（避免通道混淆）
        # 只有在都没有提供的情况下，才返回基础查询结果
        if channel is None and ip is None:
            return query.first()
        else:
            # 如果提供了channel或ip但没匹配到，返回None（避免匹配到错误的通道）
            return None
    
    def get_by_date_and_rtsp_prefix(
        self, 
        date: str, 
        base_rtsp: str, 
        channel: str
    ) -> List[Task]:
        """根据日期、RTSP 前缀和通道获取任务列表"""
        prefix = f"{base_rtsp.rstrip('/')}/{channel}/%"
        return (
            self.db.query(Task)
            .filter(Task.date == date)
            .filter(Task.rtsp_url.like(prefix))
            .order_by(Task.index)
            .all()
        )
    
    def create(self, task_data: dict) -> Task:
        """创建新任务"""
        task = Task(**task_data)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task
    
    def bulk_create(self, tasks_data: List[dict]) -> List[Task]:
        """批量创建任务"""
        tasks = [Task(**data) for data in tasks_data]
        self.db.bulk_save_objects(tasks)
        self.db.commit()
        return tasks
    
    def update(self, task: Task, **kwargs) -> Task:
        """更新任务"""
        for key, value in kwargs.items():
            setattr(task, key, value)
        self.db.commit()
        self.db.refresh(task)
        return task
    
    def delete(self, task_id: int) -> bool:
        """删除任务"""
        task = self.get_by_id(task_id)
        if task:
            self.db.delete(task)
            self.db.commit()
            return True
        return False
    
    def bulk_delete(self, task_ids: List[int]) -> int:
        """批量删除任务"""
        count = self.db.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)
        self.db.commit()
        return count
    
    # ==================== 查询操作 ====================
    
    def get_pending_or_playing_tasks(self) -> List[Task]:
        """获取待运行或运行中的任务"""
        return (
            self.db.query(Task)
            .filter(Task.status.in_(["pending", "playing"]))
            .filter((Task.screenshot_path.is_(None)) | (Task.screenshot_path == ""))
            .all()
        )
    
    def get_failed_tasks_for_retry(
        self, 
        max_retry_count: int = 3,
        current_time: Optional[datetime] = None
    ) -> List[Task]:
        """获取需要重试的失败任务"""
        if current_time is None:
            current_time = datetime.utcnow()
        
        return (
            self.db.query(Task)
            .filter(Task.status == "failed")
            .filter(Task.retry_count < max_retry_count)
            .filter(Task.next_retry_at.isnot(None))
            .filter(Task.next_retry_at <= current_time)
            .all()
        )
    
    def get_tasks_with_screenshot_but_not_completed(self) -> List[Task]:
        """获取有截图但状态不是 completed 的任务（用于状态协调）"""
        return (
            self.db.query(Task)
            .filter(Task.screenshot_path.isnot(None))
            .filter(Task.screenshot_path != "")
            .filter(Task.status != "completed")
            .all()
        )
    
    def get_tasks_by_filters(
        self,
        date: Optional[str] = None,
        task_id: Optional[int] = None,
        ip: Optional[str] = None,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        status_in: Optional[List[str]] = None,
        start_ts_gte: Optional[int] = None,
        start_ts_lte: Optional[int] = None,
        end_ts_gte: Optional[int] = None,
        end_ts_lte: Optional[int] = None,
        screenshot_path_like: Optional[str] = None,
        rtsp_url_like: Optional[str] = None,
        order_by_index_desc: bool = True,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Tuple[List[Task], int]:
        """
        根据多个条件查询任务（支持分页）
        
        Returns:
            (任务列表, 总数)
        """
        query = self.db.query(Task)
        
        # 基础过滤
        if date:
            query = query.filter(Task.date == date)
        
        if task_id:
            query = query.filter(Task.id == task_id)
        
        # IP 过滤
        if ip:
            ip_clean = ip.strip()
            query = query.filter(
                or_(
                    Task.ip == ip_clean,
                    and_(Task.ip.is_(None), Task.rtsp_url.ilike(f"%@{ip_clean}%"))
                )
            )
        
        # 通道过滤
        if channel:
            ch_clean = channel.strip().lower()
            if not ch_clean.startswith("c"):
                ch_clean = f"c{ch_clean}"
            if ch_clean.startswith("/"):
                ch_clean = ch_clean.strip("/")
            query = query.filter(
                or_(
                    Task.channel == ch_clean,
                    and_(Task.channel.is_(None), Task.rtsp_url.ilike(f"%/{ch_clean}/%"))
                )
            )
        
        # 状态过滤
        if status:
            query = query.filter(Task.status == status.strip())
        elif status_in:
            query = query.filter(Task.status.in_(status_in))
        
        # 时间戳范围过滤
        if start_ts_gte is not None:
            query = query.filter(Task.start_ts >= start_ts_gte)
        if start_ts_lte is not None:
            query = query.filter(Task.start_ts <= start_ts_lte)
        if end_ts_gte is not None:
            query = query.filter(Task.end_ts >= end_ts_gte)
        if end_ts_lte is not None:
            query = query.filter(Task.end_ts <= end_ts_lte)
        
        # 截图路径过滤
        if screenshot_path_like:
            like_expr = f"%{screenshot_path_like.strip()}%"
            query = query.filter(Task.screenshot_path.ilike(like_expr))
        
        # RTSP URL 过滤
        if rtsp_url_like:
            like_expr = f"%{rtsp_url_like.strip()}%"
            query = query.filter(Task.rtsp_url.ilike(like_expr))
        
        # 获取总数
        total = query.count()
        
        # 排序
        if order_by_index_desc:
            query = query.order_by(Task.index.desc())
        else:
            query = query.order_by(Task.index)
        
        # 分页
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        
        return query.all(), total
    
    def get_available_dates(self) -> List[str]:
        """获取所有可用的日期列表"""
        dates_set = set()
        rows = self.db.query(Task.start_ts).distinct().all()
        for (start_ts,) in rows:
            if start_ts:
                try:
                    dt = datetime.fromtimestamp(start_ts)
                    date_str = dt.strftime("%Y-%m-%d")
                    dates_set.add(date_str)
                except (ValueError, OSError):
                    continue
        return sorted(list(dates_set), reverse=True)
    
    def get_available_ips(self) -> List[str]:
        """获取所有可用的 IP 地址列表"""
        ips_set = set()
        rows = self.db.query(Task.ip, Task.rtsp_url).distinct().all()
        for ip_val, rtsp_url in rows:
            if ip_val:
                ips_set.add(ip_val)
                continue
            if rtsp_url:
                match = re.search(r'@([\d.]+)(?::\d+)?/', rtsp_url)
                if match:
                    ips_set.add(match.group(1))
        return sorted(list(ips_set))
    
    def get_available_channels(self) -> List[str]:
        """获取所有可用的通道列表"""
        channels_set = set()
        rows = self.db.query(Task.channel, Task.rtsp_url).distinct().all()
        for ch_val, rtsp_url in rows:
            if ch_val:
                channels_set.add(ch_val)
                continue
            if rtsp_url:
                match = re.search(r'/(c\d+)/', rtsp_url)
                if match:
                    channels_set.add(match.group(1))
        # 按通道数字排序
        return sorted(list(channels_set), key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0)
    
    def update_status_batch(
        self, 
        task_ids: List[int], 
        status: str,
        updated_at: Optional[datetime] = None
    ) -> int:
        """批量更新任务状态"""
        if updated_at is None:
            updated_at = datetime.utcnow()
        
        count = (
            self.db.query(Task)
            .filter(Task.id.in_(task_ids))
            .update(
                {"status": status, "updated_at": updated_at},
                synchronize_session=False
            )
        )
        self.db.commit()
        return count
    
    def reconcile_task_status(self) -> int:
        """
        协调任务状态：将已生成截图但状态仍为非 completed 的任务纠正为 completed
        
        Returns:
            更新的任务数量
        """
        stale_tasks = self.get_tasks_with_screenshot_but_not_completed()
        if not stale_tasks:
            return 0
        
        count = 0
        for task in stale_tasks:
            task.status = "completed"
            task.error = None
            task.next_retry_at = None
            count += 1
        
        self.db.commit()
        return count
    
    def get_task_with_screenshot(
        self, 
        task_id: int
    ) -> Optional[Tuple[Task, Optional[Screenshot]]]:
        """
        获取任务及其最新截图
        
        Returns:
            (Task, Screenshot) 元组，如果没有截图则 Screenshot 为 None
        """
        task = self.get_by_id(task_id)
        if not task:
            return None
        
        screenshot = (
            self.db.query(Screenshot)
            .filter(Screenshot.task_id == task_id)
            .order_by(Screenshot.id.desc())
            .first()
        )
        
        return (task, screenshot)

