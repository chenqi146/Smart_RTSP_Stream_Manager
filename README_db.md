# 数据库说明（MySQL）

## 配置
默认配置（可用环境变量覆盖）：
- MYSQL_USER=root
- MYSQL_PASSWORD=test123456
- MYSQL_HOST=localhost
- MYSQL_PORT=3306
- MYSQL_DB=smart_rtsp

配置文件：`config.py`（基于环境变量生成 SQLAlchemy URL）。

## 创建数据库
在 MySQL 中先创建库：
```sql
CREATE DATABASE smart_rtsp DEFAULT CHARACTER SET utf8mb4;
```

## 表结构
- `tasks`：任务分片
  - date, index, start_ts, end_ts, rtsp_url, status, screenshot_path, error, created_at, updated_at
- `screenshots`：截图
  - task_id, file_path, hash_value, is_duplicate, kept_path, created_at
- `ocr_results`：OCR 结果
  - screenshot_id, detected_time, detected_timestamp, confidence, is_manual_corrected, corrected_time, corrected_timestamp, created_at, updated_at

## 初始化
运行服务时（`app/main.py`）会自动 `Base.metadata.create_all` 创建表。

## 数据流
1. `POST /api/tasks/create`：写入 tasks。
2. `POST /api/tasks/run`：拉流截图 → 保存截图记录 → OCR 结果写入 ocr_results → 去重更新 screenshots。

## 依赖
- SQLAlchemy >= 2.0
- PyMySQL（随 SQLAlchemy 自动调用；若缺失请 `pip install pymysql`）

