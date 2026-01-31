"""自动调度规则 API 集成测试"""
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


class AutoScheduleAPITester:
    """自动调度规则 API 测试类"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
        self.created_rule_ids = []  # 记录创建的规则ID，用于清理
    
    def log_result(self, test_name: str, success: bool, message: str = ""):
        """记录测试结果"""
        status = "[OK]" if success else "[FAIL]"
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message
        })
        print(f"{status} {test_name}: {message}")
    
    def cleanup(self):
        """清理测试数据"""
        for rule_id in self.created_rule_ids:
            try:
                self.session.delete(f"{self.base_url}/api/auto-schedule/rules/{rule_id}")
            except:
                pass
    
    def test_list_rules(self) -> bool:
        """测试获取所有规则"""
        try:
            response = self.session.get(f"{self.base_url}/api/auto-schedule/rules")
            if response.status_code == 200:
                rules = response.json()
                self.log_result("获取所有规则", True, f"返回 {len(rules)} 条规则")
                return True
            else:
                self.log_result("获取所有规则", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("获取所有规则", False, str(e))
            return False
    
    def test_create_rule(self) -> bool:
        """测试创建规则"""
        try:
            rule_data = {
                "use_today": True,
                "base_rtsp": "rtsp://test@192.168.1.100:554/c1",
                "channel": "c1",
                "interval_minutes": 10,
                "trigger_time": "18:00",
            }
            response = self.session.post(
                f"{self.base_url}/api/auto-schedule/rules",
                json=rule_data
            )
            if response.status_code == 200:
                data = response.json()
                rule_id = data.get("id")
                if rule_id:
                    self.created_rule_ids.append(rule_id)
                    self.log_result("创建规则", True, f"规则ID: {rule_id}")
                    return True
                else:
                    self.log_result("创建规则", False, "未返回规则ID")
                    return False
            else:
                self.log_result("创建规则", False, f"状态码: {response.status_code}, 响应: {response.text}")
                return False
        except Exception as e:
            self.log_result("创建规则", False, str(e))
            return False
    
    def test_create_rule_validation(self) -> bool:
        """测试创建规则的验证"""
        test_cases = [
            {
                "name": "缺少日期",
                "data": {
                    "use_today": False,
                    "base_rtsp": "rtsp://test@192.168.1.100:554/c1",
                    "channel": "c1",
                    "interval_minutes": 10,
                    "trigger_time": "18:00",
                },
                "expected_status": 400,
            },
            {
                "name": "无效的RTSP地址",
                "data": {
                    "use_today": True,
                    "base_rtsp": "http://test@192.168.1.100:554/c1",
                    "channel": "c1",
                    "interval_minutes": 10,
                    "trigger_time": "18:00",
                },
                "expected_status": 400,
            },
            {
                "name": "无效的通道格式",
                "data": {
                    "use_today": True,
                    "base_rtsp": "rtsp://test@192.168.1.100:554/c1",
                    "channel": "channel1",
                    "interval_minutes": 10,
                    "trigger_time": "18:00",
                },
                "expected_status": 400,
            },
            {
                "name": "无效的触发时间",
                "data": {
                    "use_today": True,
                    "base_rtsp": "rtsp://test@192.168.1.100:554/c1",
                    "channel": "c1",
                    "interval_minutes": 10,
                    "trigger_time": "25:00",
                },
                "expected_status": 400,
            },
        ]
        
        success_count = 0
        for test_case in test_cases:
            try:
                response = self.session.post(
                    f"{self.base_url}/api/auto-schedule/rules",
                    json=test_case["data"]
                )
                if response.status_code == test_case["expected_status"]:
                    success_count += 1
                else:
                    print(f"  警告: {test_case['name']} 期望状态码 {test_case['expected_status']}, 实际 {response.status_code}")
            except Exception as e:
                print(f"  错误: {test_case['name']} - {str(e)}")
        
        if success_count == len(test_cases):
            self.log_result("创建规则验证", True, f"所有验证测试通过 ({success_count}/{len(test_cases)})")
            return True
        else:
            self.log_result("创建规则验证", False, f"部分验证失败 ({success_count}/{len(test_cases)})")
            return False
    
    def test_update_rule(self) -> bool:
        """测试更新规则"""
        try:
            # 先创建一个规则
            rule_data = {
                "use_today": True,
                "base_rtsp": "rtsp://test@192.168.1.101:554/c2",
                "channel": "c2",
                "interval_minutes": 20,
                "trigger_time": "19:00",
            }
            create_response = self.session.post(
                f"{self.base_url}/api/auto-schedule/rules",
                json=rule_data
            )
            if create_response.status_code != 200:
                self.log_result("更新规则", False, "无法创建测试规则")
                return False
            
            rule_id = create_response.json().get("id")
            if not rule_id:
                self.log_result("更新规则", False, "未获取到规则ID")
                return False
            
            self.created_rule_ids.append(rule_id)
            
            # 更新规则
            update_data = {"is_enabled": False}
            update_response = self.session.patch(
                f"{self.base_url}/api/auto-schedule/rules/{rule_id}",
                json=update_data
            )
            if update_response.status_code == 200:
                self.log_result("更新规则", True, f"规则ID: {rule_id}")
                return True
            else:
                self.log_result("更新规则", False, f"状态码: {update_response.status_code}")
                return False
        except Exception as e:
            self.log_result("更新规则", False, str(e))
            return False
    
    def test_delete_rule(self) -> bool:
        """测试删除规则"""
        try:
            # 先创建一个规则
            rule_data = {
                "use_today": True,
                "base_rtsp": "rtsp://test@192.168.1.102:554/c3",
                "channel": "c3",
                "interval_minutes": 30,
                "trigger_time": "20:00",
            }
            create_response = self.session.post(
                f"{self.base_url}/api/auto-schedule/rules",
                json=rule_data
            )
            if create_response.status_code != 200:
                self.log_result("删除规则", False, "无法创建测试规则")
                return False
            
            rule_id = create_response.json().get("id")
            if not rule_id:
                self.log_result("删除规则", False, "未获取到规则ID")
                return False
            
            # 删除规则
            delete_response = self.session.delete(
                f"{self.base_url}/api/auto-schedule/rules/{rule_id}"
            )
            if delete_response.status_code == 200:
                self.log_result("删除规则", True, f"规则ID: {rule_id}")
                return True
            else:
                self.log_result("删除规则", False, f"状态码: {delete_response.status_code}")
                return False
        except Exception as e:
            self.log_result("删除规则", False, str(e))
            return False
    
    def test_delete_nonexistent_rule(self) -> bool:
        """测试删除不存在的规则"""
        try:
            response = self.session.delete(
                f"{self.base_url}/api/auto-schedule/rules/99999"
            )
            if response.status_code == 404:
                self.log_result("删除不存在规则", True, "正确返回404")
                return True
            else:
                self.log_result("删除不存在规则", False, f"状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("删除不存在规则", False, str(e))
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("自动调度规则 API 集成测试")
        print("=" * 60)
        
        try:
            # 功能完整性测试
            print("\n=== 功能完整性测试 ===")
            self.test_list_rules()
            self.test_create_rule()
            self.test_update_rule()
            self.test_delete_rule()
            
            # 验证测试
            print("\n=== 验证测试 ===")
            self.test_create_rule_validation()
            self.test_delete_nonexistent_rule()
            
        finally:
            # 清理测试数据
            self.cleanup()
        
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
    tester = AutoScheduleAPITester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

