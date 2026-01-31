#!/bin/bash

# Edge 启动脚本
# 日志文件
LOG_FILE="edge.log"

# 启动 edge（后台运行）
nohup edge \
  -a 10.1.0.13 \
  -c qjvpn \
  -k qjvpn@123 \
  -l 113.141.72.43:5000 \
  -v \
  -f \
  > "${LOG_FILE}" 2>&1 &

# 输出进程信息
echo "Edge started successfully."
echo "PID: $!"
echo "Log file: ${LOG_FILE}"

