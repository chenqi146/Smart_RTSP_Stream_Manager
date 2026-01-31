from pathlib import Path
from typing import Dict, Optional, Tuple
import re
from datetime import datetime

import cv2
from sqlalchemy.orm import Session

try:
    import easyocr
except ImportError:  # pragma: no cover - optional dependency
    easyocr = None

from models import OcrResult, Screenshot

TIME_REGEX = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


def _load_reader(lang: str = "en"):
    if easyocr is None:
        raise RuntimeError("easyocr is not installed. Please install easyocr first.")
    return easyocr.Reader([lang], gpu=False)


def _ensure_ocr_row_for_no_result(
    image_path: Path,
    db: Optional[Session],
    to_rel,
) -> None:
    """
    当没有识别到时间水印时，如果有 Screenshot 记录、但还没有 OcrResult 记录，
    也写入一条“已处理但未识别到”的 OCR 记录（detected_time 为空，confidence=0）。

    这样前端就可以区分：
    - 没有 OcrResult 记录          => OCR 未处理
    - 有 OcrResult 但没有时间字段  => OCR 已处理但未识别到
    """
    if not db:
        return

    key_path = to_rel(image_path) if to_rel else str(image_path)
    shot = db.query(Screenshot).filter_by(file_path=key_path).first()
    if not shot:
        return

    # 已经有 OCR 记录则不重复写入
    existing = db.query(OcrResult).filter_by(screenshot_id=shot.id).first()
    if existing:
        return

    ocr = OcrResult(
        screenshot_id=shot.id,
        detected_time=None,
        detected_timestamp=None,
        confidence=0.0,
    )
    db.add(ocr)
    db.commit()


def read_timestamp_from_image(
    image_path: Path,
    crop_box: Optional[Tuple[int, int, int, int]] = None,
    lang: str = "en",
    db: Optional[Session] = None,
    to_rel=None,
) -> Optional[Dict]:
    """
    从图片中识别时间水印。

    - crop_box: (x1, y1, x2, y2)，用于限制 OCR 区域（例如左上角时间水印）。
    - 返回: 若识别到时间字符串，返回 {"text":..., "confidence":...}；否则返回 None。

    同时：
    - 识别成功时写入 OcrResult（含 detected_time / detected_timestamp / confidence）；
    - 识别失败时，如果有对应 Screenshot 且还没有 OcrResult，会写入一条
      “已处理但未识别到”的记录（detected_time 为空，confidence=0）。
    """
    img = cv2.imread(str(image_path))
    if img is None:
        # 读取不到图片，视为未处理，不写入 OCR 记录
        return None

    if crop_box:
        x1, y1, x2, y2 = crop_box
        img = img[y1:y2, x1:x2]

    reader = _load_reader(lang)

    # 第一次直接用原图识别
    results = reader.readtext(img)

    # 如果第一次完全没结果，做一次简单预处理（灰度化）再试一次，提高一点识别成功率
    if not results:
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            results = reader.readtext(gray)
        except Exception:
            # 预处理失败时，不影响原有逻辑
            pass

    for _, text, conf in results:
        match = TIME_REGEX.search(text)
        if match:
            found = {"text": match.group(0), "confidence": conf}
            if db:
                key_path = to_rel(image_path) if to_rel else str(image_path)
                shot = db.query(Screenshot).filter_by(file_path=key_path).first()
                if shot:
                    ts = None
                    try:
                        ts = int(datetime.strptime(found["text"], "%Y-%m-%d %H:%M:%S").timestamp())
                    except Exception:
                        pass
                    ocr = OcrResult(
                        screenshot_id=shot.id,
                        detected_time=found["text"],
                        detected_timestamp=ts,
                        confidence=conf,
                    )
                    db.add(ocr)
                    db.commit()
            return found

    # 没有任何时间水印被识别到，标记为“已处理但未识别到”
    _ensure_ocr_row_for_no_result(image_path, db, to_rel)
    return None

