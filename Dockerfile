# ============================
# Stage 1: Build Python wheels
# ============================
FROM python:3.10-slim AS builder

WORKDIR /app

# 系统依赖（仅用于构建阶段）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 使用国内源加速
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip wheel --wheel-dir=/wheels -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple


# ============================
# Stage 2: Runtime image
# ============================
FROM python:3.10-slim AS runtime

LABEL maintainer="SmartParkingSystem"
LABEL description="Smart RTSP Stream Manager - 多阶段构建优化版"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 运行时依赖（比 builder 少很多）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 拷贝 wheels
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*

# 拷贝项目代码
COPY . .

# 创建必要目录
RUN mkdir -p /app/models /app/screenshots /app/hls /app/logs

# YOLO 模型自动处理
RUN if [ -f /app/models/yolov8n.pt ]; then true; \
    elif [ -f /app/app/yolov8n.pt ]; then cp /app/app/yolov8n.pt /app/models/ 2>/dev/null || true; fi

EXPOSE 10000

# 入口脚本
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000", "--workers", "1"]

