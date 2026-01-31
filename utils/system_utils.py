# -*- coding: utf-8 -*-
"""
系统资源检测工具
用于自动检测服务器性能并计算合适的并发数
"""

import os
import sys
import psutil
import multiprocessing
from typing import Tuple, Optional


def get_system_resources() -> dict:
    """
    获取系统资源信息
    
    Returns:
        dict: 包含 CPU 核心数、内存、可用内存等信息
    """
    try:
        # CPU 核心数（逻辑核心数，包含超线程）
        cpu_count = multiprocessing.cpu_count()
        
        # CPU 物理核心数
        try:
            cpu_physical_count = psutil.cpu_count(logical=False) or cpu_count
        except:
            cpu_physical_count = cpu_count
        
        # 内存信息（GB）
        mem = psutil.virtual_memory()
        total_mem_gb = mem.total / (1024 ** 3)
        available_mem_gb = mem.available / (1024 ** 3)
        mem_usage_percent = mem.percent
        
        # CPU 使用率（取平均值，采样间隔 1 秒）
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
        except:
            cpu_percent = 0
        
        return {
            "cpu_count": cpu_count,
            "cpu_physical_count": cpu_physical_count,
            "total_mem_gb": round(total_mem_gb, 2),
            "available_mem_gb": round(available_mem_gb, 2),
            "mem_usage_percent": mem_usage_percent,
            "cpu_percent": cpu_percent,
        }
    except Exception as e:
        print(f"[WARN] 获取系统资源信息失败: {e}")
        # 回退到基本检测
        return {
            "cpu_count": os.cpu_count() or 2,
            "cpu_physical_count": os.cpu_count() or 2,
            "total_mem_gb": 4.0,
            "available_mem_gb": 2.0,
            "mem_usage_percent": 50.0,
            "cpu_percent": 0.0,
        }


