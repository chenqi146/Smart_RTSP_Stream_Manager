"""应用生命周期管理"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.background.schedulers import start_schedule_checker
from app.background.task_runners import start_pending_runner
from app.background.retry_checker import start_failed_task_retry_checker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理：启动和关闭时执行的操作
    
    启动时：
    - 启动自动分配配置定时任务检查器
    - 启动待运行任务自动执行器
    - 启动失败任务自动重试检查器
    
    关闭时：
    - 清理资源（如果需要）
    """
    # 启动时执行
    start_schedule_checker()
    print("[INFO] 自动分配配置定时任务检查器已启动")
    
    start_pending_runner()
    print("[INFO] 待运行任务自动执行器已启动")
    
    start_failed_task_retry_checker()
    print("[INFO] 失败任务自动重试检查器已启动")
    
    yield
    
    # 关闭时执行（如果需要清理资源，可以在这里添加）
    # 目前不需要清理操作

