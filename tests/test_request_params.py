"""
测试请求参数 - 直接检查FastAPI如何解析参数
"""
import requests
import json

BASE_URL = "http://localhost:8005"
date = "2025-11-07"

print("="*60)
print("测试请求参数解析")
print("="*60)

# 测试：检查服务器日志输出
print("\n请查看服务器控制台输出，应该会显示:")
print("  [DEBUG get_tasks_paged] channel_eq=..., channel=..., channel_like=...")

# 测试1: 使用channel__eq (双下划线)
print("\n[测试1] 使用 channel__eq (双下划线)")
params1 = {"channel__eq": "c2", "page": 1, "page_size": 3}
response1 = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params1)
print(f"URL: {response1.url}")
data1 = response1.json()
print(f"总数: {data1.get('total', 0)}")
print("请检查服务器日志中的DEBUG输出")

# 测试2: 使用channel_eq (单下划线)
print("\n[测试2] 使用 channel_eq (单下划线)")
params2 = {"channel_eq": "c2", "page": 1, "page_size": 3}
response2 = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params2)
print(f"URL: {response2.url}")
data2 = response2.json()
print(f"总数: {data2.get('total', 0)}")
print("请检查服务器日志中的DEBUG输出")

# 测试3: 使用channel (旧参数)
print("\n[测试3] 使用 channel (旧参数)")
params3 = {"channel": "c2", "page": 1, "page_size": 3}
response3 = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params3)
print(f"URL: {response3.url}")
data3 = response3.json()
print(f"总数: {data3.get('total', 0)}")
print("请检查服务器日志中的DEBUG输出")

