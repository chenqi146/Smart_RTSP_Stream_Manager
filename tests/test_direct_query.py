"""
直接查询数据库验证过滤逻辑
"""
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import SessionLocal
from models import Task
from sqlalchemy import or_, and_

def test_channel_filter():
    """测试通道过滤逻辑"""
    date = "2025-11-07"
    channel_value = "c2"
    
    with SessionLocal() as db:
        # 测试1: 直接使用Task.channel过滤
        query1 = db.query(Task).filter(Task.date == date)
        total1 = query1.count()
        print(f"测试1 - 只按日期过滤: {total1}条")
        
        # 测试2: 使用channel字段过滤
        query2 = db.query(Task).filter(
            Task.date == date,
            Task.channel == channel_value
        )
        total2 = query2.count()
        print(f"测试2 - 按日期+channel字段过滤 (channel='{channel_value}'): {total2}条")
        
        # 测试3: 使用OR条件（当前代码的逻辑）
        query3 = db.query(Task).filter(
            Task.date == date,
            or_(
                Task.channel == channel_value,
                and_(Task.channel.is_(None), Task.rtsp_url.ilike(f"%/{channel_value}/%")),
            )
        )
        total3 = query3.count()
        print(f"测试3 - 按日期+OR条件过滤: {total3}条")
        
        # 测试4: 检查channel字段为None的情况
        none_count = db.query(Task).filter(
            Task.date == date,
            Task.channel.is_(None)
        ).count()
        print(f"测试4 - channel字段为None的数量: {none_count}条")
        
        # 测试5: 检查实际数据
        sample = db.query(Task).filter(
            Task.date == date,
            Task.channel == channel_value
        ).first()
        if sample:
            print(f"测试5 - 样本数据: ID={sample.id}, IP={sample.ip}, Channel={sample.channel}, RTSP={sample.rtsp_url[:60]}...")
        
        # 测试6: 检查不同channel的数据
        print("\n测试6 - 各通道数据统计:")
        from sqlalchemy import func
        stats = (
            db.query(Task.channel, func.count(Task.id).label('count'))
            .filter(Task.date == date)
            .group_by(Task.channel)
            .all()
        )
        for ch, count in stats:
            print(f"  Channel={ch}: {count}条")

if __name__ == "__main__":
    test_channel_filter()

