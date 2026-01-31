"""路径处理工具函数"""
from pathlib import Path
from app.core.config import SCREENSHOT_BASE


def to_rel(p: Path) -> str:
    """
    将路径转为相对于 SCREENSHOT_BASE 的相对路径字符串；否则返回绝对路径字符串。
    
    Args:
        p: 路径对象
        
    Returns:
        相对路径字符串或绝对路径字符串
    """
    try:
        abs_path = p.resolve()
        rel = abs_path.relative_to(SCREENSHOT_BASE)
        return rel.as_posix()
    except Exception:
        return str(p)


def build_image_url(p: Path) -> tuple[str, bool]:
    """
    构造图片可访问 URL；如果文件缺失，标记 missing。
    
    Args:
        p: 图片路径对象
        
    Returns:
        (url, missing) 元组
    """
    # 若是相对路径，先补全到截图根目录
    if not p.is_absolute():
        p = SCREENSHOT_BASE / p

    # 如果文件不存在且可能是相对路径，尝试再次拼接
    missing = not p.exists()
    try:
        abs_path = p.resolve()
        rel = abs_path.relative_to(SCREENSHOT_BASE)
        return f"/shots/{rel.as_posix()}", missing
    except Exception:
        # 不在截图目录下，走代理端点
        return f"/api/image_proxy?path={p.as_posix()}", missing

