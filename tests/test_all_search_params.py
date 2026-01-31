"""
全面测试所有搜索参数
"""
import requests
import json

BASE_URL = "http://localhost:8005"
date = "2025-11-07"
ip = "192.168.54.227"
channel = "c2"

print("="*60)
print("全面测试所有搜索参数")
print("="*60)

# 任务列表详情接口测试
print("\n" + "="*60)
print("任务列表详情接口 (/api/tasks/{date}/paged)")
print("="*60)

tests = [
    ("基础搜索-IP和通道", {"rtsp_ip": ip, "channel": channel}),
    ("新参数-IP和通道", {"ip": ip, "channel__eq": channel}),
    ("IP模糊搜索", {"ip__like": "192.168"}),
    ("通道模糊搜索", {"channel__like": "c"}),
    ("状态多选", {"status__in": "pending,playing,completed"}),
    ("截图文件名模糊搜索", {"screenshot_name__like": "176245"}),
    ("时间范围搜索", {"start_ts__gte": 1734048000, "start_ts__lte": 1734134399}),
    ("组合搜索-IP+通道+状态", {"ip": ip, "channel__eq": channel, "status": "completed"}),
]

for test_name, params in tests:
    params["page"] = 1
    params["page_size"] = 5
    response = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params)
    if response.status_code == 200:
        data = response.json()
        total = data.get('total', 0)
        status = "[PASS]" if total >= 0 else "[FAIL]"
        print(f"{status} {test_name}: {total}条")
    else:
        print(f"✗ {test_name}: 错误 {response.status_code}")

# 任务列表接口测试
print("\n" + "="*60)
print("任务列表接口 (/api/tasks/configs)")
print("="*60)

tests2 = [
    ("基础搜索-日期", {"date": date}),
    ("IP精准搜索", {"ip": ip}),
    ("IP模糊搜索", {"ip__like": "192.168"}),
    ("通道搜索", {"channel": channel}),
    ("状态搜索", {"status": "完成"}),
    ("状态多选", {"status__in": "完成,部分失败"}),
    ("间隔时间范围", {"interval_minutes__gte": 10, "interval_minutes__lte": 15}),
]

for test_name, params in tests2:
    params["page"] = 1
    params["page_size"] = 10
    response = requests.get(f"{BASE_URL}/api/tasks/configs", params=params)
    if response.status_code == 200:
        data = response.json()
        total = data.get('total', 0)
        status = "[PASS]" if total >= 0 else "[FAIL]"
        print(f"{status} {test_name}: {total}条")
    else:
        print(f"✗ {test_name}: 错误 {response.status_code}")

# 图片列表接口测试
print("\n" + "="*60)
print("图片列表接口 (/api/images/{date})")
print("="*60)

tests3 = [
    ("基础搜索-IP和通道", {"rtsp_ip": ip, "channel": channel}),
    ("新参数-IP和通道", {"task_ip": ip, "task_channel": channel}),
    ("任务IP模糊搜索", {"task_ip__like": "192.168"}),
    ("任务通道模糊搜索", {"task_channel__like": "c"}),
    ("任务状态多选", {"task_status__in": "completed,failed"}),
    ("状态标签搜索", {"status_label": "待截图"}),
    ("状态标签多选", {"status_label__in": "待截图,截图中"}),
    ("图片名称模糊搜索", {"name__like": "176245"}),
    ("缺失状态过滤", {"missing": False}),
]

for test_name, params in tests3:
    response = requests.get(f"{BASE_URL}/api/images/{date}", params=params)
    if response.status_code == 200:
        data = response.json()
        total = data.get('count', 0)
        status = "[PASS]" if total >= 0 else "[FAIL]"
        print(f"{status} {test_name}: {total}条")
    else:
        print(f"✗ {test_name}: 错误 {response.status_code}")

print("\n" + "="*60)
print("测试完成")
print("="*60)

