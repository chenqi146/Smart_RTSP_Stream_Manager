"""数据库表结构检查和自动迁移工具

在系统启动时自动检查数据库表结构，如果缺少字段则自动添加。
"""

from sqlalchemy import text, inspect
from db import engine
from typing import List, Tuple


def check_and_add_missing_columns() -> List[str]:
    """检查并添加缺失的数据库字段。
    
    返回:
        List[str]: 添加的字段列表
    """
    added_columns = []
    
    try:
        with engine.connect() as conn:
            # 检查 parking_changes 表的 vehicle_features 字段
            if not _column_exists(conn, "parking_changes", "vehicle_features"):
                print("[DB Migration] 检测到 parking_changes 表缺少 vehicle_features 字段，正在添加...")
                conn.execute(text("""
                    ALTER TABLE parking_changes 
                    ADD COLUMN vehicle_features JSON NULL 
                    COMMENT '车辆视觉特征（JSON格式）：包含HSV直方图、宽高比、雨刮等特征，用于车辆重识别'
                """))
                conn.commit()  # 显式提交 ALTER TABLE 操作
                added_columns.append("parking_changes.vehicle_features")
                print("[DB Migration] ✓ 已添加 vehicle_features 字段到 parking_changes 表")
            
            # 可以在这里添加更多字段检查
            # 例如：
            # if not _column_exists(conn, "table_name", "column_name"):
            #     conn.execute(text("ALTER TABLE ..."))
            #     conn.commit()
            #     added_columns.append("table_name.column_name")
            
    except Exception as e:
        print(f"[DB Migration] 检查数据库字段时出错: {e}")
        import traceback
        traceback.print_exc()
        # 不抛出异常，允许系统继续启动
    
    return added_columns


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    """检查表中是否存在指定字段。
    
    参数:
        conn: 数据库连接
        table_name: 表名
        column_name: 字段名
    
    返回:
        bool: 字段是否存在
    """
    try:
        # 首先尝试使用 SQLAlchemy 的 inspect（更可靠）
        inspector = inspect(engine)
        if inspector.has_table(table_name):
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        return False
    except Exception:
        # 如果 inspect 失败，尝试使用 MySQL 的 INFORMATION_SCHEMA
        try:
            result = conn.execute(text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = :table_name 
                AND COLUMN_NAME = :column_name
            """), {"table_name": table_name, "column_name": column_name})
            return result.fetchone() is not None
        except Exception as e:
            print(f"[DB Migration] 检查字段 {table_name}.{column_name} 时出错: {e}")
            return False


def check_database_schema() -> Tuple[bool, List[str]]:
    """检查数据库表结构完整性。
    
    返回:
        Tuple[bool, List[str]]: (是否完整, 缺失的字段列表)
    """
    missing_fields = []
    
    try:
        with engine.connect() as conn:
            # 检查关键字段
            required_fields = [
                ("parking_changes", "vehicle_features"),
                # 可以添加更多需要检查的字段
            ]
            
            for table_name, column_name in required_fields:
                if not _column_exists(conn, table_name, column_name):
                    missing_fields.append(f"{table_name}.{column_name}")
    
    except Exception as e:
        print(f"[DB Migration] 检查数据库结构时出错: {e}")
        return False, []
    
    return len(missing_fields) == 0, missing_fields
