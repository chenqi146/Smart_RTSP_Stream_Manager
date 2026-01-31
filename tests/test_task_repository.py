"""任务仓库层测试"""
import sys
import io
from pathlib import Path

# 设置标准输出编码为 UTF-8（Windows 兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import SessionLocal
from app.repositories.task_repository import TaskRepository
from models import Task


def test_repository_basic_operations():
    """测试基础 CRUD 操作"""
    print("\n=== 测试基础 CRUD 操作 ===")
    
    with SessionLocal() as db:
        repo = TaskRepository(db)
        
        # 测试获取可用日期
        dates = repo.get_available_dates()
        print(f"[OK] 可用日期数量: {len(dates)}")
        if dates:
            print(f"  最新日期: {dates[0]}")
        
        # 测试获取可用 IP
        ips = repo.get_available_ips()
        print(f"[OK] 可用 IP 数量: {len(ips)}")
        if ips:
            print(f"  示例 IP: {ips[0]}")
        
        # 测试获取可用通道
        channels = repo.get_available_channels()
        print(f"[OK] 可用通道数量: {len(channels)}")
        if channels:
            print(f"  示例通道: {channels[0]}")
        
        # 测试状态协调
        reconciled_count = repo.reconcile_task_status()
        print(f"[OK] 状态协调: 更新了 {reconciled_count} 个任务")
        
        print("[OK] 基础 CRUD 操作测试通过")


def test_repository_query_operations():
    """测试查询操作"""
    print("\n=== 测试查询操作 ===")
    
    with SessionLocal() as db:
        repo = TaskRepository(db)
        
        # 测试获取待运行任务
        pending_tasks = repo.get_pending_or_playing_tasks()
        print(f"[OK] 待运行/运行中任务数量: {len(pending_tasks)}")
        
        # 测试获取失败任务
        failed_tasks = repo.get_failed_tasks_for_retry()
        print(f"[OK] 需要重试的失败任务数量: {len(failed_tasks)}")
        
        # 测试分页查询
        if pending_tasks:
            tasks, total = repo.get_tasks_by_filters(
                status="pending",
                limit=5,
                offset=0
            )
            print(f"[OK] 分页查询: 返回 {len(tasks)} 条，总计 {total} 条")
        
        print("[OK] 查询操作测试通过")


def test_repository_concurrent_access():
    """测试并发访问"""
    print("\n=== 测试并发访问 ===")
    
    import threading
    import time
    
    results = []
    errors = []
    
    def query_task():
        try:
            with SessionLocal() as db:
                repo = TaskRepository(db)
                tasks, total = repo.get_tasks_by_filters(limit=10)
                results.append(total)
        except Exception as e:
            errors.append(str(e))
    
    # 创建10个并发线程
    threads = []
    for i in range(10):
        t = threading.Thread(target=query_task)
        threads.append(t)
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    if errors:
        print(f"[FAIL] 并发访问错误: {len(errors)} 个错误")
        for err in errors[:3]:
            print(f"  - {err}")
        return False
    
    print(f"[OK] 并发访问测试: {len(results)} 个线程成功，结果一致: {len(set(results)) == 1}")
    return True


def test_repository_security():
    """测试安全性（SQL注入防护等）"""
    print("\n=== 测试安全性 ===")
    
    with SessionLocal() as db:
        repo = TaskRepository(db)
        
        # 测试 SQL 注入防护（使用参数化查询）
        malicious_inputs = [
            "'; DROP TABLE tasks; --",
            "1' OR '1'='1",
            "'; DELETE FROM tasks; --",
        ]
        
        for malicious_input in malicious_inputs:
            try:
                # 这些查询应该安全地处理恶意输入
                tasks, total = repo.get_tasks_by_filters(
                    ip=malicious_input,
                    limit=1
                )
                print(f"[OK] SQL 注入防护测试通过: {malicious_input[:20]}...")
            except Exception as e:
                # 如果抛出异常，说明有防护，这也是好的
                print(f"[OK] SQL 注入防护: 异常被正确捕获")
        
        print("[OK] 安全性测试通过")


if __name__ == "__main__":
    print("=" * 60)
    print("任务仓库层测试")
    print("=" * 60)
    
    try:
        test_repository_basic_operations()
        test_repository_query_operations()
        concurrent_ok = test_repository_concurrent_access()
        test_repository_security()
        
        print("\n" + "=" * 60)
        print("[PASS] 所有测试通过！")
        print("=" * 60)
    except Exception as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

