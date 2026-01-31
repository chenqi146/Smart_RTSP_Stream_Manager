#!/bin/bash
set -e

# 等待 MySQL 就绪（仅当使用 MySQL 且 MYSQL_HOST 非空时）
wait_for_mysql() {
    if [ -z "${MYSQL_HOST}" ] || [ "${MYSQL_HOST}" = "localhost" ] || [ "${MYSQL_HOST}" = "127.0.0.1" ]; then
        return 0
    fi
    echo "[entrypoint] 等待 MySQL 就绪: ${MYSQL_HOST}:${MYSQL_PORT:-3306}"
    max_attempts=60
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if python -c "
import socket
import os
host = os.environ.get('MYSQL_HOST', 'mysql')
port = int(os.environ.get('MYSQL_PORT', 3306))
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect((host, port))
    s.close()
    exit(0)
except Exception:
    exit(1)
" 2>/dev/null; then
            echo "[entrypoint] MySQL 已就绪"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    echo "[entrypoint] 警告: 等待 MySQL 超时，将继续启动（若连接失败请检查数据库）"
}

# 初始化数据库表
init_db() {
    echo "[entrypoint] 执行数据库表初始化..."
    if python init_db_tables.py 2>/dev/null; then
        echo "[entrypoint] 数据库表初始化完成"
    else
        echo "[entrypoint] 数据库表初始化失败或跳过（可能使用 SQLite）"
    fi
}

cd /app
wait_for_mysql
init_db

# 启动应用（执行 CMD）
exec "$@"
