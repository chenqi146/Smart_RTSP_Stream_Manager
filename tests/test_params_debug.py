"""
调试参数传递 - 检查FastAPI如何解析参数
"""
import requests
import json

BASE_URL = "http://localhost:8005"
date = "2025-11-07"

print("="*60)
print("调试参数传递")
print("="*60)

# 测试：直接访问API文档查看参数
print("\n访问API文档查看参数定义...")
print(f"Swagger UI: {BASE_URL}/docs")
print(f"ReDoc: {BASE_URL}/redoc")

# 测试：使用不同的参数名格式
print("\n[测试1] 使用 channel__eq (双下划线)")
params1 = {"channel__eq": "c2", "page": 1, "page_size": 3}
response1 = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params1)
print(f"URL: {response1.url}")
print(f"状态码: {response1.status_code}")
data1 = response1.json()
print(f"总数: {data1.get('total', 0)}")

print("\n[测试2] 使用 channel_eq (单下划线)")
params2 = {"channel_eq": "c2", "page": 1, "page_size": 3}
response2 = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params2)
print(f"URL: {response2.url}")
print(f"状态码: {response2.status_code}")
data2 = response2.json()
print(f"总数: {data2.get('total', 0)}")

print("\n[测试3] 使用旧参数 channel")
params3 = {"channel": "c2", "page": 1, "page_size": 3}
response3 = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params3)
print(f"URL: {response3.url}")
print(f"状态码: {response3.status_code}")
data3 = response3.json()
print(f"总数: {data3.get('total', 0)}")

