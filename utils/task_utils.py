"""任务相关工具函数"""
from typing import Optional
from app.core.config import TASK_STORE, RUNNING_KEYS, COMBO_SEM, MAX_COMBO_CONCURRENCY


def make_task_key(date: str, base_rtsp: str, channel: str) -> str:
    """
    生成任务组合的唯一键
    
    Args:
        date: 任务日期
        base_rtsp: RTSP 基础地址
        channel: 通道号
        
    Returns:
        任务键字符串，格式：date::base_rtsp::channel
    """
    base_clean = (base_rtsp or "").rstrip("/")
    channel_clean = channel or ""
    return f"{date}::{base_clean}::{channel_clean}"


def is_task_running(key: str) -> bool:
    """
    检查任务组合是否正在运行
    
    Args:
        key: 任务键
        
    Returns:
        是否正在运行
    """
    return key in RUNNING_KEYS


def acquire_combo_semaphore(blocking: bool = False) -> bool:
    """
    获取组合并发信号量
    
    Args:
        blocking: 是否阻塞等待
        
    Returns:
        是否成功获取
    """
    return COMBO_SEM.acquire(blocking=blocking)


def release_combo_semaphore():
    """释放组合并发信号量"""
    COMBO_SEM.release()


def add_running_key(key: str):
    """添加运行中的任务键"""
    RUNNING_KEYS.add(key)


def remove_running_key(key: str):
    """移除运行中的任务键"""
    RUNNING_KEYS.discard(key)


def get_max_concurrency() -> int:
    """获取最大并发数"""
    return MAX_COMBO_CONCURRENCY

