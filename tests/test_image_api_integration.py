"""图片管理 API 集成测试"""
import sys
import io
from pathlib import Path
import requests

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 设置标准输出编码为 UTF-8（Windows 兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# API 基础 URL
BASE_URL = "http://localhost:8005"


class ImageAPITester:
    """图片 API 测试类"""
    
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
    
    def test_get_available_dates(self) -> bool:
        """测试获取可用日期"""
        try:
            response = self.session.get(f"{self.base_url}/api/images/available_dates")
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
    
    def test_list_images_all(self) -> bool:
        """测试获取所有图片"""
        try:
            response = self.session.get(f"{self.base_url}/api/images")
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                count = data.get("count", 0)
                self.log_result("获取所有图片", True, f"返回 {len(items)} 条，总计 {count} 条")
                return True
            else:
                self.log_result("获取所有图片", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("获取所有图片", False, str(e))
            return False
    
    def test_list_images_by_date(self) -> bool:
        """测试按日期获取图片"""
        try:
            # 先获取可用日期
            dates_response = self.session.get(f"{self.base_url}/api/images/available_dates")
            if dates_response.status_code == 200:
                dates_data = dates_response.json()
                dates = dates_data.get("dates", [])
                if dates:
                    test_date = dates[0]["date"]
                    response = self.session.get(f"{self.base_url}/api/images/{test_date}")
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("items", [])
                        self.log_result("按日期获取图片", True, f"日期 {test_date} 返回 {len(items)} 条")
                        return True
                    else:
                        self.log_result("按日期获取图片", False, f"状态码: {response.status_code}")
                        return False
                else:
                    self.log_result("按日期获取图片", True, "没有可用日期，跳过测试")
                    return True
            else:
                self.log_result("按日期获取图片", False, "无法获取可用日期")
                return False
        except Exception as e:
            self.log_result("按日期获取图片", False, str(e))
            return False
    
    def test_search_images(self) -> bool:
        """测试图片搜索功能"""
        try:
            # 测试各种搜索条件
            search_tests = [
                {"task_ip": "192.168.54.227"},
                {"task_channel": "c1"},
                {"task_status": "completed"},
                {"name__like": "jpg"},
            ]
            
            success_count = 0
            for search_params in search_tests:
                response = self.session.get(
                    f"{self.base_url}/api/images",
                    params=search_params,
                    timeout=10
                )
                if response.status_code == 200:
                    success_count += 1
            
            if success_count == len(search_tests):
                self.log_result("图片搜索功能", True, f"所有搜索条件测试通过 ({success_count}/{len(search_tests)})")
                return True
            else:
                self.log_result("图片搜索功能", False, f"部分搜索失败 ({success_count}/{len(search_tests)})")
                return False
        except Exception as e:
            self.log_result("图片搜索功能", False, str(e))
            return False
    
    def test_image_proxy(self) -> bool:
        """测试图片代理功能"""
        try:
            # 先获取一张图片的路径
            response = self.session.get(f"{self.base_url}/api/images", params={"limit": 1})
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                if items and items[0].get("path"):
                    path = items[0]["path"]
                    proxy_response = self.session.get(
                        f"{self.base_url}/api/image_proxy",
                        params={"path": path},
                        timeout=5
                    )
                    if proxy_response.status_code in [200, 404]:  # 404 也是正常的（文件可能不存在）
                        self.log_result("图片代理功能", True, f"代理响应状态码: {proxy_response.status_code}")
                        return True
                    else:
                        self.log_result("图片代理功能", False, f"状态码: {proxy_response.status_code}")
                        return False
                else:
                    self.log_result("图片代理功能", True, "没有图片数据，跳过测试")
                    return True
            else:
                self.log_result("图片代理功能", False, "无法获取图片列表")
                return False
        except Exception as e:
            self.log_result("图片代理功能", False, str(e))
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("图片管理 API 集成测试")
        print("=" * 60)
        
        # 功能完整性测试
        print("\n=== 功能完整性测试 ===")
        self.test_get_available_dates()
        self.test_list_images_all()
        self.test_list_images_by_date()
        self.test_search_images()
        self.test_image_proxy()
        
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
        if total_tests > 0:
            print(f"成功率: {passed_tests/total_tests*100:.1f}%")
        
        if failed_tests > 0:
            print("\n失败的测试:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['message']}")
        
        return failed_tests == 0


if __name__ == "__main__":
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
    tester = ImageAPITester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

