"""工具类路由模块"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

from app.services.utils_service import UtilsService

router = APIRouter(tags=["工具类"])


# ==================== HLS 流 ====================

@router.get("/api/hls/start")
def start_hls_proxy(rtsp_url: str = Query(..., description="RTSP流地址")):
    """
    On-demand RTSP -> HLS conversion; returns m3u8 URL.
    """
    service = UtilsService()
    return service.start_hls_stream(rtsp_url)


# ==================== 健康检查 ====================

@router.get("/healthz")
def healthz():
    """健康检查端点"""
    service = UtilsService()
    return service.get_health_status()


# ==================== OCR ====================
# OCR功能已移除


# ==================== 图片代理 ====================

@router.get("/api/image_proxy")
def image_proxy(path: str = Query(..., description="图片路径")):
    """
    代理返回任意存在的图片文件（来源于数据库记录）。
    """
    service = UtilsService()
    image_path = service.proxy_image(path)
    return FileResponse(image_path)


# ==================== 静态页面 ====================

@router.get("/", include_in_schema=False)
def index():
    """返回首页静态文件"""
    service = UtilsService()
    index_path = service.get_index_page()
    if index_path:
        return FileResponse(index_path)
    return {"message": "static page not found"}


# ==================== 管理类接口：一键清空 & 重新部署 ====================

@router.post("/api/admin/clear_all")
def clear_all_data():
    """
    清空当前系统的所有业务数据：
    - 数据库中的任务/截图/自动调度规则
    - 截图目录、HLS 目录中的文件
    - 内存中的任务缓存、运行中任务、HLS 进程

    仅建议在开发/测试环境使用。
    """
    service = UtilsService()
    return service.clear_all_data()


@router.post("/api/admin/redeploy")
def redeploy_system():
    """
    重新部署系统：在清空业务数据的基础上，重建数据库表结构。

    相当于在当前环境下做一次“全新初始化”。
    """
    service = UtilsService()
    return service.redeploy_system()


@router.post("/api/admin/backfill_parking_change")
def backfill_parking_change(limit: int = Query(200, ge=1, le=1000, description="每批标记为待检测的截图数量")):
    """
    将历史未做车位变化识别的截图标记为 pending，由车位变化检测 Worker 自动补齐。
    仅影响 yolo_status 为 NULL、done 或 failed 的记录；可多次调用直到返回 marked=0。
    """
    service = UtilsService()
    marked = service.mark_screenshots_pending_for_parking_change(limit=limit)
    return {"message": "已标记为待检测，Worker 将自动处理", "marked": marked}
