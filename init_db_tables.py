# -*- coding: utf-8 -*-
"""
数据库表初始化脚本
用于在部署时确保所有数据库表（包括新表）都被创建
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import engine, Base
from sqlalchemy import text

# 尝试导入所有模型，如果某个模型不存在，记录警告但继续执行
try:
    from models import (
        TaskBatch,
        Task,
        Screenshot,
        AutoScheduleRule,
        NvrConfig,
        ChannelConfig,
        ParkingSpace,
        ParkingChange,
        ParkingChangeSnapshot,
    )
    MINUTE_SCREENSHOT_AVAILABLE = False
    try:
        from models import MinuteScreenshot
        MINUTE_SCREENSHOT_AVAILABLE = True
    except ImportError:
        print("[WARN] MinuteScreenshot 类在 models.py 中不存在，将使用 SQL 直接创建表")
except ImportError as e:
    print(f"[WARN] 部分模型导入失败: {e}")
    MINUTE_SCREENSHOT_AVAILABLE = False

def init_database_tables():
    """创建所有数据库表（如果不存在）"""
    try:
        print("[INFO] 正在创建数据库表（如果不存在）...")
        print("[INFO] 这将创建以下表：")
        print("  - task_batches (任务批次表)")
        print("  - tasks (任务表)")
        print("  - screenshots (截图表)")
        print("  - minute_screenshots (每分钟截图表)")
        print("  - auto_schedule_rules (自动调度规则表)")
        print("  - nvr_configs (NVR配置表)")
        print("  - channel_configs (通道配置表)")
        print("  - parking_spaces (停车位表)")
        print("  - parking_changes (停车变化表)")
        print("  - parking_change_snapshots (停车变化快照表)")
        print("")
        
        # 检查 metadata 中是否包含所有表
        table_names = [t.name for t in Base.metadata.sorted_tables]
        print(f"[DEBUG] Metadata 中包含的表: {', '.join(sorted(table_names))}")
        
        # 特别检查 minute_screenshots 表是否在 metadata 中
        if 'minute_screenshots' in table_names:
            print("[DEBUG] ✅ minute_screenshots 表已在 metadata 中")
        else:
            print("[WARN] ⚠️  minute_screenshots 表不在 metadata 中，可能导入失败")
            print("[DEBUG] 尝试重新导入 MinuteScreenshot...")
            try:
                from models import MinuteScreenshot
                # 强制注册到 metadata
                MinuteScreenshot.__table__.create(bind=engine, checkfirst=True)
                print("[DEBUG] ✅ 已单独创建 minute_screenshots 表")
            except Exception as import_err:
                print(f"[ERROR] 重新导入失败: {import_err}")
                import traceback
                traceback.print_exc()
        
        # 创建所有表
        print("[INFO] 执行 Base.metadata.create_all()...")
        Base.metadata.create_all(bind=engine)
        
        # 验证表是否创建成功（查询数据库）
        print("[INFO] 验证表是否创建成功...")
        from sqlalchemy import inspect
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        print(f"[DEBUG] 数据库中现有的表: {', '.join(sorted(existing_tables))}")
        
        # 特别处理 minute_screenshots 表
        if 'minute_screenshots' in existing_tables:
            print("[INFO] ✅ minute_screenshots 表已成功创建")
        else:
            print("[WARN] ⚠️  minute_screenshots 表未在数据库中找到")
            print("[INFO] 尝试使用 SQL 直接创建 minute_screenshots 表...")
            try:
                # 使用 SQL 直接创建表（如果模型类不存在）
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS minute_screenshots (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    task_id INT NOT NULL,
                    minute_index INT NOT NULL,
                    start_ts BIGINT NOT NULL,
                    end_ts BIGINT NOT NULL,
                    file_path VARCHAR(512) NOT NULL DEFAULT '',
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    error VARCHAR(512) NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_task_minute (task_id, minute_index),
                    INDEX idx_task_time (task_id, start_ts, end_ts),
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    UNIQUE KEY uq_task_minute_index (task_id, minute_index)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='每分钟截图表：记录每个任务的每分钟截图文件';
                """
                with engine.connect() as conn:
                    conn.execute(text(create_table_sql))
                    conn.commit()
                print("[INFO] ✅ 已使用 SQL 创建 minute_screenshots 表")
            except Exception as create_err:
                print(f"[ERROR] SQL 创建失败: {create_err}")
                import traceback
                traceback.print_exc()
                # 如果 SQL 创建也失败，尝试使用模型类（如果可用）
                if MINUTE_SCREENSHOT_AVAILABLE:
                    try:
                        from models import MinuteScreenshot
                        MinuteScreenshot.__table__.create(bind=engine, checkfirst=True)
                        print("[INFO] ✅ 已使用模型类创建 minute_screenshots 表")
                    except Exception as model_err:
                        print(f"[ERROR] 模型类创建也失败: {model_err}")
        
        print("[INFO] ✅ 数据库表创建完成")
        return True
    except Exception as e:
        print(f"[ERROR] 数据库表创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = init_database_tables()
    sys.exit(0 if success else 1)

