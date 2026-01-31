"""OCR 异步后台 worker

启动一个后台线程，持续从 OCR_JOB_QUEUE 中取出任务，
为每一张截图执行 OCR 识别，并写入数据库 + OCR_STORE。

这样可以将 OCR 从截图主流程中解耦出来，避免截图速度被 OCR 拖慢。
"""
import threading
import time
from pathlib import Path
from typing import Optional, Tuple, Dict

from sqlalchemy.orm import Session

from app.core.config import OCR_JOB_QUEUE
from app.services.ocr_service import OcrService
from db import SessionLocal
from utils.path_utils import to_rel


_ocr_worker_started = False


def _ocr_worker_loop(poll_interval: float = 0.5) -> None:
    """后台 OCR 线程主循环。

    设计要点：
    - 每次从队列取 1 个任务，失败只影响当前任务，不影响主流程。
    - 使用独立的 SessionLocal，避免与截图线程的事务冲突。
    - 适当 sleep，避免空轮询占用过高 CPU。
    """
    ocr_service = OcrService()
    print("[OCR] 后台 OCR worker 已启动")
    while True:
        try:
            job: Dict = OCR_JOB_QUEUE.get(timeout=poll_interval)
        except Exception:
            # 队列暂时为空，稍作休眠后继续
            time.sleep(poll_interval)
            continue

        image_path_str: str = job.get("image_path", "")
        crop_box: Optional[Tuple[int, int, int, int]] = job.get("crop_box")
        image_path = Path(image_path_str)

        if not image_path.exists():
            print(f"[OCR] 队列任务图片不存在，跳过: {image_path}")
            continue

        try:
            with SessionLocal() as db:  # type: Session
                ocr_service.run_ocr_for_screenshot(
                    image_path=image_path,
                    crop_box=crop_box,
                    db=db,
                    to_rel=to_rel,
                )
        except Exception as e:
            # 单个任务失败只记录日志，不中断整个 worker
            print(f"[WARN] OCR worker 处理任务失败: file={image_path}, err={e}")
        finally:
            OCR_JOB_QUEUE.task_done()


def start_ocr_worker() -> None:
    """启动全局唯一的 OCR 后台线程。"""
    global _ocr_worker_started
    if _ocr_worker_started:
        return
    thread = threading.Thread(target=_ocr_worker_loop, name="ocr-worker", daemon=True)
    thread.start()
    _ocr_worker_started = True


