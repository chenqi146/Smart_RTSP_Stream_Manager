import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from sqlalchemy.orm import Session

from models import Screenshot


def capture_frame(
    rtsp_url: str,
    output_path: Path,
    warmup_frames: int = 20,
    timeout_sec: int = 10,
    db: Optional[Session] = None,
    task_id: Optional[int] = None,
    to_rel=None,
) -> bool:
    """
    Capture a single frame from RTSP and save as image.
    Returns True if saved successfully. If db provided, insert Screenshot.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 设置RTSP流选项：增加超时时间和缓冲区大小
    # 注意：这些选项需要在创建VideoCapture时通过环境变量或URL参数设置
    # OpenCV的VideoCapture对RTSP流的超时控制有限，主要通过FFmpeg后端实现
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    
    # 设置缓冲区大小（减少延迟）
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    if not cap.isOpened():
        print(f"[ERROR] 无法打开RTSP流: {rtsp_url}")
        print(f"[INFO] 提示：如果使用s1主码流失败，可以尝试使用s0子码流（低分辨率但更稳定）")
        return False

    # 获取并记录流的分辨率信息
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[INFO] RTSP流分辨率: {frame_width}x{frame_height}, FPS: {fps}, URL: {rtsp_url}")

    start = time.time()
    frame: Optional[object] = None
    grabbed = False

    try:
        # warm-up frames
        for _ in range(warmup_frames):
            grabbed, frame = cap.read()
            if not grabbed:
                break
            if time.time() - start > timeout_sec:
                break

        if not grabbed or frame is None:
            print(f"[ERROR] 无法从RTSP流读取帧: {rtsp_url}")
            return False
        
        # 记录实际捕获的帧分辨率
        actual_height, actual_width = frame.shape[:2]
        print(f"[INFO] 捕获的帧分辨率: {actual_width}x{actual_height}, 准备保存到: {output_path}")

        # 目标输出分辨率（统一为 1920x1080）
        target_width, target_height = 1920, 1080
        try:
            # 第一步：直接缩放到目标分辨率
            if actual_width != target_width or actual_height != target_height:
                frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
                print(f"[INFO] 已将帧缩放为目标分辨率: {target_width}x{target_height}")
        except Exception as e:
            print(f"[WARN] 直接缩放到 1920x1080 失败，尝试使用画布方式适配: {e}")

        # 第二步：确保最终帧尺寸一定是 1920x1080（必要时填充到画布中）
        final_h, final_w = frame.shape[:2]
        if final_w != target_width or final_h != target_height:
            try:
                canvas = np.zeros((target_height, target_width, 3), dtype=frame.dtype)
                # 等比缩放后居中贴到画布
                scale = min(target_width / final_w, target_height / final_h)
                new_w, new_h = int(final_w * scale), int(final_h * scale)
                resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                x0 = (target_width - new_w) // 2
                y0 = (target_height - new_h) // 2
                canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
                frame = canvas
                print(f"[INFO] 使用画布方式适配为目标分辨率: {target_width}x{target_height}")
            except Exception as e:
                print(f"[WARN] 使用画布方式适配 1920x1080 失败，将使用当前分辨率保存: {e}")

        # 此时 frame.shape 应尽量为 (1080, 1920, 3)
        final_h, final_w = frame.shape[:2]
        print(f"[INFO] 最终保存帧分辨率: {final_w}x{final_h}, 输出文件: {output_path}")

        saved = cv2.imwrite(str(output_path), frame)
        if saved and db and task_id is not None:
            rel = to_rel(output_path) if to_rel else str(output_path)
            try:
                # 检查该任务是否已有截图记录，确保每个任务只有一张截图
                existing_shot = db.query(Screenshot).filter(Screenshot.task_id == task_id).first()
                if existing_shot:
                    # 如果已存在，更新现有记录的文件路径
                    existing_shot.file_path = rel
                    existing_shot.is_duplicate = False  # 重置去重标记
                    existing_shot.kept_path = None  # 清空保留路径
                    # 重置 YOLO 状态，等待异步 Worker 重新检测
                    existing_shot.yolo_status = "pending"
                    existing_shot.yolo_last_error = None
                    db.commit()
                    print(f"[INFO] 更新任务 {task_id} 的截图记录: {rel}")
                else:
                    # 如果不存在，创建新记录
                    shot = Screenshot(task_id=task_id, file_path=rel)
                    db.add(shot)
                    db.commit()
                    print(f"[INFO] 创建任务 {task_id} 的截图记录: {rel}")
            except Exception as e:
                # 如果任务不存在（外键约束错误），记录警告但不中断流程
                print(f"[WARN] Failed to save screenshot to DB (task_id={task_id} may not exist): {e}")
                db.rollback()
        return bool(saved)
    finally:
        cap.release()

