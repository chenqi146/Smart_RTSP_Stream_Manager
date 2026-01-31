# -*- coding: utf-8 -*-
"""更新数据库表结构，添加 vehicle_features 字段"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import engine
from sqlalchemy import text

def update_schema():
    """添加 vehicle_features 字段到 parking_changes 表"""
    with engine.connect() as conn:
        try:
            # 检查字段是否已存在
            result = conn.execute(text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'parking_changes' 
                AND COLUMN_NAME = 'vehicle_features'
            """))
            exists = result.fetchone() is not None
            
            if exists:
                print("字段 vehicle_features 已存在，无需添加")
            else:
                # 添加字段
                conn.execute(text("""
                    ALTER TABLE parking_changes 
                    ADD COLUMN vehicle_features JSON NULL 
                    COMMENT '车辆视觉特征（JSON格式）：包含HSV直方图、宽高比、雨刮等特征，用于车辆重识别'
                """))
                conn.commit()
                print("已成功添加 vehicle_features 字段到 parking_changes 表")
        except Exception as e:
            print(f"更新数据库表结构时出错: {e}")
            print("如果字段已存在，可以忽略此错误")
            conn.rollback()

if __name__ == "__main__":
    update_schema()
