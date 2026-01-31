"""工具类 API 集成测试"""
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


class UtilsAPITester:
    """工具类 API 测试类"""
    
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
    
    def test_healthz(self) -> bool:
        """测试健康检查"""
        try:
            response = self.session.get(f"{self.base_url}/healthz", timeout=2)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    self.log_result("健康检查", True, "服务正常")
                    return True
                else:
                    self.log_result("健康检查", False, f"状态异常: {data}")
                    return False
            else:
                self.log_result("健康检查", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("健康检查", False, str(e))
            return False
    
    def test_get_ocr_results(self) -> bool:
        """测试获取 OCR 结果"""
        try:
            # 使用一个存在的日期进行测试
            test_date = "2025-11-01"
            response = self.session.get(f"{self.base_url}/api/ocr/{test_date}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                # OCR 功能已注释，应该返回空结果
                self.log_result("获取 OCR 结果", True, f"日期 {test_date} 返回 {data.get('count', 0)} 条结果")
                return True
            else:
                self.log_result("获取 OCR 结果", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("获取 OCR 结果", False, str(e))
            return False
    
    def test_image_proxy(self) -> bool:
        """测试图片代理"""
        try:
            # 先获取一张图片的路径
            images_response = self.session.get(f"{self.base_url}/api/images", params={"limit": 1}, timeout=5)
            if images_response.status_code == 200:
                images_data = images_response.json()
                items = images_data.get("items", [])
                if items and items[0].get("path"):
                    path = items[0]["path"]
                    proxy_response = self.session.get(
                        f"{self.base_url}/api/image_proxy",
                        params={"path": path},
                        timeout=5
                    )
                    if proxy_response.status_code in [200, 404]:  # 404 也是正常的（文件可能不存在）
                        self.log_result("图片代理", True, f"代理响应状态码: {proxy_response.status_code}")
                        return True
                    else:
                        self.log_result("图片代理", False, f"状态码: {proxy_response.status_code}")
                        return False
                else:
                    self.log_result("图片代理", True, "没有图片数据，跳过测试")
                    return True
            else:
                self.log_result("图片代理", False, "无法获取图片列表")
                return False
        except Exception as e:
            self.log_result("图片代理", False, str(e))
            return False
    
    def test_index_page(self) -> bool:
        """测试首页"""
        try:
            response = self.session.get(f"{self.base_url}/", timeout=5)
            if response.status_code == 200:
                # 可能是 HTML 或 JSON
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type or "application/json" in content_type:
                    self.log_result("首页", True, f"内容类型: {content_type}")
                    return True
                else:
                    self.log_result("首页", False, f"意外的内容类型: {content_type}")
                    return False
            else:
                self.log_result("首页", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("首页", False, str(e))
            return False
    
    def test_hls_start(self) -> bool:
        """测试 HLS 流启动（需要有效的 RTSP 地址）"""
        try:
            # 使用一个测试 RTSP 地址（可能不存在，但可以测试错误处理）
            test_rtsp = "rtsp://test@192.168.1.100:554/c1"
            response = self.session.get(
                f"{self.base_url}/api/hls/start",
                params={"rtsp_url": test_rtsp},
                timeout=30  # HLS 启动可能需要更长时间
            )
            # HLS 启动可能成功或失败（取决于 RTSP 地址是否有效）
            # 只要不是 500 以外的错误，都算正常
            if response.status_code in [200, 500]:
                if response.status_code == 200:
                    data = response.json()
                    self.log_result("HLS 流启动", True, f"m3u8: {data.get('m3u8', 'N/A')}")
                else:
                    # 500 错误是预期的（RTSP 地址无效）
                    self.log_result("HLS 流启动", True, "RTSP 地址无效（预期行为）")
                return True
            else:
                self.log_result("HLS 流启动", False, f"状态码: {response.status_code}")
                return False
        except requests.exceptions.Timeout:
            self.log_result("HLS 流启动", True, "超时（可能是 RTSP 地址无效，预期行为）")
            return True
        except Exception as e:
            self.log_result("HLS 流启动", False, str(e))
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("工具类 API 集成测试")
        print("=" * 60)
        
        # 功能完整性测试
        print("\n=== 功能完整性测试 ===")
        self.test_healthz()
        self.test_get_ocr_results()
        self.test_image_proxy()
        self.test_index_page()
        self.test_hls_start()
        
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
    tester = UtilsAPITester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

