"""
简单搜索测试 - 验证参数传递
"""
import requests

BASE_URL = "http://localhost:8005"
date = "2025-11-07"

print("="*60)
print("简单搜索测试")
print("="*60)

# 测试：使用channel_eq（单下划线，FastAPI解析后的参数名）
print("\n[测试] 使用 channel_eq (单下划线)")
params = {"channel_eq": "c2", "page": 1, "page_size": 3}
response = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params)
print(f"URL: {response.url}")
print(f"状态码: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"总数: {data.get('total', 0)}")
    if data.get('items'):
        print("前3项的通道:")
        for item in data['items']:
            rtsp = item.get('rtsp_url', '')
            ch = 'c2' if '/c2/' in rtsp else ('c4' if '/c4/' in rtsp else 'unknown')
            print(f"  {ch}")

