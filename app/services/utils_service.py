"""工具类业务逻辑层（Service Pattern）"""
from typing import Dict, Optional, Any
from pathlib import Path
import uuid
import time
import shutil

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import (
    HLS_BASE,
    HLS_PROCS,
    SCREENSHOT_BASE,
    STATIC_DIR,
    TASK_STORE,
    RUNNING_KEYS,
)
from services.stream_hls import start_hls, probe_rtsp
from db import SessionLocal, engine, Base
from models import (
    Task,
    Screenshot,
    AutoScheduleRule,
    ParkingChange,
    ParkingChangeSnapshot,
    TaskBatch,
    OcrResult,
    MinuteScreenshot,
)


class UtilsService:
    """工具类业务逻辑服务"""
    
    def __init__(self):
        pass
    
    def start_hls_stream(self, rtsp_url: str) -> Dict[str, Any]:
        """
        启动 HLS 流转换
        
        返回: {"m3u8": m3u8_url, "warn": warn_message}
        """
        # 探测 RTSP 流
        ok, err = probe_rtsp(rtsp_url)
        if not ok:
            # 尝试继续启动，但返回警告信息（方便调试）
            print(f"[HLS][warn] RTSP probe failed, continue start. detail={err[:500]}")
        
        # 生成唯一键和输出目录
        key = str(uuid.uuid4())
        out_dir = HLS_BASE / key
        proc = start_hls(rtsp_url, out_dir, stream_name="index")
        
        if not proc:
            detail = "FFmpeg启动失败或未安装"
            if err:
                detail += f"；probe: {err[:300]}"
            raise HTTPException(status_code=500, detail=detail)
        
        # 等待 m3u8 文件生成，超时则认为启动失败
        m3u8_path = out_dir / "index.m3u8"
        wait_time = 20  # seconds, 给转码/生成m3u8更多时间
        poll_interval = 0.5
        elapsed = 0.0
        
        while elapsed < wait_time:
            if m3u8_path.exists():
                break
            if proc.poll() is not None:
                # ffmpeg 已退出
                proc.terminate()
                raise HTTPException(
                    status_code=500,
                    detail="FFmpeg启动后异常退出，未生成m3u8"
                )
            time.sleep(poll_interval)
            elapsed += poll_interval
        
        if not m3u8_path.exists():
            try:
                proc.terminate()
            except Exception:
                pass
            raise HTTPException(
                status_code=500,
                detail="未生成m3u8，请检查RTSP源或FFmpeg输出（可能需要更长时间或流无数据）"
            )
        
        # 保存进程引用
        HLS_PROCS[key] = proc
        m3u8_url = f"/hls/{key}/index.m3u8"
        warn = None if ok else f"RTSP探测失败，已尝试直接启动：{err[:200]}"
        
        return {"m3u8": m3u8_url, "warn": warn}
    
    def get_health_status(self) -> Dict[str, str]:
        """获取健康检查状态"""
        return {"status": "ok"}
    
    # OCR功能已移除，get_ocr_results方法已废弃
    
    def proxy_image(self, path: str) -> Path:
        """
        代理返回图片文件
        
        返回: 图片文件路径
        抛出: HTTPException 如果文件不存在
        """
        p = Path(path)
        if not p.is_absolute():
            p = SCREENSHOT_BASE / p
        if not p.exists():
            raise HTTPException(status_code=404, detail="file not found")
        return p
    
    def get_index_page(self) -> Optional[Path]:
        """
        获取首页静态文件
        
        返回: 首页文件路径，如果不存在则返回 None
        """
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return index_path
        return None

    # ==================== 管理类工具：清空与重新部署 ====================

    def _clear_directory_contents(self, base: Path) -> None:
        """
        删除目录下的所有内容，但保留目录本身。
        """
        if not base.exists():
            return
        for child in base.iterdir():
            try:
                if child.is_file() or child.is_symlink():
                    child.unlink()
                elif child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
            except Exception as e:
                print(f"[WARN] 清理目录内容失败: {child}, err={e}")

    def _clear_database(self, db: Session) -> None:
        """
        清空业务相关表中的数据，但不删除表结构。
        注意：必须按照外键依赖关系，从最底层的子表开始删除，避免外键约束错误。
        当前依赖关系简要说明：
        - ParkingChange / ParkingChangeSnapshot 依赖 Screenshot / Task / 车位配置等
        - OcrResult 依赖 Screenshot
        - MinuteScreenshot 依赖 Task
        - Screenshot 依赖 Task
        - TaskBatch 可能被 Task 引用
        """
        try:
            # 1. 先删除最底层的子表（车位变化相关表，依赖 tasks, screenshots, channel_configs, parking_spaces）
            db.query(ParkingChange).delete(synchronize_session=False)
            db.query(ParkingChangeSnapshot).delete(synchronize_session=False)
            
            # 2. 删除 OCR 结果（如果表存在，依赖 screenshots，必须在删除 screenshots 之前删除）
            # 注意：即使 OCR 功能已移除，但数据库表可能仍然存在，需要先删除以避免外键约束错误
            try:
                db.query(OcrResult).delete(synchronize_session=False)
            except Exception as e:
                # 如果表不存在或已删除，忽略错误
                print(f"[WARN] 删除 OCR 结果时出错（可能表已不存在）: {e}")
            
            # 3. 删除每分钟截图（minute_screenshots），该表通过 task_id 依赖 tasks，
            #    必须在删除 Task 之前清空，否则会触发外键约束错误。
            try:
                db.query(MinuteScreenshot).delete(synchronize_session=False)
            except Exception as e:
                # 表可能尚未创建或已被手工删除，记录告警但不中断流程
                print(f"[WARN] 删除 minute_screenshots 记录时出错（可能表已不存在）: {e}")
            
            # 4. 删除截图（screenshots，依赖 tasks）
            db.query(Screenshot).delete(synchronize_session=False)
            
            # 5. 删除任务明细（tasks，可能依赖 TaskBatch）
            db.query(Task).delete(synchronize_session=False)
            
            # 6. 删除任务批次（如果有）
            db.query(TaskBatch).delete(synchronize_session=False)
            
            # 7. 删除自动调度规则（独立表）
            db.query(AutoScheduleRule).delete(synchronize_session=False)
            
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[ERROR] 清空数据库失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def mark_screenshots_pending_for_parking_change(self, limit: int = 200) -> int:
        """
        将历史未做车位变化识别的截图标记为 pending，供车位变化检测 Worker 自动处理（补齐）。
        仅处理 yolo_status 为 NULL、done 或 failed 的记录，每批最多 limit 条，按 id 升序。
        """
        with SessionLocal() as db:
            rows = (
                db.query(Screenshot)
                .filter(
                    or_(
                        Screenshot.yolo_status.is_(None),
                        Screenshot.yolo_status.in_(["done", "failed"]),
                    )
                )
                .order_by(Screenshot.id.asc())
                .limit(limit)
                .all()
            )
            for s in rows:
                s.yolo_status = "pending"
                s.yolo_last_error = None
            db.commit()
            n = len(rows)
            if n > 0:
                print(f"[INFO] 车位变化补齐：已将 {n} 张截图标记为待检测 (yolo_status=pending)")
            return n

    def clear_all_data(self) -> Dict[str, Any]:
        """
        清空系统中的所有业务数据：
        - 数据库中的 Task / Screenshot / AutoScheduleRule / ParkingChange / ParkingChangeSnapshot / TaskBatch 记录
        - 截图目录、HLS 目录下的所有文件
        - 内存状态（任务缓存、运行中任务、HLS 进程）

        注意：该操作不可恢复，仅用于开发/测试环境的一键重置。
        """
        # 清空数据库记录
        with SessionLocal() as db:
            self._clear_database(db)

        # 清理文件系统内容（保留根目录）
        self._clear_directory_contents(SCREENSHOT_BASE)
        self._clear_directory_contents(HLS_BASE)

        # 停止并清空 HLS 进程
        for key, proc in list(HLS_PROCS.items()):
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception as e:
                print(f"[WARN] 停止 HLS 进程失败: {key}, err={e}")
            finally:
                HLS_PROCS.pop(key, None)

        # 清空内存状态
        TASK_STORE.clear()
        RUNNING_KEYS.clear()

        return {
            "message": "系统业务数据已清空（数据库记录、截图/HLS 文件、内存状态）",
        }

    def redeploy_system(self) -> Dict[str, Any]:
        """
        重新部署系统：
        - 调用 clear_all_data 清空业务数据
        - Drop All + Create All，重新创建数据库结构

        相当于在当前环境下做一次“全新初始化”。
        """
        # 先做一次业务数据清空，确保文件和内存状态干净
        self.clear_all_data()

        # 重建数据库结构
        try:
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"重新部署失败：{e}")

        return {
            "message": "系统已重新部署：数据库结构已重建，业务数据已清空。"
        }

