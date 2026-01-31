"""OCR 相关业务逻辑服务

负责在截图完成后识别画面中的时间水印，并将结果写入数据库的 OcrResult 表，
同时更新全局 OCR_STORE 以兼容现有的 /api/ocr/{date} 接口。
"""
from pathlib import Path
from typing import Optional, Dict, Tuple

from sqlalchemy.orm import Session

from app.core.config import OCR_STORE, OCR_JOB_QUEUE
from services.ocr_reader import read_timestamp_from_image


class OcrService:
    """封装 OCR 识别和结果存储的服务类。"""

    def __init__(self) -> None:
        # 目前没有需要初始化的状态，保留扩展点
        pass

    def run_ocr_for_screenshot(
        self,
        image_path: Path,
        crop_box: Optional[Tuple[int, int, int, int]],
        db: Session,
        to_rel,
    ) -> Optional[Dict]:
        """对单张截图执行时间 OCR，并写入数据库与全局缓存。

        :param image_path: 截图文件的绝对路径
        :param crop_box:   OCR 裁剪区域 (x1, y1, x2, y2)，允许为 None
        :param db:         SQLAlchemy 会话
        :param to_rel:     将绝对路径转换为相对路径的函数（与截图存库逻辑保持一致）
        :return:           OCR 结果 dict，或 None
        """
        if not image_path.exists():
            print(f"[OCR] 跳过：图片文件不存在，无法识别时间水印: {image_path}")
            return None

        print(f"[OCR] 开始识别时间水印: {image_path}")
        result = read_timestamp_from_image(
            image_path=image_path,
            crop_box=crop_box,
            db=db,
            to_rel=to_rel,
        )
        if result:
            # 使用与其他模块一致的 key（绝对路径字符串）
            OCR_STORE[str(image_path)] = result
            detected_time = result.get("detected_time") or result.get("ocr_detected_time")
            corrected_time = result.get("corrected_time") or result.get("ocr_corrected_time")
            confidence = result.get("confidence")
            print(
                f"[OCR] 识别完成: file={image_path}, "
                f"detected_time={detected_time}, corrected_time={corrected_time}, confidence={confidence}"
            )
        else:
            print(f"[OCR] 未能从截图中识别到时间水印: {image_path}")
        return result

    # ============ 新增：异步 OCR 接口（仅入队，由后台线程消费） ============

    def enqueue_ocr_job(
        self,
        image_path: Path,
        crop_box: Optional[Tuple[int, int, int, int]],
    ) -> None:
        """将 OCR 任务加入后台队列，由独立线程异步处理。

        后台线程会自行创建数据库会话并调用 run_ocr_for_screenshot，
        因此这里不需要也不应该持有 Session。
        """
        if not image_path.exists():
            print(f"[OCR] 跳过入队：图片文件不存在，无法识别时间水印: {image_path}")
            return
        job = {
            "image_path": str(image_path),
            "crop_box": crop_box,
        }
        try:
            OCR_JOB_QUEUE.put_nowait(job)
            print(f"[OCR] 已加入异步识别队列: {image_path}")
        except Exception as e:
            # 入队失败时退化为同步执行，避免彻底丢失 OCR 功能
            print(f"[WARN] OCR 入队失败，回退为同步识别: {e}")
            from db import SessionLocal  # 延迟导入避免循环依赖
            from utils.path_utils import to_rel as default_to_rel

            with SessionLocal() as db:
                self.run_ocr_for_screenshot(
                    image_path=image_path,
                    crop_box=crop_box,
                    db=db,
                    to_rel=default_to_rel,
                )


