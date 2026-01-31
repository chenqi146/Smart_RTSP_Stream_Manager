"""任务清理服务"""
from typing import Optional, List
from pathlib import Path
from sqlalchemy.orm import Session

from models import Task, Screenshot, TaskBatch
from app.repositories.task_repository import TaskRepository
from app.core.config import SCREENSHOT_BASE


class TaskCleanupService:
    """任务清理服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = TaskRepository(db)
    
    def delete_task(self, task_id: int) -> bool:
        """
        删除单个任务及其关联数据
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否删除成功
        """
        task = self.repository.get_by_id(task_id)
        if not task:
            return False
        
        # 删除关联的截图和OCR结果
        screenshots = self.db.query(Screenshot).filter(Screenshot.task_id == task_id).all()
        screenshot_ids = [s.id for s in screenshots]
        
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
        
        # 删除数据库记录
        # OCR功能已移除，不再删除OCR记录
        self.db.query(Screenshot).filter(Screenshot.task_id == task_id).delete(synchronize_session=False)
        self.db.delete(task)
        self.db.commit()
        
        return True
    
    def delete_config_tasks(
        self, 
        date: str, 
        rtsp_ip: str, 
        channel: str
    ) -> dict:
        """
        删除指定配置下的所有任务
        
        Args:
            date: 日期
            rtsp_ip: RTSP IP地址
            channel: 通道
            
        Returns:
            删除结果字典
        """
        import re
        
        # 查找匹配的任务
        query = self.db.query(Task).filter(Task.date == date)
        if rtsp_ip:
            like_expr = f"%{rtsp_ip}%"
            query = query.filter(Task.rtsp_url.ilike(like_expr))
        if channel:
            like_expr = f"%/{channel}/%" if not channel.startswith("/") else f"%{channel}%"
            query = query.filter(Task.rtsp_url.ilike(like_expr))
        
        tasks = query.all()
        if not tasks:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="未找到匹配的任务")
        
        task_ids = [t.id for t in tasks]
        
        # 删除关联数据
        screenshots = self.db.query(Screenshot).filter(Screenshot.task_id.in_(task_ids)).all()
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
        
        # 删除数据库记录（任务及其截图、OCR）
        # OCR功能已移除，不再删除OCR记录
        self.db.query(Screenshot).filter(Screenshot.task_id.in_(task_ids)).delete(synchronize_session=False)
        # 记录涉及到的批次ID，便于后续删除任务批次
        batch_id_rows = self.db.query(Task.batch_id).filter(Task.id.in_(task_ids)).distinct().all()
        batch_ids = [bid for (bid,) in batch_id_rows if bid is not None]
        self.db.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)
        if batch_ids:
            self.db.query(TaskBatch).filter(TaskBatch.id.in_(batch_ids)).delete(synchronize_session=False)
        self.db.commit()
        
        return {
            "message": f"已删除 {len(tasks)} 个任务及其关联数据",
            "count": len(tasks),
            "date": date,
            "rtsp_ip": rtsp_ip,
            "channel": channel,
        }
    
    def clear_date_data(
        self, 
        date: str, 
        base_rtsp: Optional[str] = None, 
        channel: Optional[str] = None
    ):
        """
        清理指定日期的任务数据
        
        Args:
            date: 日期
            base_rtsp: RTSP 基础地址（可选）
            channel: 通道（可选）
        """
        import re
        
        print(f"[INFO] 开始清理任务数据 - 日期: {date}, RTSP: {base_rtsp}, 通道: {channel}")
        
        # 构建查询条件
        query = self.db.query(Task.id).filter(Task.date == date)
        
        # 如果提供了base_rtsp和channel，则精确匹配
        if base_rtsp and channel:
            ip_match = re.search(r'@([\d.]+)(?::\d+)?', base_rtsp)
            base_ip = ip_match.group(1) if ip_match else None
            base_rtsp_clean = base_rtsp.rstrip("/")
            match_prefix = f"{base_rtsp_clean}/{channel}/"
            
            if base_ip:
                query = query.filter(Task.ip == base_ip, Task.channel == channel)
            else:
                query = query.filter(Task.rtsp_url.like(f"{match_prefix}%"))
            print(f"[INFO] 精确匹配清理 - 前缀: {match_prefix}")
        elif base_rtsp:
            ip_match = re.search(r'@([\d.]+)(?::\d+)?', base_rtsp)
            base_ip = ip_match.group(1) if ip_match else None
            if base_ip:
                query = query.filter(Task.ip == base_ip)
            else:
                query = query.filter(Task.rtsp_url.like(f"{base_rtsp}%"))
        elif channel:
            query = query.filter(Task.channel == channel)
        
        # 获取任务ID列表
        task_id_rows = query.all()
        task_ids = [r.id for r in task_id_rows]
        
        if not task_ids:
            print(f"[INFO] 没有找到需要清理的任务")
            return
        
        # OCR功能已移除，不再删除OCR记录
        print(f"[INFO] 已删除 {ocr_count} 个OCR记录")
        
        # 删除截图（数据库+磁盘）
        shot_rows = self.db.query(Screenshot.id, Screenshot.file_path).filter(
            Screenshot.task_id.in_(task_ids)
        ).all()
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
        self.db.query(Screenshot).filter(Screenshot.task_id.in_(task_ids)).delete(synchronize_session=False)
        print(f"[INFO] 已删除 {screenshot_count} 个截图记录（含磁盘文件）")
        
        # 删除任务及其所属批次（如果一个批次的任务全部被删除）
        task_count = self.db.query(Task).filter(Task.id.in_(task_ids)).count()
        # 先记录涉及到的批次ID
        batch_id_rows = self.db.query(Task.batch_id).filter(Task.id.in_(task_ids)).distinct().all()
        batch_ids = [bid for (bid,) in batch_id_rows if bid is not None]
        self.db.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)
        print(f"[INFO] 已删除 {task_count} 个任务记录")

        if batch_ids:
            # 这里直接删除这些批次记录；因为 clear_date_data 目前用于“重建某天某通道的任务”，
            # 被删除的任务批次在业务上也已经无效。
            deleted_batches = (
                self.db.query(TaskBatch)
                .filter(TaskBatch.id.in_(batch_ids))
                .delete(synchronize_session=False)
            )
            print(f"[INFO] 已删除 {deleted_batches} 个任务批次记录")

        self.db.commit()
        print(f"[INFO] 清理完成 - 共清理 {len(task_ids)} 个任务及其关联数据")

