"""测试运行脚本"""
import sys
import subprocess
import time
import requests
from pathlib import Path
import io

# 设置标准输出编码为 UTF-8（Windows 兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent
BASE_URL = "http://localhost:8005"


def check_server_running():
    """检查服务器是否运行"""
    try:
        response = requests.get(f"{BASE_URL}/healthz", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def run_repository_tests():
    """运行仓库层测试"""
    print("\n" + "=" * 60)
    print("1. 运行仓库层测试")
    print("=" * 60)
    
    result = subprocess.run(
        [sys.executable, "tests/test_task_repository.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    print(result.stdout)
    if result.stderr:
        print("错误输出:", result.stderr)
    
    return result.returncode == 0


def run_api_tests():
    """运行 API 集成测试"""
    print("\n" + "=" * 60)
    print("2. 运行任务管理 API 集成测试")
    print("=" * 60)
    
    if not check_server_running():
        print("[WARN] 服务器未运行，跳过 API 测试")
        print("   请先启动服务器: python app/main.py")
        return False
    
    result = subprocess.run(
        [sys.executable, "tests/test_task_api_integration.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    print(result.stdout)
    if result.stderr:
        print("错误输出:", result.stderr)
    
    return result.returncode == 0


def run_image_api_tests():
    """运行图片管理 API 集成测试"""
    print("\n" + "=" * 60)
    print("3. 运行图片管理 API 集成测试")
    print("=" * 60)
    
    if not check_server_running():
        print("[WARN] 服务器未运行，跳过 API 测试")
        print("   请先启动服务器: python app/main.py")
        return False
    
    result = subprocess.run(
        [sys.executable, "tests/test_image_api_integration.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    print(result.stdout)
    if result.stderr:
        print("错误输出:", result.stderr)
    
    return result.returncode == 0


def run_auto_schedule_api_tests():
    """运行自动调度规则 API 集成测试"""
    print("\n" + "=" * 60)
    print("4. 运行自动调度规则 API 集成测试")
    print("=" * 60)
    
    if not check_server_running():
        print("[WARN] 服务器未运行，跳过 API 测试")
        print("   请先启动服务器: python app/main.py")
        return False
    
    result = subprocess.run(
        [sys.executable, "tests/test_auto_schedule_api_integration.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    print(result.stdout)
    if result.stderr:
        print("错误输出:", result.stderr)
    
    return result.returncode == 0


def run_utils_api_tests():
    """运行工具类 API 集成测试"""
    print("\n" + "=" * 60)
    print("5. 运行工具类 API 集成测试")
    print("=" * 60)
    
    if not check_server_running():
        print("[WARN] 服务器未运行，跳过 API 测试")
        print("   请先启动服务器: python app/main.py")
        return False
    
    result = subprocess.run(
        [sys.executable, "tests/test_utils_api_integration.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    print(result.stdout)
    if result.stderr:
        print("错误输出:", result.stderr)
    
    return result.returncode == 0


def main():
    """主函数"""
    print("=" * 60)
    print("Smart RTSP Stream Manager 模块重构测试")
    print("=" * 60)
    
    # 检查服务器
    server_running = check_server_running()
    if server_running:
        print("[OK] 服务器正在运行")
    else:
        print("[WARN] 服务器未运行")
        print("   仓库层测试可以运行，但 API 测试需要服务器运行")
    
    # 运行测试
    results = []
    
    # 1. 仓库层测试（不需要服务器）
    repo_ok = run_repository_tests()
    results.append(("仓库层测试", repo_ok))
    
    # 2. 任务管理 API 集成测试（需要服务器）
    if server_running:
        api_ok = run_api_tests()
        results.append(("任务管理 API 集成测试", api_ok))
    else:
        results.append(("任务管理 API 集成测试", None))  # None 表示跳过
    
    # 3. 图片管理 API 集成测试（需要服务器）
    if server_running:
        image_api_ok = run_image_api_tests()
        results.append(("图片管理 API 集成测试", image_api_ok))
    else:
        results.append(("图片管理 API 集成测试", None))  # None 表示跳过
    
    # 4. 自动调度规则 API 集成测试（需要服务器）
    if server_running:
        auto_schedule_api_ok = run_auto_schedule_api_tests()
        results.append(("自动调度规则 API 集成测试", auto_schedule_api_ok))
    else:
        results.append(("自动调度规则 API 集成测试", None))  # None 表示跳过
    
    # 5. 工具类 API 集成测试（需要服务器）
    if server_running:
        utils_api_ok = run_utils_api_tests()
        results.append(("工具类 API 集成测试", utils_api_ok))
    else:
        results.append(("工具类 API 集成测试", None))  # None 表示跳过
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for test_name, result in results:
        if result is None:
            status = "[SKIP] 跳过"
        elif result:
            status = "[PASS] 通过"
        else:
            status = "[FAIL] 失败"
        print(f"{status} {test_name}")
    
    # 判断总体结果
    passed_tests = [r for _, r in results if r is True]
    failed_tests = [r for _, r in results if r is False]
    
    if failed_tests:
        print(f"\n[FAIL] 有 {len(failed_tests)} 个测试失败，请检查错误信息")
        return 1
    elif len(passed_tests) == len([r for _, r in results if r is not None]):
        print(f"\n[PASS] 所有测试通过！({len(passed_tests)}/{len([r for _, r in results if r is not None])})")
        return 0
    else:
        print(f"\n[WARN] 部分测试跳过")
        return 0


if __name__ == "__main__":
    sys.exit(main())

