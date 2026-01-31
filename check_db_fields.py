"""
检查数据库字段和实际数据
"""
import sys
from pathlib import Path

# 添加项目路径
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import SessionLocal
from models import Task

def check_task_fields():
    """检查Task表的字段和实际数据"""
    with SessionLocal() as db:
        # 获取一个样本任务
        sample_task = db.query(Task).first()
        if not sample_task:
            print("数据库中没有任务数据")
            return
        
        print("="*60)
        print("Task表字段检查")
        print("="*60)
        print(f"\n样本任务ID: {sample_task.id}")
        print(f"日期: {sample_task.date}")
        print(f"RTSP URL: {sample_task.rtsp_url}")
        print(f"IP字段: {sample_task.ip} (类型: {type(sample_task.ip)})")
        print(f"Channel字段: {sample_task.channel} (类型: {type(sample_task.channel)})")
        print(f"状态: {sample_task.status}")
        
        # 检查不同通道的数据
        print("\n" + "="*60)
        print("不同通道的数据统计")
        print("="*60)
        
        # 统计channel字段的值
        channels = db.query(Task.channel).distinct().all()
        print(f"\nChannel字段的唯一值:")
        for (ch,) in channels:
            count = db.query(Task).filter(Task.channel == ch).count()
            print(f"  {ch}: {count}条")
        
        # 检查IP字段
        print("\n" + "="*60)
        print("IP字段统计")
        print("="*60)
        ips = db.query(Task.ip).distinct().limit(10).all()
        print(f"\nIP字段的唯一值（前10个）:")
        for (ip,) in ips:
            if ip:
                count = db.query(Task).filter(Task.ip == ip).count()
                print(f"  {ip}: {count}条")
        
        # 检查特定日期的数据
        print("\n" + "="*60)
        print("特定日期的数据检查 (2025-11-07)")
        print("="*60)
        date = "2025-11-07"
        tasks = db.query(Task).filter(Task.date == date).limit(10).all()
        print(f"\n前10条任务:")
        for task in tasks:
            print(f"  ID={task.id}, IP={task.ip}, Channel={task.channel}, RTSP={task.rtsp_url[:60]}...")
        
        # 检查IP和Channel的组合
        print("\n" + "="*60)
        print("IP和Channel组合统计 (2025-11-07)")
        print("="*60)
        from sqlalchemy import func
        combinations = (
            db.query(Task.ip, Task.channel, func.count(Task.id).label('count'))
            .filter(Task.date == date)
            .group_by(Task.ip, Task.channel)
            .all()
        )
        for ip, channel, count in combinations:
            print(f"  IP={ip}, Channel={channel}: {count}条")

if __name__ == "__main__":
    check_task_fields()

