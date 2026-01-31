"""任务业务逻辑服务层"""
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import re

from models import Task, TaskBatch
from schemas.tasks import TaskCreateRequest, TaskCreateResponse, TaskSegment, RunTaskRequest
from app.repositories.task_repository import TaskRepository
from services.segment_generator import build_segment_tasks
from services.stream_check import check_rtsp
from utils.task_utils import make_task_key
from app.core.config import TASK_STORE
from app.core.constants import MAX_RETRY_COUNT
from utils.path_utils import to_rel


class TaskService:
    """任务业务逻辑服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = TaskRepository(db)
    
    # ==================== 任务创建和管理 ====================
    
    def ensure_tasks(self, req: TaskCreateRequest) -> TaskCreateResponse:
        """
        确保任务存在，如果不存在则创建；
        若同一 IP/日期/通道/时间段的任务已存在，则不会重复创建，只做统计返回。
        
        Args:
            req: 任务创建请求
            
        Returns:
            任务创建响应
        """
        # 先校验流可用性（用第一段 URL 检测），失败仅警告不阻塞生成
        test_segments = build_segment_tasks(
            req.date, 
            base_rtsp=req.base_rtsp, 
            channel=req.channel, 
            interval_minutes=req.interval_minutes
        )
        if not test_segments:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="no segments generated")
        
        first_url = test_segments[0]["rtsp_url"]
        ok, err = check_rtsp(first_url)
        if not ok:
            print(f"[WARN] RTSP check failed, continue generating tasks. detail={err[:300]}")
        
        # 生成任务段（理论上的完整时间轴）
        segments = build_segment_tasks(
            req.date,
            base_rtsp=req.base_rtsp,
            channel=req.channel,
            interval_minutes=req.interval_minutes,
        )
        models = [TaskSegment(**seg) for seg in segments]
        key = make_task_key(req.date, req.base_rtsp, req.channel)
        TASK_STORE[key] = models

        if not models:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="no segments generated")

        # 创建任务批次（任务列表主表）
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
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        print(
            f"[INFO] 生成任务批次 - 日期: {req.date}, IP: {ip_val_for_batch}, 通道: {ch_val_for_batch or req.channel}, "
            f"时间段: {batch_start_ts}-{batch_end_ts}, 间隔: {req.interval_minutes} 分钟, 分片数: {len(models)}"
        )

        # 统计：哪些时间段已经有任务，哪些需要新建
        tasks_data: list[dict] = []
        existing_count = 0
        created_count = 0

        print(f"[DEBUG] 开始处理 {len(models)} 个任务段，日期: {req.date}, 通道: {req.channel}")
        
        for seg in models:
            # 解析 IP 和通道
            ip_val = None
            ip_match = re.search(r'@([\d.]+)(?::\d+)?', seg.rtsp_url)
            if ip_match:
                ip_val = ip_match.group(1)
            
            ch_val = None
            ch_match = re.search(r'/(c\d+)/', seg.rtsp_url)
            if ch_match:
                ch_val = ch_match.group(1)
            # 如果从URL解析失败，使用请求中的channel作为fallback
            if not ch_val:
                ch_val = req.channel
            
            # 判断该时间段任务是否已存在（同日期 + start_ts + end_ts + ip + channel）
            existing_task = self.repository.get_by_date_and_timestamps(
                req.date,
                seg.start_ts,
                seg.end_ts,
                channel=ch_val,
                ip=ip_val,
            )
            if existing_task:
                existing_count += 1
                if existing_count <= 3:  # 只打印前3个已存在任务的日志，避免日志过多
                    print(f"[DEBUG] 任务已存在 - 日期: {req.date}, 通道: {ch_val}, IP: {ip_val}, start_ts: {seg.start_ts}, end_ts: {seg.end_ts}, task_id: {existing_task.id}")
                continue

            created_count += 1
            tasks_data.append(
                {
                    "date": req.date,
                    "index": seg.index,
                    "start_ts": seg.start_ts,
                    "end_ts": seg.end_ts,
                    "rtsp_url": seg.rtsp_url,
                    "status": seg.status,
                    "ip": ip_val,
                    "channel": ch_val,
                    "batch_id": batch.id,
                }
            )
        
        print(f"[DEBUG] 任务统计 - 需要新建: {created_count} 段, 已存在: {existing_count} 段, tasks_data长度: {len(tasks_data)}")
        
        if tasks_data:
            try:
                self.repository.bulk_create(tasks_data)
                print(f"[DEBUG] 成功批量创建 {len(tasks_data)} 个任务")
            except Exception as e:
                print(f"[ERROR] 批量创建任务失败: {e}")
                raise
        print(
            f"[INFO] 任务生成完成 - 日期: {req.date}, 通道: {req.channel}, "
            f"新建: {created_count} 段, 已存在: {existing_count} 段"
        )
        
        return TaskCreateResponse(
            date=req.date,
            total_segments=len(models),
            segments=models,
            created_segments=created_count,
            existing_segments=existing_count,
        )
    
    def _clear_date_data(self, date: str, base_rtsp: Optional[str] = None, channel: Optional[str] = None):
        """
        清理指定日期的任务数据
        
        Args:
            date: 日期
            base_rtsp: RTSP 基础地址（可选）
            channel: 通道（可选）
        """
        from app.services.task_cleanup_service import TaskCleanupService
        cleanup_service = TaskCleanupService(self.db)
        cleanup_service.clear_date_data(date, base_rtsp=base_rtsp, channel=channel)
    
    # ==================== 任务查询 ====================
    
    def get_available_dates(self) -> List[Dict[str, str]]:
        """获取所有可用的日期列表"""
        dates = self.repository.get_available_dates()
        return [{"date": d} for d in dates]
    
    def get_available_ips(self) -> List[Dict[str, str]]:
        """获取所有可用的 IP 地址列表"""
        ips = self.repository.get_available_ips()
        return [{"ip": ip} for ip in ips]
    
    def get_available_channels(self) -> List[Dict[str, str]]:
        """获取所有可用的通道列表"""
        channels = self.repository.get_available_channels()
        return [{"channel": ch} for ch in channels]
    
    def get_tasks_paged(
        self,
        date: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        task_id: Optional[int] = None,
        **filters
    ) -> Dict:
        """
        获取分页的任务列表
        
        Args:
            date: 日期
            page: 页码
            page_size: 每页大小
            task_id: 任务ID（精确查询）
            **filters: 其他过滤条件
            
        Returns:
            分页结果字典
        """
        # 状态协调
        self.repository.reconcile_task_status()
        
        # 计算分页参数
        page = max(page, 1)
        page_size = max(min(page_size, 50), 10)
        offset = (page - 1) * page_size
        
        # 构建查询参数
        query_params = {
            "date": date,
            "task_id": task_id,
            "offset": offset,
            "limit": page_size,
            "order_by_index_desc": True,
        }
        
        # 添加过滤条件
        if "ip" in filters:
            query_params["ip"] = filters["ip"]
        if "channel" in filters:
            query_params["channel"] = filters["channel"]
        if "status" in filters:
            query_params["status"] = filters["status"]
        if "status_in" in filters:
            status_list = [s.strip() for s in filters["status_in"].split(",") if s.strip()]
            query_params["status_in"] = status_list
        if "screenshot_name_like" in filters:
            query_params["screenshot_path_like"] = filters["screenshot_name_like"]
        if "rtsp_url_like" in filters:
            query_params["rtsp_url_like"] = filters["rtsp_url_like"]
        if "start_ts_gte" in filters:
            query_params["start_ts_gte"] = filters["start_ts_gte"]
        if "start_ts_lte" in filters:
            query_params["start_ts_lte"] = filters["start_ts_lte"]
        if "end_ts_gte" in filters:
            query_params["end_ts_gte"] = filters["end_ts_gte"]
        if "end_ts_lte" in filters:
            query_params["end_ts_lte"] = filters["end_ts_lte"]
        
        # 执行查询
        tasks, total = self.repository.get_tasks_by_filters(**query_params)
        
        # 转换为响应格式
        items = [
            {
                "id": t.id,
                "index": t.index,
                "start_ts": t.start_ts,
                "end_ts": t.end_ts,
                "rtsp_url": t.rtsp_url,
                "ip": t.ip,
                "channel": t.channel,
                "status": t.status,
                "screenshot_path": t.screenshot_path,
                "error": t.error,
                "date": t.date,
                "operation_time": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in tasks
        ]
        
        return {
            "date": date or "all",
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": items
        }
    
    # ==================== 任务删除 ====================
    
    def delete_task(self, task_id: int) -> bool:
        """
        删除单个任务及其关联数据
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否删除成功
        """
        from app.services.task_cleanup_service import TaskCleanupService
        cleanup_service = TaskCleanupService(self.db)
        return cleanup_service.delete_task(task_id)
    
    def delete_config_tasks(
        self, 
        date: str, 
        rtsp_ip: str, 
        channel: str
    ) -> Dict:
        """
        删除指定配置下的所有任务
        
        Args:
            date: 日期
            rtsp_ip: RTSP IP地址
            channel: 通道
            
        Returns:
            删除结果字典
        """
        from app.services.task_cleanup_service import TaskCleanupService
        cleanup_service = TaskCleanupService(self.db)
        return cleanup_service.delete_config_tasks(date, rtsp_ip, channel)
    
    # ==================== 任务状态管理 ====================
    
    def reconcile_task_status(self) -> int:
        """
        协调任务状态：将已生成截图但状态仍为非 completed 的任务纠正为 completed
        
        Returns:
            更新的任务数量
        """
        return self.repository.reconcile_task_status()
    
    def update_task_status(
        self,
        date: str,
        start_ts: int,
        end_ts: int,
        status: str,
        screenshot_path: Optional[str] = None,
        error: Optional[str] = None,
        channel: Optional[str] = None,
        ip: Optional[str] = None
    ) -> bool:
        """
        更新任务状态
        
        Args:
            date: 日期
            start_ts: 开始时间戳
            end_ts: 结束时间戳
            status: 状态
            screenshot_path: 截图路径（可选）
            error: 错误信息（可选）
            channel: 通道（可选）
            ip: IP地址（可选）
            
        Returns:
            是否更新成功
        """
        task = self.repository.get_by_date_and_timestamps(
            date, start_ts, end_ts, channel=channel, ip=ip
        )
        
        if not task:
            print(f"[WARN] 未找到需要更新的任务记录，可能已被删除。date={date}, start={start_ts}, end={end_ts}")
            return False
        
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if screenshot_path is not None:
            update_data["screenshot_path"] = screenshot_path
        if error is not None:
            update_data["error"] = error
        
        self.repository.update(task, **update_data)
        return True

