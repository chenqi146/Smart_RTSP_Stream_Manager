"""
增强版搜索API测试 - 使用实际数据验证
运行方式：python test_search_api_enhanced.py
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8005"

def get_available_dates():
    """获取可用的日期列表"""
    try:
        response = requests.get(f"{BASE_URL}/api/tasks/configs", params={"page": 1, "page_size": 100}, timeout=5)
        if response.status_code == 200:
            data = response.json()
            dates = set()
            for item in data.get('items', []):
                if item.get('date'):
                    dates.add(item['date'])
            return sorted(list(dates))
    except Exception as e:
        print(f"获取日期列表失败: {e}")
    return []

def get_sample_data():
    """获取样本数据用于测试"""
    try:
        response = requests.get(f"{BASE_URL}/api/tasks/configs", params={"page": 1, "page_size": 10}, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('items'):
                return data['items'][0]  # 返回第一条数据作为样本
    except Exception as e:
        print(f"获取样本数据失败: {e}")
    return None

def test_task_detail_search_enhanced(sample_date, sample_ip, sample_channel):
    """增强版任务列表详情搜索测试"""
    print("\n" + "="*60)
    print("测试任务列表详情搜索 (/api/tasks/{date}/paged)")
    print("="*60)
    
    # 测试1: 基础搜索（向后兼容）
    print("\n[测试1] 基础搜索 - IP和通道（向后兼容）")
    params = {
        "rtsp_ip": sample_ip,
        "channel": sample_channel,
        "page": 1,
        "page_size": 5
    }
    response = requests.get(f"{BASE_URL}/api/tasks/{sample_date}/paged", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total1 = data.get('total', 0)
        print(f"  总数: {total1}")
        print(f"  返回项数: {len(data.get('items', []))}")
        if data.get('items'):
            item = data['items'][0]
            print(f"  第一项: IP={item.get('rtsp_url', 'N/A')[:50]}...")
            # 验证所有返回项的IP和通道
            all_match = all(
                sample_ip in item.get('rtsp_url', '') and sample_channel in item.get('rtsp_url', '')
                for item in data['items']
            )
            print(f"  验证: 所有项都包含IP和通道 - {'[PASS]' if all_match else '[FAIL]'}")
    
    # 测试2: 新参数精准搜索
    print("\n[测试2] 新参数精准搜索 - IP和通道")
    params = {
        "ip": sample_ip,
        "channel__eq": sample_channel,
        "page": 1,
        "page_size": 5
    }
    response = requests.get(f"{BASE_URL}/api/tasks/{sample_date}/paged", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total2 = data.get('total', 0)
        print(f"  总数: {total2}")
        # 验证结果应该与测试1相同
        if total1 > 0:
            match = (total1 == total2)
            print(f"  验证: 与测试1结果一致 - {'[PASS]' if match else '[FAIL]'}")
    
    # 测试3: 模糊搜索
    print("\n[测试3] 模糊搜索 - IP部分匹配")
    ip_prefix = sample_ip.split('.')[0] + '.' + sample_ip.split('.')[1]  # 前两段
    params = {
        "ip__like": ip_prefix,
        "page": 1,
        "page_size": 5
    }
    response = requests.get(f"{BASE_URL}/api/tasks/{sample_date}/paged", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total3 = data.get('total', 0)
        print(f"  总数: {total3}")
        if data.get('items'):
            # 验证所有返回项都包含IP前缀
            all_match = all(ip_prefix in item.get('rtsp_url', '') for item in data['items'])
            print(f"  验证: 所有项都包含IP前缀 - {'[PASS]' if all_match else '[FAIL]'}")
    
    # 测试4: 状态多选
    print("\n[测试4] 状态多选")
    params = {
        "status__in": "pending,playing,completed",
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/{sample_date}/paged", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total4 = data.get('total', 0)
        print(f"  总数: {total4}")
        if data.get('items'):
            statuses = set(item.get('status') for item in data['items'])
            print(f"  返回的状态: {statuses}")
            valid_statuses = {'pending', 'playing', 'completed'}
            all_valid = all(s in valid_statuses for s in statuses)
            print(f"  验证: 所有状态都在允许范围内 - {'[PASS]' if all_valid else '[FAIL]'}")
    
    # 测试5: 截图文件名模糊搜索
    print("\n[测试5] 截图文件名模糊搜索")
    params = {
        "screenshot_name__like": "176245",
        "page": 1,
        "page_size": 5
    }
    response = requests.get(f"{BASE_URL}/api/tasks/{sample_date}/paged", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total5 = data.get('total', 0)
        print(f"  总数: {total5}")
        if data.get('items'):
            # 验证所有返回项的截图文件名都包含搜索关键词
            all_match = all(
                '176245' in (item.get('screenshot_path', '') or '')
                for item in data['items']
            )
            print(f"  验证: 所有项都包含关键词 - {'[PASS]' if all_match else '[FAIL]'}")


def test_task_configs_search_enhanced(sample_date, sample_ip):
    """增强版任务列表搜索测试"""
    print("\n" + "="*60)
    print("测试任务列表搜索 (/api/tasks/configs)")
    print("="*60)
    
    # 测试1: 基础搜索
    print("\n[测试1] 基础搜索 - 日期")
    params = {
        "date": sample_date,
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/configs", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total1 = data.get('total', 0)
        print(f"  总数: {total1}")
        print(f"  返回项数: {len(data.get('items', []))}")
        if data.get('items'):
            item = data['items'][0]
            print(f"  第一项: IP={item.get('ip')}, 通道={item.get('channel')}, 状态={item.get('status')}")
            # 验证所有返回项的日期
            all_match = all(item.get('date') == sample_date for item in data['items'])
            print(f"  验证: 所有项都是指定日期 - {'[PASS]' if all_match else '[FAIL]'}")
    
    # 测试2: IP精准搜索
    print("\n[测试2] IP精准搜索")
    params = {
        "ip": sample_ip,
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/configs", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total2 = data.get('total', 0)
        print(f"  总数: {total2}")
        if data.get('items'):
            # 验证所有返回项的IP
            all_match = all(item.get('ip') == sample_ip for item in data['items'])
            print(f"  验证: 所有项的IP都匹配 - {'[PASS]' if all_match else '[FAIL]'}")
    
    # 测试3: IP模糊搜索
    print("\n[测试3] IP模糊搜索")
    ip_prefix = sample_ip.split('.')[0] + '.' + sample_ip.split('.')[1]
    params = {
        "ip__like": ip_prefix,
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/configs", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total3 = data.get('total', 0)
        print(f"  总数: {total3}")
        if data.get('items'):
            # 验证所有返回项的IP都包含前缀
            all_match = all(ip_prefix in (item.get('ip') or '') for item in data['items'])
            print(f"  验证: 所有项的IP都包含前缀 - {'[PASS]' if all_match else '[FAIL]'}")
            # 模糊搜索应该返回更多结果
            more_results = total3 >= total2
            print(f"  验证: 模糊搜索返回更多或相等结果 - {'[PASS]' if more_results else '[FAIL]'}")
    
    # 测试4: 状态搜索
    print("\n[测试4] 状态搜索 - 完成")
    params = {
        "status": "完成",
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/configs", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total4 = data.get('total', 0)
        print(f"  总数: {total4}")
        if data.get('items'):
            statuses = set(item.get('status') for item in data['items'])
            print(f"  返回的状态: {statuses}")
            all_completed = all(item.get('status') == '完成' for item in data['items'])
            print(f"  验证: 所有项都是'完成'状态 - {'[PASS]' if all_completed else '[FAIL]'}")


def test_images_search_enhanced(sample_date, sample_ip, sample_channel):
    """增强版图片列表搜索测试"""
    print("\n" + "="*60)
    print("测试图片列表搜索 (/api/images/{date})")
    print("="*60)
    
    # 测试1: 基础搜索（向后兼容）
    print("\n[测试1] 基础搜索 - IP和通道（向后兼容）")
    params = {
        "rtsp_ip": sample_ip,
        "channel": sample_channel
    }
    response = requests.get(f"{BASE_URL}/api/images/{sample_date}", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total1 = data.get('count', 0)
        print(f"  总数: {total1}")
        print(f"  返回项数: {len(data.get('items', []))}")
        if data.get('items'):
            item = data['items'][0]
            print(f"  第一项: 名称={item.get('name', 'N/A')[:30]}..., IP={item.get('task_ip')}, 通道={item.get('task_channel')}")
            # 验证所有返回项的IP和通道
            all_match = all(
                item.get('task_ip') == sample_ip and item.get('task_channel') == sample_channel
                for item in data['items']
            )
            print(f"  验证: 所有项都匹配IP和通道 - {'[PASS]' if all_match else '[FAIL]'}")
    
    # 测试2: 新参数精准搜索
    print("\n[测试2] 新参数精准搜索 - IP和通道")
    params = {
        "task_ip": sample_ip,
        "task_channel": sample_channel
    }
    response = requests.get(f"{BASE_URL}/api/images/{sample_date}", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total2 = data.get('count', 0)
        print(f"  总数: {total2}")
        # 验证结果应该与测试1相同
        if total1 > 0:
            match = (total1 == total2)
            print(f"  验证: 与测试1结果一致 - {'[PASS]' if match else '[FAIL]'}")
    
    # 测试3: 任务状态多选
    print("\n[测试3] 任务状态多选")
    params = {
        "task_status__in": "completed,failed"
    }
    response = requests.get(f"{BASE_URL}/api/images/{sample_date}", params=params)
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total3 = data.get('count', 0)
        print(f"  总数: {total3}")
        if data.get('items'):
            statuses = set(item.get('task_status') for item in data['items'])
            print(f"  返回的任务状态: {statuses}")
            valid_statuses = {'completed', 'failed'}
            all_valid = all(s in valid_statuses for s in statuses)
            print(f"  验证: 所有状态都在允许范围内 - {'[PASS]' if all_valid else '[FAIL]'}")


def main():
    """主函数"""
    print("="*60)
    print("增强版搜索API测试")
    print("="*60)
    print(f"API地址: {BASE_URL}")
    
    # 检查服务器
    try:
        response = requests.get(f"{BASE_URL}/api/tasks/configs", params={"page": 1, "page_size": 1}, timeout=5)
        if response.status_code != 200:
            print(f"错误: 服务器返回状态码 {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print("错误: 无法连接到服务器，请确保服务器正在运行")
        print("提示: 运行 python app/main.py 启动服务器")
        return
    except Exception as e:
        print(f"错误: {e}")
        return
    
    # 获取样本数据
    print("\n获取样本数据...")
    sample = get_sample_data()
    if not sample:
        print("错误: 无法获取样本数据，请确保数据库中有数据")
        return
    
    sample_date = sample.get('date')
    sample_ip = sample.get('ip')
    sample_channel = sample.get('channel')
    
    print(f"使用样本数据: 日期={sample_date}, IP={sample_ip}, 通道={sample_channel}")
    
    # 运行测试
    test_task_detail_search_enhanced(sample_date, sample_ip, sample_channel)
    test_task_configs_search_enhanced(sample_date, sample_ip)
    test_images_search_enhanced(sample_date, sample_ip, sample_channel)
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
    print("\n提示: 请检查所有验证结果，确保都是 [PASS]")


if __name__ == "__main__":
    main()