def calculate_optimal_concurrency(
    db_pool_size: int = 20,
    db_max_overflow: int = 40,
    mem_per_task_gb: float = 0.2,  # 每个任务预估占用 200MB 内存
    cpu_per_task: float = 0.25,  # 每个任务预估占用 0.25 个 CPU 核心
) -> Tuple[int, int]:
    """
    根据服务器资源自动计算最优并发数
    
    Args:
        db_pool_size: 数据库连接池基础大小
        db_max_overflow: 数据库连接池最大溢出数
        mem_per_task_gb: 每个任务预估占用的内存（GB）
        cpu_per_task: 每个任务预估占用的 CPU 核心数
    
    Returns:
        Tuple[int, int]: (MAX_COMBO_CONCURRENCY, MAX_WORKERS_PER_COMBO)
    """
    try:
        resources = get_system_resources()
        
        cpu_count = resources["cpu_count"]
        cpu_physical_count = resources["cpu_physical_count"]
        available_mem_gb = resources["available_mem_gb"]
        mem_usage_percent = resources["mem_usage_percent"]
        cpu_percent = resources["cpu_percent"]
        
        # 数据库连接池限制
        max_db_connections = db_pool_size + db_max_overflow
        
        # 基于 CPU 的计算
        # 考虑到 RTSP 截图任务主要是 I/O 密集型（网络 + 磁盘），可以适当超过物理核心数
        # 但为了避免过度竞争，建议不超过逻辑核心数的 1.5 倍
        if cpu_percent > 80:
            # CPU 使用率过高，降低并发
            cpu_based_max = max(2, int(cpu_physical_count * 0.5))
        elif cpu_percent > 60:
            # CPU 使用率较高，适度并发
            cpu_based_max = max(4, int(cpu_physical_count * 0.75))
        else:
            # CPU 使用率正常，可以使用更多并发
            cpu_based_max = min(cpu_count * 2, cpu_physical_count * 1.5)
        
        cpu_based_max = max(2, int(cpu_based_max))
        
        # 基于内存的计算
        # 预留 2GB 给系统和数据库，剩余内存分配给任务
        reserved_mem_gb = 2.0
        usable_mem_gb = max(1.0, available_mem_gb - reserved_mem_gb)
        
        # 如果内存使用率超过 80%，降低可用内存估算
        if mem_usage_percent > 80:
            usable_mem_gb *= 0.5
        elif mem_usage_percent > 60:
            usable_mem_gb *= 0.7
        
        # 每个任务预估需要的内存（考虑到并发时峰值更高，加 50% 缓冲）
        actual_mem_per_task_gb = mem_per_task_gb * 1.5
        mem_based_max = max(2, int(usable_mem_gb / actual_mem_per_task_gb))
        
        # 基于数据库连接池的计算
        # 每个任务可能需要 2-3 个数据库连接（查询、更新、事务等）
        connections_per_task = 2.5
        db_based_max = max(2, int(max_db_connections / connections_per_task / 2))  # 除以2是保守估计
        
        # 取三个限制中的最小值，确保不超过任何资源限制
        total_max_concurrency = min(cpu_based_max, mem_based_max, db_based_max)
        
        # 计算全局并发和单组合并发
        # 策略：根据服务器规模和总并发限制，动态调整全局并发和单组合并发
        # RTSP 截图任务主要是 I/O 密集型，可以设置较高的并发数
        
        # 如果总并发限制较小，优先保证全局并发（多个通道组合可以并行）
        if total_max_concurrency <= 6:
            # 小服务器：全局并发 = min(物理核心数, 4)，单组合并发 = 2
            max_combo_concurrency = max(2, min(4, cpu_physical_count))
            max_workers_per_combo = 2
        elif total_max_concurrency <= 12:
            # 中等服务器：全局并发 = min(物理核心数, 6)，单组合并发 = 2-3
            max_combo_concurrency = max(3, min(6, cpu_physical_count))
            max_workers_per_combo = 2
        elif total_max_concurrency <= 24:
            # 较大服务器：全局并发 = min(物理核心数 * 1.2, 8)，单组合并发 = 3
            max_combo_concurrency = max(4, min(8, int(cpu_physical_count * 1.2)))
            max_workers_per_combo = 3
        else:
            # 大服务器：全局并发 = min(物理核心数 * 1.5, 12)，单组合并发 = 4
            max_combo_concurrency = max(6, min(12, int(cpu_physical_count * 1.5)))
            max_workers_per_combo = 4
        
        # 确保不超过总并发限制
        estimated_total = max_combo_concurrency * max_workers_per_combo
        if estimated_total > total_max_concurrency:
            # 如果估算的总并发超过限制，按比例缩小
            ratio = total_max_concurrency / estimated_total
            max_combo_concurrency = max(2, int(max_combo_concurrency * ratio))
            max_workers_per_combo = max(2, int(max_workers_per_combo * ratio))
        
        return max_combo_concurrency, max_workers_per_combo
        
    except Exception as e:
        print(f"[WARN] 自动计算并发数失败: {e}")
        # 回退到保守的默认值
        return 4, 4


def print_system_info():
    """打印系统信息和推荐的并发配置"""
    try:
        resources = get_system_resources()
        max_combo, max_workers = calculate_optimal_concurrency()
        
        print("=" * 60)
        print("系统资源检测结果")
        print("=" * 60)
        print(f"CPU 核心数（逻辑）: {resources['cpu_count']}")
        print(f"CPU 核心数（物理）: {resources['cpu_physical_count']}")
        print(f"CPU 使用率: {resources['cpu_percent']:.1f}%")
        print(f"总内存: {resources['total_mem_gb']:.2f} GB")
        print(f"可用内存: {resources['available_mem_gb']:.2f} GB")
        print(f"内存使用率: {resources['mem_usage_percent']:.1f}%")
        print("")
        print("推荐的并发配置：")
        print(f"  MAX_COMBO_CONCURRENCY (全局并发): {max_combo}")
        print(f"  MAX_WORKERS_PER_COMBO (单组合并发): {max_workers}")
        print(f"  总并发任务数: {max_combo * max_workers}")
        print("=" * 60)
        
        return max_combo, max_workers
    except Exception as e:
        print(f"[ERROR] 打印系统信息失败: {e}")
        return 4, 4


if __name__ == "__main__":
    # 命令行直接运行时，打印系统信息
    print_system_info()

