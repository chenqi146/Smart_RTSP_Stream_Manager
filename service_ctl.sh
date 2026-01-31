#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

CMD="${1:-start}"
PORT="${2:-${PORT:-10000}}"
HOST="${HOST:-0.0.0.0}"

# 自动激活 conda 环境（如存在）
CONDA_ENV_PATH="/data/Smart_RTSP_Stream_Manager/.conda/envs/rtsp-py310"
if [ -d "$CONDA_ENV_PATH" ]; then
  if command -v conda >/dev/null 2>&1; then
    # shellcheck disable=SC1091
    source "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh" 2>/dev/null || true
    conda activate "$CONDA_ENV_PATH" 2>/dev/null || true
  fi
fi

# 加载 .env（如果存在）
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

export PYTHONPATH="$ROOT_DIR"

# MySQL 配置（默认值与 deploy_and_start.sh 保持一致）
export MYSQL_USER="${MYSQL_USER:-root}"
export MYSQL_PASSWORD="${MYSQL_PASSWORD:-test123456}"
export MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
export MYSQL_PORT="${MYSQL_PORT:-3306}"
export MYSQL_DB="${MYSQL_DB:-smart_rtsp}"
export USE_SQLITE_FALLBACK="${USE_SQLITE_FALLBACK:-false}"

# 日志配置（参考 deploy_and_start.sh）
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/app.log"
PID_FILE="$LOG_DIR/app.pid"

ensure_log_file() {
  mkdir -p "$LOG_DIR"
  chmod 755 "$LOG_DIR" 2>/dev/null || true
  CURRENT_USER=$(whoami 2>/dev/null || echo "")
  if [ -n "$CURRENT_USER" ]; then
    chown "$CURRENT_USER:$CURRENT_USER" "$LOG_DIR" 2>/dev/null || true
  fi
  if [ -f "$LOG_FILE" ]; then
    chmod 644 "$LOG_FILE" 2>/dev/null || true
    if [ -n "$CURRENT_USER" ]; then
      chown "$CURRENT_USER:$CURRENT_USER" "$LOG_FILE" 2>/dev/null || true
    fi
  fi
  if ! ( : >> "$LOG_FILE" ) 2>/dev/null; then
    echo "❌ 无法写入日志文件: $LOG_FILE"
    echo "   请修复权限后重试"
    exit 1
  fi
}

is_running() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
      CMDLINE=$(ps -p "$PID" -o command= 2>/dev/null || echo "")
      if echo "$CMDLINE" | grep -q "uvicorn .*app.main:app"; then
        return 0
      fi
    fi
  fi
  return 1
}

start_server() {
  if is_running; then
    echo "服务已在运行中 (PID: $(cat "$PID_FILE"))"
    exit 0
  fi

  ensure_log_file

  UVICORN_CMD="uvicorn"
  if ! command -v uvicorn >/dev/null 2>&1; then
    if python -m uvicorn --version >/dev/null 2>&1; then
      UVICORN_CMD="python -m uvicorn"
    else
      echo "❌ 未找到 uvicorn，请先在当前环境安装: pip install uvicorn"
      exit 1
    fi
  fi

  echo "数据库配置:"
  echo "  MYSQL_HOST=$MYSQL_HOST"
  echo "  MYSQL_PORT=$MYSQL_PORT"
  echo "  MYSQL_DB=$MYSQL_DB"
  echo "  MYSQL_USER=$MYSQL_USER"
  echo "  USE_SQLITE_FALLBACK=$USE_SQLITE_FALLBACK"

  nohup $UVICORN_CMD app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    > "$LOG_FILE" 2>&1 &

  echo $! > "$PID_FILE"

  echo "Uvicorn started in background"
  echo "PID: $(cat "$PID_FILE")"
  echo "Log: $LOG_FILE"
}

stop_server() {
  if is_running; then
    PID=$(cat "$PID_FILE")
    echo "停止服务 (PID: $PID)..."
    kill -15 "$PID" 2>/dev/null || true
    sleep 2
    if ps -p "$PID" > /dev/null 2>&1; then
      kill -9 "$PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "服务已停止"
    return 0
  fi

  # 兜底：查找可能的遗留进程
  PID=$(ps aux | grep "uvicorn.*app.main:app" | grep -v grep | awk '{print $2}' | head -1)
  if [ -n "$PID" ]; then
    echo "发现未记录的服务进程 (PID: $PID)，停止中..."
    kill -15 "$PID" 2>/dev/null || true
    sleep 2
    if ps -p "$PID" > /dev/null 2>&1; then
      kill -9 "$PID" 2>/dev/null || true
    fi
    echo "服务已停止"
    return 0
  fi

  echo "未发现运行中的服务"
  return 1
}

case "$CMD" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  restart)
    if ! stop_server; then
      start_server
      exit 0
    fi
    start_server
    ;;
  *)
    echo "用法: $0 {start|stop|restart} [port]"
    exit 1
    ;;
esac
