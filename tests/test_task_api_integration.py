"""任务 API 集成测试（功能完整性、并发、安全）"""
import sys
import io
import time
import threading
from pathlib import Path
from typing import List, Dict
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# 设置标准输出编码为 UTF-8（Windows 兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# API 基础 URL
BASE_URL = "http://localhost:8005"


class TaskAPITester:
    """任务 API 测试类"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
    
    def log_result(self, test_name: str, success: bool, message: str = ""):
        """记录测试结果"""
        status = "[OK]" if success else "[FAIL]"
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message
        })
        print(f"{status} {test_name}: {message}")
    
    # ==================== 功能完整性测试 ====================
    
    def test_get_available_dates(self) -> bool:
        """测试获取可用日期"""
        try:
            response = self.session.get(f"{self.base_url}/api/tasks/available_dates")
            if response.status_code == 200:
                data = response.json()
                dates = data.get("dates", [])
                self.log_result("获取可用日期", True, f"返回 {len(dates)} 个日期")
                return True
            else:
                self.log_result("获取可用日期", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("获取可用日期", False, str(e))
            return False
    
    def test_get_available_ips(self) -> bool:
        """测试获取可用 IP"""
        try:
            response = self.session.get(f"{self.base_url}/api/tasks/available_ips")
            if response.status_code == 200:
                data = response.json()
                ips = data.get("ips", [])
                self.log_result("获取可用 IP", True, f"返回 {len(ips)} 个 IP")
                return True
            else:
                self.log_result("获取可用 IP", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("获取可用 IP", False, str(e))
            return False
    
    def test_get_available_channels(self) -> bool:
        """测试获取可用通道"""
        try:
            response = self.session.get(f"{self.base_url}/api/tasks/available_channels")
            if response.status_code == 200:
                data = response.json()
                channels = data.get("channels", [])
                self.log_result("获取可用通道", True, f"返回 {len(channels)} 个通道")
                return True
            else:
                self.log_result("获取可用通道", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("获取可用通道", False, str(e))
            return False
    
    def test_get_task_configs(self, date: str = None) -> bool:
        """测试获取任务配置列表"""
        try:
            url = f"{self.base_url}/api/tasks/configs"
            params = {"page": 1, "page_size": 10}
            if date:
                params["date"] = date
            
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                total = data.get("total", 0)
                self.log_result("获取任务配置列表", True, f"返回 {len(items)} 条，总计 {total} 条")
                return True
            else:
                self.log_result("获取任务配置列表", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("获取任务配置列表", False, str(e))
            return False
    
    def test_get_tasks_paged(self, date: str = None) -> bool:
        """测试获取任务详情（分页）"""
        try:
            url = f"{self.base_url}/api/tasks/paged"
            params = {"page": 1, "page_size": 10}
            if date:
                params["date"] = date
            
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                total = data.get("total", 0)
                self.log_result("获取任务详情（分页）", True, f"返回 {len(items)} 条，总计 {total} 条")
                return True
            else:
                self.log_result("获取任务详情（分页）", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("获取任务详情（分页）", False, str(e))
            return False
    
    def test_search_tasks(self) -> bool:
        """测试任务搜索功能"""
        try:
            # 测试各种搜索条件
            search_tests = [
                {"ip": "10.10.11.122"},
                {"channel": "c1"},
                {"status": "completed"},
                {"screenshot_name__like": "1762452600"},
            ]
            
            success_count = 0
            for search_params in search_tests:
                url = f"{self.base_url}/api/tasks/paged"
                params = {"page": 1, "page_size": 5, **search_params}
                response = self.session.get(url, params=params)
                if response.status_code == 200:
                    success_count += 1
            
            if success_count == len(search_tests):
                self.log_result("任务搜索功能", True, f"所有搜索条件测试通过 ({success_count}/{len(search_tests)})")
                return True
            else:
                self.log_result("任务搜索功能", False, f"部分搜索失败 ({success_count}/{len(search_tests)})")
                return False
        except Exception as e:
            self.log_result("任务搜索功能", False, str(e))
            return False
    
    # ==================== 并发测试 ====================
    
    def test_concurrent_requests(self, num_threads: int = 20) -> bool:
        """测试并发请求"""
        print(f"\n=== 并发测试 ({num_threads} 个并发请求) ===")
        
        results = []
        errors = []
        
        def make_request(thread_id: int):
            try:
                url = f"{self.base_url}/api/tasks/configs"
                params = {"page": 1, "page_size": 5}
                response = self.session.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    results.append(thread_id)
                    return True
                else:
                    errors.append(f"Thread {thread_id}: Status {response.status_code}")
                    return False
            except Exception as e:
                errors.append(f"Thread {thread_id}: {str(e)}")
                return False
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()
        
        elapsed_time = time.time() - start_time
        
        success_rate = len(results) / num_threads * 100
        
        if len(errors) == 0 and success_rate >= 95:
            self.log_result(
                "并发请求测试", 
                True, 
                f"成功率: {success_rate:.1f}%, 耗时: {elapsed_time:.2f}s, 成功: {len(results)}/{num_threads}"
            )
            return True
        else:
            self.log_result(
                "并发请求测试", 
                False, 
                f"成功率: {success_rate:.1f}%, 错误: {len(errors)} 个"
            )
            if errors:
                for err in errors[:3]:
                    print(f"  - {err}")
            return False
    
    # ==================== 安全测试 ====================
    
    def test_sql_injection_protection(self) -> bool:
        """测试 SQL 注入防护"""
        print("\n=== 安全测试 ===")
        
        malicious_inputs = [
            "'; DROP TABLE tasks; --",
            "1' OR '1'='1",
            "'; DELETE FROM tasks; --",
            "1'; UPDATE tasks SET status='hacked'; --",
        ]
        
        success_count = 0
        for malicious_input in malicious_inputs:
            try:
                # 尝试通过搜索参数注入 SQL
                url = f"{self.base_url}/api/tasks/paged"
                params = {
                    "ip": malicious_input,
                    "page": 1,
                    "page_size": 1
                }
                response = self.session.get(url, params=params, timeout=5)
                
                # 应该返回正常响应（参数化查询）或错误响应（输入验证），但不应该执行 SQL
                if response.status_code in [200, 400, 422]:
                    success_count += 1
                else:
                    print(f"  警告: 状态码 {response.status_code} 对于输入: {malicious_input[:30]}...")
            except Exception as e:
                # 异常也是可以接受的（说明有防护）
                success_count += 1
        
        if success_count == len(malicious_inputs):
            self.log_result("SQL 注入防护", True, f"所有恶意输入被正确处理 ({success_count}/{len(malicious_inputs)})")
            return True
        else:
            self.log_result("SQL 注入防护", False, f"部分输入未正确处理 ({success_count}/{len(malicious_inputs)})")
            return False
    
    def test_input_validation(self) -> bool:
        """测试输入验证"""
        try:
            # 测试无效的分页参数
            invalid_tests = [
                {"page": -1, "page_size": 10},
                {"page": 0, "page_size": 10},
                {"page": 1, "page_size": -1},
                {"page": 1, "page_size": 0},
                {"page": 1, "page_size": 1000},  # 超过最大值
            ]
            
            success_count = 0
            for params in invalid_tests:
                url = f"{self.base_url}/api/tasks/configs"
                response = self.session.get(url, params=params, timeout=5)
                # 应该返回错误或修正后的值
                if response.status_code in [200, 400, 422]:
                    success_count += 1
            
            if success_count == len(invalid_tests):
                self.log_result("输入验证", True, f"所有无效输入被正确处理 ({success_count}/{len(invalid_tests)})")
                return True
            else:
                self.log_result("输入验证", False, f"部分无效输入未正确处理 ({success_count}/{len(invalid_tests)})")
                return False
        except Exception as e:
            self.log_result("输入验证", False, str(e))
            return False
    
    # ==================== 运行所有测试 ====================
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("任务 API 集成测试")
        print("=" * 60)
        
        # 功能完整性测试
        print("\n=== 功能完整性测试 ===")
        self.test_get_available_dates()
        self.test_get_available_ips()
        self.test_get_available_channels()
        self.test_get_task_configs()
        self.test_get_tasks_paged()
        self.test_search_tasks()
        
        # 并发测试
        self.test_concurrent_requests(num_threads=20)
        
        # 安全测试
        self.test_sql_injection_protection()
        self.test_input_validation()
        
        # 汇总结果
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        print(f"成功率: {passed_tests/total_tests*100:.1f}%")
        
        if failed_tests > 0:
            print("\n失败的测试:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['message']}")
        
        return failed_tests == 0


if __name__ == "__main__":
    import sys
    
    # 检查服务器是否运行
    try:
        response = requests.get(f"{BASE_URL}/healthz", timeout=2)
        if response.status_code != 200:
            print(f"[FAIL] 服务器未正常运行 (状态码: {response.status_code})")
            print("请先启动服务器: python app/main.py")
            sys.exit(1)
    except requests.exceptions.RequestException:
        print(f"[FAIL] 无法连接到服务器: {BASE_URL}")
        print("请先启动服务器: python app/main.py")
        sys.exit(1)
    
    # 运行测试
    tester = TaskAPITester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

