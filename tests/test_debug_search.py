"""
调试搜索API - 检查实际返回的数据
"""
import requests
import json

BASE_URL = "http://localhost:8005"
date = "2025-11-07"
ip = "192.168.54.227"
channel = "c2"

print("="*60)
print("调试搜索API")
print("="*60)

# 测试1: 旧参数
print("\n[测试1] 旧参数 - rtsp_ip + channel")
params1 = {
    "rtsp_ip": ip,
    "channel": channel,
    "page": 1,
    "page_size": 5
}
response1 = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params1)
data1 = response1.json()
print(f"总数: {data1.get('total', 0)}")
if data1.get('items'):
    print("前3项的通道:")
    for item in data1['items'][:3]:
        rtsp = item.get('rtsp_url', '')
        ch_match = None
        if '/c1/' in rtsp:
            ch_match = 'c1'
        elif '/c2/' in rtsp:
            ch_match = 'c2'
        elif '/c3/' in rtsp:
            ch_match = 'c3'
        elif '/c4/' in rtsp:
            ch_match = 'c4'
        print(f"  {rtsp[:60]}... -> {ch_match}")

# 测试2: 新参数
print("\n[测试2] 新参数 - ip + channel__eq")
params2 = {
    "ip": ip,
    "channel__eq": channel,
    "page": 1,
    "page_size": 5
}
response2 = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params2)
data2 = response2.json()
print(f"总数: {data2.get('total', 0)}")
if data2.get('items'):
    print("前3项的通道:")
    for item in data2['items'][:3]:
        rtsp = item.get('rtsp_url', '')
        ch_match = None
        if '/c1/' in rtsp:
            ch_match = 'c1'
        elif '/c2/' in rtsp:
            ch_match = 'c2'
        elif '/c3/' in rtsp:
            ch_match = 'c3'
        elif '/c4/' in rtsp:
            ch_match = 'c4'
        print(f"  {rtsp[:60]}... -> {ch_match}")

# 测试3: 只传IP
print("\n[测试3] 只传IP - ip")
params3 = {
    "ip": ip,
    "page": 1,
    "page_size": 5
}
response3 = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params3)
data3 = response3.json()
print(f"总数: {data3.get('total', 0)}")

# 测试4: 只传通道
print("\n[测试4] 只传通道 - channel__eq")
params4 = {
    "channel__eq": channel,
    "page": 1,
    "page_size": 5
}
response4 = requests.get(f"{BASE_URL}/api/tasks/{date}/paged", params=params4)
data4 = response4.json()
print(f"总数: {data4.get('total', 0)}")

