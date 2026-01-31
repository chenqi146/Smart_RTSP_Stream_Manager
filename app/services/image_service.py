"""图片业务逻辑层（Service Pattern）"""
from typing import List, Optional, Dict, Tuple, Set
from pathlib import Path
import re
from sqlalchemy.orm import Session
from sqlalchemy import tuple_

from app.repositories.image_repository import ImageRepository
from app.core.config import SCREENSHOT_BASE
from models import Task, Screenshot, ParkingChangeSnapshot


class ImageService:
    """图片业务逻辑服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = ImageRepository(db)
    
    def build_image_url(self, p: Path, prefer_detected: bool = False) -> Tuple[str, bool]:
        """
        构造图片可访问 URL；如果文件缺失，标记 missing。
        
        参数:
            p: 图片路径
            prefer_detected: 如果为 True，优先返回 _detected.jpg 的URL（如果存在）
        
        返回: (url, missing)
        """
        # 若是相对路径，先补全到截图根目录
        if not p.is_absolute():
            p = SCREENSHOT_BASE / p
        
        # 如果优先使用 _detected.jpg，先检查是否存在
        if prefer_detected:
            detected_path = p.parent / f"{p.stem}_detected{p.suffix}"
            if detected_path.exists():
                p = detected_path
        
        # 如果文件不存在且可能是相对路径，尝试再次拼接
        missing = not p.exists()
        try:
            abs_path = p.resolve()
            rel = abs_path.relative_to(SCREENSHOT_BASE)

            # 为了避免浏览器缓存旧图片（同一路径下内容被更新），
            # 将文件最后修改时间作为版本号附加到 URL 查询参数中。
            version = int(abs_path.stat().st_mtime) if abs_path.exists() else 0
            url = f"/shots/{rel.as_posix()}"
            if version:
                url = f"{url}?v={version}"
            return url, missing
        except Exception:
            # 不在截图目录下，走代理端点
            return f"/api/image_proxy?path={p.as_posix()}", missing
    
    def to_relative_path(self, p: Path) -> str:
        """
        将路径转为相对于 SCREENSHOT_BASE 的相对路径字符串；否则返回绝对路径字符串。
        """
        try:
            abs_path = p.resolve()
            rel = abs_path.relative_to(SCREENSHOT_BASE)
            return rel.as_posix()
        except Exception:
            return str(p)
    
    def get_task_ip_from_rtsp(self, rtsp_url: str) -> str:
        """从 RTSP URL 中提取 IP 地址"""
        ip_match = re.search(r'@([\d.]+)(?::\d+)?/', rtsp_url)
        return ip_match.group(1) if ip_match else ""
    
    def get_task_channel_from_rtsp(self, rtsp_url: str) -> str:
        """从 RTSP URL 中提取通道"""
        channel_match = re.search(r'/(c\d+)/', rtsp_url)
        return channel_match.group(1) if channel_match else ""
    
    def get_status_label(self, task: Task, shot: Optional[Screenshot]) -> Tuple[Optional[str], Optional[str]]:
        """
        根据任务状态和截图情况确定显示状态标签
        
        返回: (status_label, status_label_display)
        status_label: None=正常显示, "pending"=待截图, "playing"=截图中, "missing"=文件缺失, "failed"=截图失败
        status_label_display: 中文显示文本
        """
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
                # 任务失败但没有任何截图记录，更合理地视为“暂无截图/缺失”
                status_label = "missing"
                status_label_display = "文件缺失"
            else:
                # completed 但没有截图记录，可能是文件被删除
                status_label = "missing"
                status_label_display = "文件缺失"
        
        return status_label, status_label_display
    
    def list_images(
        self,
        date: Optional[str] = None,
        screenshot_dir: str = "screenshots",
        # 向后兼容的旧参数
        rtsp_ip: Optional[str] = None,
        channel: Optional[str] = None,
        # 新的搜索参数
        name_eq: Optional[str] = None,
        name_like: Optional[str] = None,
        task_ip: Optional[str] = None,
        task_ip_like: Optional[str] = None,
        task_channel: Optional[str] = None,
        task_channel_like: Optional[str] = None,
        task_status: Optional[str] = None,
        task_status_in: Optional[str] = None,
        status_label: Optional[str] = None,
        status_label_in: Optional[str] = None,
        task_start_ts_gte: Optional[int] = None,
        task_start_ts_lte: Optional[int] = None,
        task_end_ts_gte: Optional[int] = None,
        task_end_ts_lte: Optional[int] = None,
        missing: Optional[bool] = None,
    ) -> Dict:
        """
        每个任务只返回一张截图（最新的一张），保证"任务数 = 图片数"，不多不少。
        若任务没有截图，也会返回一条记录，标记 missing=True，便于排查缺图。
        """
        items = []
        
        # 处理向后兼容参数
        ip_search = task_ip or rtsp_ip
        channel_search = task_channel or channel
        
        # 处理状态列表
        status_list = None
        if task_status_in:
            status_list = [s.strip() for s in task_status_in.split(",") if s.strip()]
        
        # 处理状态标签列表
        status_label_list = None
        if status_label_in:
            status_label_list = [s.strip() for s in status_label_in.split(",") if s.strip()]
        
        # 获取任务列表（初步按 IP/通道等过滤）
        tasks = self.repository.get_tasks_with_filters(
            date=date,
            task_ip=ip_search,
            task_ip_like=task_ip_like,
            task_channel=channel_search,
            task_channel_like=task_channel_like,
            task_status=task_status,
            task_status_in=status_list,
            task_start_ts_gte=task_start_ts_gte,
            task_start_ts_lte=task_start_ts_lte,
            task_end_ts_gte=task_end_ts_gte,
            task_end_ts_lte=task_end_ts_lte,
        )

        # 保险起见，再在 Service 层做一次精确过滤，确保 IP / 通道条件与任务列表保持一致。
        # 这样即使底层数据有历史脏数据（例如 Task.ip 为空或有误），也能通过 rtsp_url 解析出真实 IP/通道并过滤。
        def _normalize_channel(code: Optional[str]) -> str:
            if not code:
                return ""
            c = code.strip().lower()
            if c.startswith("/"):
                c = c.lstrip("/")
            if c and not c.startswith("c"):
                c = f"c{c}"
            return c

        ip_filter = (ip_search or "").strip()
        ch_filter_raw = channel_search or ""
        ch_filter = _normalize_channel(ch_filter_raw)

        if ip_filter or ch_filter:
            filtered_tasks: List[Task] = []
            for t in tasks:
                # 解析任务的实际 IP / 通道（优先用冗余字段，其次从 RTSP 中解析）
                t_ip = t.ip or self.get_task_ip_from_rtsp(t.rtsp_url or "")
                t_ch = _normalize_channel(t.channel or self.get_task_channel_from_rtsp(t.rtsp_url or ""))

                if ip_filter and t_ip != ip_filter:
                    continue
                if ch_filter and t_ch != ch_filter:
                    continue

                filtered_tasks.append(t)

            tasks = filtered_tasks

        # 为当前请求构建一次“IP+通道 -> 摄像头名称”的映射，用于在返回 JSON 时把通道展示为
        # 例如 "c1 高新四路36号枪机"。这里通过 SQL 联表查询实现，不做跨请求缓存。
        channel_display_map: Dict[Tuple[str, str], str] = {}
        parking_name_map: Dict[str, str] = {}  # IP -> 停车场名称
        if tasks:
            # 收集所有出现过的 (ip, channel) 组合和IP列表
            ip_channel_keys: Set[Tuple[str, str]] = set()
            ip_set: Set[str] = set()
            for t in tasks:
                ip_val = t.ip or self.get_task_ip_from_rtsp(t.rtsp_url)
                ch_val = t.channel or self.get_task_channel_from_rtsp(t.rtsp_url)
                if ip_val and ch_val:
                    ip_channel_keys.add((ip_val.strip(), ch_val.strip().lower()))
                if ip_val:
                    ip_set.add(ip_val.strip())

            if ip_channel_keys:
                from models import NvrConfig, ChannelConfig
                # 一次性查询所有相关的通道配置（使用与当前请求同一个 Session）
                db = self.db
                rows = (
                    db.query(
                        NvrConfig.nvr_ip,
                        NvrConfig.parking_name,
                        ChannelConfig.channel_code,
                        ChannelConfig.camera_name,
                    )
                    .join(ChannelConfig, ChannelConfig.nvr_config_id == NvrConfig.id)
                    .filter(
                        tuple_(
                            NvrConfig.nvr_ip,
                            ChannelConfig.channel_code,
                        ).in_(list(ip_channel_keys))
                    )
                    .all()
                )
                for nvr_ip, parking_name, ch_code, cam_name in rows:
                    key = (nvr_ip.strip(), ch_code.strip().lower())
                    display = ch_code.strip().lower()
                    if cam_name:
                        display = f"{display} {cam_name.strip()}"
                    channel_display_map[key] = display
                    # 同时记录停车场名称
                    if parking_name:
                        parking_name_map[nvr_ip.strip()] = parking_name.strip()
            
            # 如果有些IP没有在通道查询中出现，单独查询停车场名称
            if ip_set:
                from models import NvrConfig
                missing_ips = ip_set - set(parking_name_map.keys())
                if missing_ips:
                    db = self.db
                    nvr_rows = db.query(NvrConfig.nvr_ip, NvrConfig.parking_name).filter(
                        NvrConfig.nvr_ip.in_(list(missing_ips))
                    ).all()
                    for nvr_ip, parking_name in nvr_rows:
                        if parking_name:
                            parking_name_map[nvr_ip.strip()] = parking_name.strip()
        
        # 批量获取截图
        task_ids = [t.id for t in tasks]
        screenshot_dict = self.repository.get_screenshot_dict_by_task_ids(task_ids)

        # 批量获取车位变化快照（通过 screenshot_id 关联）
        screenshot_ids = [s.id for s in screenshot_dict.values() if s]
        parking_change_snapshots = {}
        if screenshot_ids:
            snapshots = (
                self.db.query(ParkingChangeSnapshot)
                .filter(ParkingChangeSnapshot.screenshot_id.in_(screenshot_ids))
                .all()
            )
            for snap in snapshots:
                parking_change_snapshots[snap.screenshot_id] = {
                    "change_count": snap.change_count or 0,
                    "detected_at": snap.detected_at.isoformat() if snap.detected_at else None,
                    "snapshot_id": snap.id,
                }

        # OCR功能已移除，不再获取OCR结果
        
        # 处理通道过滤（向后兼容）
        channel_filter_val = None
        if channel:
            channel_filter_val = channel.strip().lower()
            if not channel_filter_val.startswith("c"):
                channel_filter_val = f"c{channel_filter_val}"
            if channel_filter_val.startswith("/"):
                channel_filter_val = channel_filter_val.strip("/")
        
        # 构建返回项
        for t in tasks:
            shot = screenshot_dict.get(t.id)
            # OCR功能已移除
            ocr = None
            
            # 获取状态标签
            status_label_val, status_label_display = self.get_status_label(t, shot)
            
            # 处理截图信息
            if shot:
                p = Path(shot.file_path)
                url, missing_val = self.build_image_url(p)
                name = p.name
                path = str(p)
                if missing_val:
                    status_label_val = "missing"
                    status_label_display = "文件缺失"
            else:
                url = ""
                path = ""
                name = ""
                missing_val = True
            
            # 提取任务IP和通道
            task_ip_val = t.ip
            if not task_ip_val:
                task_ip_val = self.get_task_ip_from_rtsp(t.rtsp_url)
            
            task_channel_val = t.channel
            if not task_channel_val:
                task_channel_val = self.get_task_channel_from_rtsp(t.rtsp_url)

            # 使用 SQL 联表结果对通道进行“通道+摄像头名称”展示
            channel_display = task_channel_val or ""
            key_for_display = (task_ip_val.strip(), (task_channel_val or "").strip().lower()) if task_ip_val and task_channel_val else None
            if key_for_display and key_for_display in channel_display_map:
                channel_display = channel_display_map[key_for_display]
            
            # 应用图片名称过滤
            if name_eq and name != name_eq.strip():
                continue
            if name_like and name_like.strip() not in name:
                continue
            
            # 应用状态标签过滤
            if status_label and status_label_display != status_label:
                continue
            if status_label_list and status_label_display not in status_label_list:
                continue
            
            # 应用缺失状态过滤
            if missing is not None:
                # 只要没有截图记录，或者有截图但物理文件缺失，都视为 missing=True
                item_is_missing = (not shot) or (shot and missing_val)
                if missing != item_is_missing:
                    continue
            else:
                # 默认（前端“是否缺失=全部”但没有显式勾选缺失时），只展示“有真实截图文件”的记录，
                # 将“暂无截图/文件缺失”的任务排除掉，避免用户看到疑似多余的占位卡片。
                if (not shot) or (shot and missing_val):
                    continue

            # 计算 OCR 状态，便于前端区分“未处理 / 未识别到 / 已识别”
            # - 无截图：一定是 "not_processed"
            # - 有截图但无 ocr 记录：可能是历史数据，视为 "not_processed"
            # - 有 ocr 记录：
            #     * 任一 detected/corrected 字段非空 => "ok"
            #     * 全部为空                     => "no_time"（已处理但未识别到）
            if not shot:
                ocr_status = "not_processed"
            elif not ocr:
                ocr_status = "not_processed"
            else:
                has_time = bool(
                    getattr(ocr, "detected_time", None)
                    or getattr(ocr, "detected_timestamp", None)
                    or getattr(ocr, "corrected_time", None)
                    or getattr(ocr, "corrected_timestamp", None)
                )
                ocr_status = "ok" if has_time else "no_time"

            # 获取停车场名称
            parking_name_val = parking_name_map.get(task_ip_val.strip()) if task_ip_val else None
            
            # 获取车位变化信息（如果有）
            parking_change_info = None
            if shot and shot.id in parking_change_snapshots:
                parking_change_info = parking_change_snapshots[shot.id]
            
            items.append({
                "task_id": t.id,
                "name": name,
                "path": path,
                "url": url,
                "missing": missing_val,
                "task_status": t.status or "pending",
                "status_label": status_label_val,  # 状态码：pending/playing/failed/missing/null
                "status_label_display": status_label_display,  # 中文显示文本
                "task_date": t.date,
                "task_rtsp_url": t.rtsp_url,
                "task_ip": task_ip_val,
                "task_parking_name": parking_name_val,  # 停车场名称
                # 接口返回的任务通道字段：通道编码 + 摄像头名称（如果查得到）
                # 例如："c1 高新四路36号枪机"
                "task_channel": channel_display,
                "task_start_ts": t.start_ts,
                "task_end_ts": t.end_ts,
                # 车位变化信息（如果有）
                "parking_change": parking_change_info,  # {change_count, detected_at, snapshot_id} 或 None
                # OCR功能已移除，相关字段不再返回
            })
        
        return {"date": date or "all", "count": len(items), "items": items}
    
    def get_available_dates(self, screenshot_dir: str = "screenshots") -> Dict:
        """
        返回有截图数据的日期列表（优先数据库，有则提供数量；无则扫描文件夹）。
        """
        dates: Dict[str, int] = self.repository.get_available_dates_from_db()
        
        if dates:
            return {"dates": [{"date": d, "count": dates[d]} for d in sorted(dates.keys())]}
        
        # fallback: scan filesystem
        base_dir = Path(screenshot_dir)
        if not base_dir.is_absolute():
            from app.core.config import PROJECT_ROOT
            base_dir = PROJECT_ROOT / base_dir
        if not base_dir.exists():
            return {"dates": []}
        
        for sub in base_dir.iterdir():
            if sub.is_dir():
                cnt = len(list(sub.glob("*.jpg"))) + len(list(sub.glob("*.jpeg"))) + len(list(sub.glob("*.png")))
                if cnt > 0:
                    dates[sub.name] = cnt
        
        return {"dates": [{"date": d, "count": dates[d]} for d in sorted(dates.keys())]}

    # ==================== OCR 结果查询 ====================
    # OCR功能已移除，get_task_ocr方法已废弃

