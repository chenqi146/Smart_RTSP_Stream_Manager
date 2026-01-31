# Smart RTSP Stream Manager - Docker 部署说明

本文档说明如何使用 Docker 一键部署 Smart RTSP Stream Manager（含 MySQL、应用服务、数据卷与健康检查）。

---

## 一、前置要求

- 已安装 **Docker**（建议 20.10+）
- 已安装 **Docker Compose**（V2 为 `docker compose`，V1 为 `docker-compose`）
- Windows 建议使用 **Docker Desktop**（已包含 Compose）

---

## 二、一键部署

### 2.1 Linux / macOS

```bash
cd /path/to/Smart_RTSP_Stream_Manager
chmod +x deploy_docker.sh
./deploy_docker.sh
```

### 2.2 Windows (PowerShell)

```powershell
cd D:\PycharmProjects\QJZH-Project\SmartParkingSystem\Smart_RTSP_Stream_Manager
.\deploy_docker.ps1
```

### 2.3 手动执行（不依赖脚本）

```bash
# 1. 复制并编辑环境变量（必做）
cp .env.example .env
# 编辑 .env：必须设置 APP_PORT（本机可用端口，如 8080），以及 MySQL 密码等

# 2. 构建并启动
docker compose up -d --build
# 或
docker-compose up -d --build
```

---

## 三、目录与文件说明

| 文件/目录 | 说明 |
|-----------|------|
| `Dockerfile` | 应用镜像构建（python:slim 自动拉取、依赖、YOLO、入口脚本） |
| `docker-compose.yml` | 编排：MySQL 8 + 应用服务、卷、健康检查 |
| `docker/entrypoint.sh` | 容器入口：等待 MySQL → 初始化表 → 启动 uvicorn |
| `.env.example` | 环境变量示例，复制为 `.env` 后按需修改 |
| `.dockerignore` | 构建时排除的目录（日志、截图、测试等） |
| `deploy_docker.sh` | Linux/macOS 一键部署脚本 |
| `deploy_docker.ps1` | Windows 一键部署脚本 |

---

## 四、服务与端口

- **应用 (app)**：对外端口由 **`.env` 中 `APP_PORT` 指定（必填）**，请填写本机可用端口，避免与 8000 等其它项目冲突。
  - Web 界面: `http://<主机>:<APP_PORT>`
  - API 文档: `http://<主机>:<APP_PORT>/docs`
  - 健康检查: `http://<主机>:<APP_PORT>/healthz`
- **MySQL**：端口 **3306**（仅宿主机访问时可映射，同一 compose 内 app 使用服务名 `mysql`）

---

## 五、环境变量（.env）

| 变量 | 说明 | 默认 |
|------|------|------|
| `MYSQL_HOST` | MySQL 主机（compose 内填 `mysql`） | mysql |
| `MYSQL_PORT` | MySQL 端口 | 3306 |
| `MYSQL_USER` | 数据库用户（与项目 config.py 一致） | root |
| `MYSQL_PASSWORD` | 数据库密码（与项目 config.py 一致） | test123456 |
| `MYSQL_DB` | 数据库名 | smart_rtsp |
| `MYSQL_ROOT_PASSWORD` | root 密码（MySQL 容器，建议与 MYSQL_PASSWORD 一致） | test123456 |
| `USE_SQLITE_FALLBACK` | 是否回退 SQLite（Docker 建议 false） | false |
| `APP_PORT` | 应用对外端口（必填，建议 8080/9000 等，避免冲突） | 无默认，需在 .env 中设置 |
| `MAX_COMBO_CONCURRENCY` | 并发组合数 | 4 |
| `MAX_WORKERS_PER_COMBO` | 每组合并发数 | 2 |

---

## 六、数据持久化

以下通过 Docker 卷持久化，重启/重建容器不丢失：

- `mysql_data`：MySQL 数据
- `screenshot_data`：截图目录（挂载到 `/app/screenshots`）
- `hls_data`：HLS 临时文件（挂载到 `/app/hls`）
- `log_data`：应用日志（挂载到 `/app/logs`）

---

## 七、常用命令

```bash
# 查看应用日志
docker compose logs -f app

# 查看 MySQL 日志
docker compose logs -f mysql

# 停止并删除容器（保留卷）
docker compose down

# 停止并删除容器及卷（清空数据）
docker compose down -v

# 仅重启应用
docker compose restart app

# 重新构建并启动
docker compose up -d --build
```

---

## 八、生产建议

1. **修改默认密码**：在 `.env` 中设置强密码 `MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD`。
2. **不暴露 MySQL 端口**：若仅本机访问应用，可在 `docker-compose.yml` 中删除 `mysql` 的 `ports`，避免 3306 暴露。
3. **资源限制**：可在 `app` 服务下增加 `deploy.resources.limits`（cpu、memory）。
4. **HTTPS**：对外提供 HTTPS 时，可在宿主机用 Nginx/Caddy 反向代理 `APP_PORT`，或另行配置 TLS。

---

## 九、故障排查

- **应用启动失败**：`docker compose logs app` 查看是否连不上 MySQL；确认 `.env` 中 `MYSQL_HOST=mysql`、密码与 MySQL 服务一致。
- **健康检查失败**：确认 `.env` 中已设置 `APP_PORT`，且该端口未被占用；容器内应用监听 `0.0.0.0:8000`。
- **YOLO 模型**：镜像内已包含 `app/yolov8n.pt` 或 `models/yolov8n.pt`；若缺失，首次运行会自动下载（需网络）。
