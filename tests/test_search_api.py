"""
测试搜索API功能
运行方式：python test_search_api.py
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8005"

def test_task_detail_search():
    """测试任务列表详情搜索"""
    print("\n" + "="*60)
    print("测试任务列表详情搜索 (/api/tasks/{date}/paged)")
    print("="*60)
    
    # 获取一个有效的日期
    date = "2025-12-13"  # 根据实际数据修改
    
    # 测试1: 基础搜索（向后兼容）
    print("\n测试1: 基础搜索 - IP和通道")
    params = {
        "date": date,
        "rtsp_ip": "192.168.54.227",
        "channel": "c2",
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('total', 0)}")
        print(f"返回项数: {len(data.get('items', []))}")
        if data.get('items'):
            print(f"第一项: {data['items'][0].get('rtsp_url', 'N/A')}")
    
    # 测试2: 精准搜索
    print("\n测试2: 精准搜索 - IP精准匹配")
    params = {
        "ip": "192.168.54.227",
        "channel__eq": "c2",
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('total', 0)}")
    
    # 测试3: 模糊搜索
    print("\n测试3: 模糊搜索 - IP模糊匹配")
    params = {
        "ip__like": "192.168",
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('total', 0)}")
    
    # 测试4: 状态多选
    print("\n测试4: 状态多选")
    params = {
        "status__in": "pending,playing",
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('total', 0)}")
        if data.get('items'):
            statuses = set(item.get('status') for item in data['items'])
            print(f"返回的状态: {statuses}")
    
    # 测试5: 时间范围搜索
    print("\n测试5: 时间范围搜索")
    params = {
        "start_ts__gte": 1734048000,  # 2025-12-13 00:00:00
        "start_ts__lte": 1734134399,  # 2025-12-13 23:59:59
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('total', 0)}")


def test_task_configs_search():
    """测试任务列表搜索"""
    print("\n" + "="*60)
    print("测试任务列表搜索 (/api/tasks/configs)")
    print("="*60)
    
    # 测试1: 基础搜索
    print("\n测试1: 基础搜索 - 日期")
    params = {
        "date": "2025-12-13",
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/configs", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('total', 0)}")
        print(f"返回项数: {len(data.get('items', []))}")
        if data.get('items'):
            print(f"第一项: IP={data['items'][0].get('ip')}, 通道={data['items'][0].get('channel')}")
    
    # 测试2: IP模糊搜索
    print("\n测试2: IP模糊搜索")
    params = {
        "ip__like": "192.168",
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/configs", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('total', 0)}")
    
    # 测试3: 状态搜索
    print("\n测试3: 状态搜索")
    params = {
        "status": "完成",
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/configs", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('total', 0)}")
        if data.get('items'):
            statuses = set(item.get('status') for item in data['items'])
            print(f"返回的状态: {statuses}")
    
    # 测试4: 间隔时间范围搜索
    print("\n测试4: 间隔时间范围搜索")
    params = {
        "interval_minutes__gte": 10,
        "interval_minutes__lte": 15,
        "page": 1,
        "page_size": 10
    }
    response = requests.get(f"{BASE_URL}/api/tasks/configs", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('total', 0)}")


def test_images_search():
    """测试图片列表搜索"""
    print("\n" + "="*60)
    print("测试图片列表搜索 (/api/images/{date})")
    print("="*60)
    
    date = "2025-12-13"  # 根据实际数据修改
    
    # 测试1: 基础搜索
    print("\n测试1: 基础搜索 - IP和通道")
    params = {
        "rtsp_ip": "192.168.54.227",
        "channel": "c2"
    }
    response = requests.get(f"{BASE_URL}/api/images/{date}", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('count', 0)}")
        print(f"返回项数: {len(data.get('items', []))}")
        if data.get('items'):
            print(f"第一项: 名称={data['items'][0].get('name', 'N/A')}")
    
    # 测试2: 图片名称模糊搜索
    print("\n测试2: 图片名称模糊搜索")
    params = {
        "name__like": "176245"
    }
    response = requests.get(f"{BASE_URL}/api/images/{date}", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('count', 0)}")
    
    # 测试3: 任务状态多选
    print("\n测试3: 任务状态多选")
    params = {
        "task_status__in": "completed,failed"
    }
    response = requests.get(f"{BASE_URL}/api/images/{date}", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('count', 0)}")
        if data.get('items'):
            statuses = set(item.get('task_status') for item in data['items'])
            print(f"返回的任务状态: {statuses}")
    
    # 测试4: 状态标签搜索
    print("\n测试4: 状态标签搜索")
    params = {
        "status_label": "待截图"
    }
    response = requests.get(f"{BASE_URL}/api/images/{date}", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('count', 0)}")
        if data.get('items'):
            labels = set(item.get('status_label') for item in data['items'])
            print(f"返回的状态标签: {labels}")
    
    # 测试5: 缺失状态过滤
    print("\n测试5: 缺失状态过滤")
    params = {
        "missing": False  # 只显示存在的图片
    }
    response = requests.get(f"{BASE_URL}/api/images/{date}", params=params)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"总数: {data.get('count', 0)}")


def main():
    """主函数"""
    print("开始测试搜索API功能")
    print(f"API地址: {BASE_URL}")
    
    try:
        # 测试服务器是否运行
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
    
    # 运行测试
    test_task_detail_search()
    test_task_configs_search()
    test_images_search()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    main()

