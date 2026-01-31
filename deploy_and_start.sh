#!/bin/bash
# Smart RTSP Stream Manager - 全自动部署脚本
# 使用方法: ./deploy_and_start.sh [端口号，默认8000]
# 
# 功能：从空白服务器开始，自动安装所有依赖并启动服务
# - 自动检测并安装 Python 和系统依赖
# - 自动创建虚拟环境
# - 自动安装 Python 包
# - 自动启动服务

PORT=${1:-8000}
PROJECT_DIR="/data/Smart_RTSP_Stream_Manager"
VENV_DIR="$PROJECT_DIR/.venv"
APP_MODULE="app.main:app"

echo "=========================================="
echo "Smart RTSP Stream Manager - 全自动部署"
echo "=========================================="
echo ""

# 检查是否为 root 用户
if [ "$EUID" -eq 0 ]; then
    IS_ROOT=true
    SUDO_CMD=""
else
    IS_ROOT=false
    SUDO_CMD="sudo"
fi

# 检查项目目录
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ 错误: 项目目录不存在: $PROJECT_DIR"
    echo "   请确保项目已部署到该目录"
    exit 1
fi

cd "$PROJECT_DIR"

# ============================================
# 第一步：检查并安装系统依赖
# ============================================
echo "🔍 第一步：检查系统依赖..."
echo ""

# 检查并安装 apt（如果是 Debian/Ubuntu 系统）
APT_CMD=""
if command -v apt >/dev/null 2>&1; then
    APT_CMD="apt"
elif command -v apt-get >/dev/null 2>&1; then
    APT_CMD="apt-get"
fi

if [ -n "$APT_CMD" ]; then
    # 检查是否需要更新包列表（仅在 root 用户时自动更新）
    if [ "$IS_ROOT" = "true" ]; then
        echo "📦 更新系统包列表..."
        $APT_CMD update -qq 2>/dev/null || true
    fi
fi

# 检查并安装 Python
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
    # 检查 Python 版本是否 >= 3.7
    PY_VERSION=$("$PYTHON_BIN" --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 7 ]); then
        echo "⚠️  Python 版本过低 ($PY_VERSION)，需要 Python 3.7+"
        PYTHON_BIN=""
    fi
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "⚠️  Python 3 未安装，尝试自动安装..."
    if [ -n "$APT_CMD" ] && [ "$IS_ROOT" = "true" ]; then
        if $APT_CMD install -y python3 python3-pip 2>/dev/null; then
            PYTHON_BIN="python3"
            echo "✅ Python 3 安装成功"
        else
            echo "❌ 无法自动安装 Python，请手动安装:"
            echo "   $SUDO_CMD $APT_CMD update"
            echo "   $SUDO_CMD $APT_CMD install -y python3 python3-pip"
            exit 1
        fi
    else
        echo "❌ 错误: 未找到 Python 3，且无法自动安装（需要 root 权限）"
        echo "   请手动安装:"
        echo "   $SUDO_CMD $APT_CMD update"
        echo "   $SUDO_CMD $APT_CMD install -y python3 python3-pip"
        exit 1
    fi
fi

# 检查 Python 版本
PYTHON_VERSION=$("$PYTHON_BIN" --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
echo "✅ Python 已安装: $("$PYTHON_BIN" --version)"

# 检查并安装 python3-venv
USE_WITHOUT_PIP=false
if ! "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
    echo "⚠️  python3-venv 未安装，尝试自动安装..."
    if [ -n "$APT_CMD" ]; then
        # 尝试多个可能的包名
        VENV_INSTALLED=false
        PYTHON_VERSION=$("$PYTHON_BIN" --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
        PYTHON_MAJOR_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f1,2)
        
        # 尝试安装不同版本的 venv 包（Ubuntu 22.04 通常使用 python3.10-venv）
        # 按优先级尝试：精确版本 -> 主版本 -> 通用包
        VENV_PACKAGES=(
            "python${PYTHON_VERSION}-venv"
            "python${PYTHON_MAJOR_MINOR}-venv"
            "python3.10-venv"
            "python3-venv"
        )
        
        for venv_pkg in "${VENV_PACKAGES[@]}"; do
            echo "   尝试安装: $venv_pkg"
            if $SUDO_CMD $APT_CMD install -y "$venv_pkg" 2>/dev/null; then
                VENV_INSTALLED=true
                echo "   ✅ 已安装: $venv_pkg"
                break
            fi
        done
        
        if [ "$VENV_INSTALLED" = "false" ]; then
            echo "   ⚠️  无法安装 python3-venv，将使用 --without-pip 选项"
            USE_WITHOUT_PIP=true
        else
            # 验证安装是否成功
            if "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
                USE_WITHOUT_PIP=false
            else
                echo "   ⚠️  venv 模块仍不可用，将使用 --without-pip 选项"
                USE_WITHOUT_PIP=true
            fi
        fi
    else
        echo "   ⚠️  无法自动安装 python3-venv（需要包管理器），将使用 --without-pip 选项"
        USE_WITHOUT_PIP=true
    fi
else
    # 检查 ensurepip 是否可用
    if ! "$PYTHON_BIN" -m ensurepip --help >/dev/null 2>&1; then
        echo "   ⚠️  ensurepip 不可用，将使用 --without-pip 选项"
        USE_WITHOUT_PIP=true
    fi
fi

# 检查并安装 curl 或 wget（用于下载 pip）
if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    echo "⚠️  curl/wget 未安装，尝试自动安装..."
    if [ -n "$APT_CMD" ]; then
        $SUDO_CMD $APT_CMD install -y curl 2>/dev/null || $SUDO_CMD $APT_CMD install -y wget 2>/dev/null || {
            echo "⚠️  无法安装 curl/wget，如果使用 --without-pip 可能需要手动安装 pip"
        }
    fi
fi

# 检查并安装 lsof（用于检查端口占用）
if ! command -v lsof >/dev/null 2>&1; then
    echo "⚠️  lsof 未安装，尝试自动安装..."
    if [ -n "$APT_CMD" ]; then
        $SUDO_CMD $APT_CMD install -y lsof 2>/dev/null || {
            echo "⚠️  无法安装 lsof，端口检查功能可能不可用"
        }
    fi
fi

# 检查并安装其他系统依赖（Ubuntu 22.04 可能需要）
if [ -n "$APT_CMD" ]; then
    echo "   检查其他系统依赖..."
    
    # OpenCV 需要的系统库
    MISSING_DEPS=()
    if ! ldconfig -p | grep -q libGL.so.1 2>/dev/null; then
        MISSING_DEPS+=("libgl1")
    fi
    if ! ldconfig -p | grep -q libglib-2.0.so.0 2>/dev/null; then
        MISSING_DEPS+=("libglib2.0-0")
    fi
    
    # FFmpeg（如果项目需要）
    if ! command -v ffmpeg >/dev/null 2>&1; then
        MISSING_DEPS+=("ffmpeg")
    fi
    
    # 安装缺失的依赖
    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        echo "   安装系统库: ${MISSING_DEPS[*]}"
        $SUDO_CMD $APT_CMD install -y "${MISSING_DEPS[@]}" 2>/dev/null || {
            echo "   ⚠️  部分系统库安装失败，但继续执行..."
        }
    fi
fi

echo "✅ 系统依赖检查完成"
echo ""

# ============================================
# 【可选但推荐】MySQL 安装与远程访问配置
# - 如果系统未安装 MySQL，会自动安装 mysql-server
# - 自动设置 root 账户密码为 test123456
# - 自动开放 3306 端口并允许远程连接（192.168.54.188 等外部工具可连接）
# - 自动设置本项目使用 MySQL 而不是 SQLite
# ============================================
echo "🗄  检查 MySQL 服务..."

MYSQL_ROOT_PASSWORD="test123456"

if [ -n "$APT_CMD" ]; then
    # 检查是否已安装 mysql 客户端
    if ! command -v mysql >/dev/null 2>&1; then
        echo "   未检测到 mysql 客户端，开始安装 mysql-server..."
        if $SUDO_CMD $APT_CMD install -y mysql-server 2>/dev/null; then
            echo "   ✅ mysql-server 安装完成"
        else
            echo "   ⚠️  安装 mysql-server 失败，稍后可能会使用 SQLite 作为后备数据库"
        fi
    fi
fi

# 启动并设置 MySQL 开机自启（如果已安装）
if command -v mysql >/dev/null 2>&1 && command -v systemctl >/dev/null 2>&1; then
    echo "   确保 MySQL 服务已启动..."
    $SUDO_CMD systemctl enable mysql >/dev/null 2>&1 || true
    $SUDO_CMD systemctl start mysql >/dev/null 2>&1 || true

    # 配置 MySQL 监听 0.0.0.0，允许远程连接
    MYSQL_CNF="/etc/mysql/mysql.conf.d/mysqld.cnf"
    if [ -f "$MYSQL_CNF" ]; then
        echo "   配置 MySQL 绑定地址为 0.0.0.0（允许远程连接）..."
        if grep -q "^bind-address" "$MYSQL_CNF" 2>/dev/null; then
            $SUDO_CMD sed -i 's/^bind-address.*/bind-address = 0.0.0.0/' "$MYSQL_CNF" || true
        else
            echo "" | $SUDO_CMD tee -a "$MYSQL_CNF" >/dev/null
            echo "[mysqld]" | $SUDO_CMD tee -a "$MYSQL_CNF" >/dev/null
            echo "bind-address = 0.0.0.0" | $SUDO_CMD tee -a "$MYSQL_CNF" >/dev/null
        fi
        $SUDO_CMD systemctl restart mysql >/dev/null 2>&1 || true
    fi

    # 设置 root 账户密码与远程访问（尽量容错，不因异常中断脚本）
    echo "   配置 MySQL root 账户密码与远程访问..."
    $SUDO_CMD mysql -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '${MYSQL_ROOT_PASSWORD}';" 2>/dev/null || true
    $SUDO_CMD mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';" 2>/dev/null || true
    $SUDO_CMD mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION; FLUSH PRIVILEGES;" 2>/dev/null || true

    # 自动创建项目数据库（如果不存在）
    $SUDO_CMD mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "CREATE DATABASE IF NOT EXISTS smart_rtsp DEFAULT CHARACTER SET utf8mb4;" 2>/dev/null || true

    # 自动开放防火墙 3306 端口（如果使用 ufw）
    if command -v ufw >/dev/null 2>&1; then
        UFW_STATUS=$($SUDO_CMD ufw status 2>/dev/null | head -n 1)
        if echo "$UFW_STATUS" | grep -qi "active"; then
            echo "   检测到 ufw 防火墙开启，开放 3306 端口..."
            $SUDO_CMD ufw allow 3306/tcp >/dev/null 2>&1 || true
            $SUDO_CMD ufw reload >/dev/null 2>&1 || true
        fi
    fi

    echo "   ✅ MySQL 检查/安装/配置完成"
else
    echo "   ℹ️  系统上未检测到 mysql 命令，可能未安装 mysql-server，将在应用中使用 SQLite 作为后备数据库（如已开启）。"
fi

# 为应用设置默认的 MySQL 环境变量（如未自行配置），强制使用 MySQL 而不是 SQLite
export MYSQL_USER="${MYSQL_USER:-root}"
export MYSQL_PASSWORD="${MYSQL_PASSWORD:-${MYSQL_ROOT_PASSWORD}}"
export MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
export MYSQL_PORT="${MYSQL_PORT:-3306}"
export MYSQL_DB="${MYSQL_DB:-smart_rtsp}"
export USE_SQLITE_FALLBACK="${USE_SQLITE_FALLBACK:-false}"

echo "   当前数据库配置："
echo "     MYSQL_HOST=$MYSQL_HOST"
echo "     MYSQL_PORT=$MYSQL_PORT"
echo "     MYSQL_DB=$MYSQL_DB"
echo "     MYSQL_USER=$MYSQL_USER"
echo "     USE_SQLITE_FALLBACK=$USE_SQLITE_FALLBACK"
echo ""

# ============================================
# 第二步：创建虚拟环境
# ============================================
echo "🔧 第二步：设置虚拟环境..."

if [ ! -d "$VENV_DIR" ]; then
    echo "   创建虚拟环境: $VENV_DIR"
    echo "   这可能需要几分钟时间，请耐心等待..."
    echo ""
    
    START_TIME=$(date +%s)
    NEED_INSTALL_PIP=false
    
    # 尝试创建虚拟环境
    if [ "$USE_WITHOUT_PIP" = "true" ]; then
        echo "   [使用 --without-pip 选项]"
        if "$PYTHON_BIN" -m venv --without-pip "$VENV_DIR" 2>&1; then
            VENV_EXIT_CODE=0
            NEED_INSTALL_PIP=true
        else
            VENV_EXIT_CODE=$?
        fi
    else
        # 先尝试正常创建
        if "$PYTHON_BIN" -m venv "$VENV_DIR" 2>&1; then
            VENV_EXIT_CODE=0
        else
            VENV_EXIT_CODE=$?
            # 如果失败，尝试使用 --without-pip
            if [ $VENV_EXIT_CODE -ne 0 ]; then
                echo "   [正常创建失败，尝试 --without-pip 选项]"
                [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR"
                if "$PYTHON_BIN" -m venv --without-pip "$VENV_DIR" 2>&1; then
                    VENV_EXIT_CODE=0
                    NEED_INSTALL_PIP=true
                    echo "   ✅ 使用 --without-pip 创建成功"
                else
                    VENV_EXIT_CODE=$?
                fi
            fi
        fi
    fi
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    if [ $VENV_EXIT_CODE -ne 0 ]; then
        echo "❌ 虚拟环境创建失败 (耗时: ${DURATION}秒)"
        echo ""
        echo "请检查："
        echo "  1. Python 版本是否兼容"
        echo "  2. 是否有足够的磁盘空间"
        echo "  3. 目录权限是否正确"
        exit 1
    fi
    
    echo "   ✅ 虚拟环境创建成功 (耗时: ${DURATION}秒)"
    
    # 验证虚拟环境
    sleep 2
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        echo "❌ 错误: 虚拟环境文件不完整"
        rm -rf "$VENV_DIR"
        exit 1
    fi
    
    # 如果使用了 --without-pip，安装 pip
    if [ "$NEED_INSTALL_PIP" = "true" ]; then
        echo ""
        echo "📦 安装 pip..."
        VENV_PYTHON="$VENV_DIR/bin/python"
        [ ! -f "$VENV_PYTHON" ] && VENV_PYTHON="$VENV_DIR/bin/python3"
        
        # 定义多个 pip 下载源（包括备用地址）
        PIP_SOURCES=(
            "https://bootstrap.pypa.io/get-pip.py"
            "https://raw.githubusercontent.com/pypa/get-pip/main/public/get-pip.py"
            "https://files.pythonhosted.org/packages/source/p/pip/get-pip.py"
        )
        
        PIP_DOWNLOADED=false
        DOWNLOAD_CMD=""
        
        # 确定下载命令
        if command -v curl >/dev/null 2>&1; then
            DOWNLOAD_CMD="curl -sSL --connect-timeout 10 --max-time 30"
        elif command -v wget >/dev/null 2>&1; then
            DOWNLOAD_CMD="wget -q --timeout=10 --tries=2 -O"
        else
            echo "❌ 错误: 需要 curl 或 wget 来下载 pip"
            exit 1
        fi
        
        # 尝试从多个源下载
        for pip_url in "${PIP_SOURCES[@]}"; do
            echo "   尝试下载 pip 安装脚本: $pip_url"
            
            if [ -n "$DOWNLOAD_CMD" ]; then
                if command -v curl >/dev/null 2>&1; then
                    if curl -sSL --connect-timeout 10 --max-time 30 "$pip_url" -o /tmp/get-pip.py 2>/dev/null; then
                        if [ -f /tmp/get-pip.py ] && [ -s /tmp/get-pip.py ] && head -1 /tmp/get-pip.py | grep -q "python\|#!/" 2>/dev/null; then
                            PIP_DOWNLOADED=true
                            echo "   ✅ 下载成功"
                            break
                        else
                            rm -f /tmp/get-pip.py
                        fi
                    fi
                elif command -v wget >/dev/null 2>&1; then
                    if wget -q --timeout=10 --tries=2 "$pip_url" -O /tmp/get-pip.py 2>/dev/null; then
                        if [ -f /tmp/get-pip.py ] && [ -s /tmp/get-pip.py ] && head -1 /tmp/get-pip.py | grep -q "python\|#!/" 2>/dev/null; then
                            PIP_DOWNLOADED=true
                            echo "   ✅ 下载成功"
                            break
                        else
                            rm -f /tmp/get-pip.py
                        fi
                    fi
                fi
            fi
        done
        
        # 如果所有源都失败，尝试使用系统 python3-pip 包
        if [ "$PIP_DOWNLOADED" = "false" ]; then
            echo "   ⚠️  所有下载源均失败，尝试使用系统 python3-pip 包..."
            
            if [ -n "$APT_CMD" ]; then
                if $SUDO_CMD $APT_CMD install -y python3-pip 2>/dev/null; then
                    # 复制系统 pip 到虚拟环境
                    SYSTEM_PIP=$(which pip3 2>/dev/null || which pip 2>/dev/null)
                    if [ -n "$SYSTEM_PIP" ] && [ -f "$SYSTEM_PIP" ]; then
                        echo "   复制系统 pip 到虚拟环境..."
                        cp "$SYSTEM_PIP" "$VENV_DIR/bin/pip" 2>/dev/null || true
                        cp "$SYSTEM_PIP" "$VENV_DIR/bin/pip3" 2>/dev/null || true
                        # 复制 pip 相关的包
                        SYSTEM_PIP_DIR=$(dirname "$SYSTEM_PIP")
                        if [ -d "$SYSTEM_PIP_DIR/../lib/python3/dist-packages/pip" ]; then
                            mkdir -p "$VENV_DIR/lib/python3/dist-packages" 2>/dev/null || true
                            cp -r "$SYSTEM_PIP_DIR/../lib/python3/dist-packages/pip" "$VENV_DIR/lib/python3/dist-packages/" 2>/dev/null || true
                        fi
                        if "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
                            PIP_DOWNLOADED=true
                            echo "   ✅ 使用系统 pip 安装成功"
                        fi
                    fi
                fi
            fi
        fi
        
        # 如果仍然失败，尝试使用 ensurepip（如果可用）
        if [ "$PIP_DOWNLOADED" = "false" ]; then
            echo "   ⚠️  尝试使用 ensurepip..."
            
            # 检查系统 Python 是否有 ensurepip
            if "$PYTHON_BIN" -c "import ensurepip" 2>/dev/null; then
                echo "   使用系统 ensurepip 安装 pip..."
                "$VENV_PYTHON" -m ensurepip --upgrade --default-pip 2>&1
                if "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
                    PIP_DOWNLOADED=true
                    echo "   ✅ 使用 ensurepip 安装成功"
                fi
            fi
        fi
        
        # 如果仍然失败，提供手动安装指导
        if [ "$PIP_DOWNLOADED" = "false" ]; then
            echo ""
            echo "❌ 错误: 无法自动下载 pip 安装脚本"
            echo ""
            echo "可能的原因："
            echo "  1. 网络连接问题（无法访问 pip 下载源）"
            echo "  2. 防火墙阻止了连接"
            echo "  3. DNS 解析失败"
            echo ""
            echo "解决方案："
            echo "  方案 1: 手动下载并安装 pip"
            echo "    curl -sSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py"
            echo "    或"
            echo "    wget https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py"
            echo "    然后运行: $VENV_PYTHON /tmp/get-pip.py"
            echo ""
            echo "  方案 2: 使用国内镜像下载"
            echo "    curl -sSL https://mirrors.aliyun.com/pypi/simple/get-pip.py -o /tmp/get-pip.py"
            echo "    或"
            echo "    wget https://mirrors.aliyun.com/pypi/simple/get-pip.py -O /tmp/get-pip.py"
            echo "    然后运行: $VENV_PYTHON /tmp/get-pip.py"
            echo ""
            echo "  方案 3: 安装 python3-pip 系统包并复制到虚拟环境"
            echo "    $SUDO_CMD $APT_CMD install -y python3-pip"
            echo "    然后复制 pip 到虚拟环境:"
            echo "    SYSTEM_PIP=\$(which pip3)"
            echo "    cp \$SYSTEM_PIP $VENV_DIR/bin/pip"
            echo "    cp \$SYSTEM_PIP $VENV_DIR/bin/pip3"
            echo ""
            echo "  方案 4: 使用系统 Python 的 ensurepip（如果可用）"
            echo "    $VENV_PYTHON -m ensurepip --upgrade --default-pip"
            echo ""
            exit 1
        fi
        
        # 安装 pip
        if [ -f /tmp/get-pip.py ]; then
            echo "   正在安装 pip..."
            if "$VENV_PYTHON" /tmp/get-pip.py --quiet 2>&1; then
                rm -f /tmp/get-pip.py
                # 验证 pip 是否安装成功
                if "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
                    echo "   ✅ pip 安装完成"
                else
                    echo "   ⚠️  pip 安装可能不完整，但继续执行..."
                fi
            else
                echo "   ⚠️  pip 安装过程有警告，但继续执行..."
                rm -f /tmp/get-pip.py
            fi
        fi
    fi
else
    echo "   ✅ 虚拟环境已存在"
fi

# 激活虚拟环境
if ! source "$VENV_DIR/bin/activate" 2>/dev/null; then
    echo "❌ 错误: 无法激活虚拟环境"
    exit 1
fi

if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ 错误: 虚拟环境激活失败"
    exit 1
fi

echo "✅ 虚拟环境已激活"

# 检查虚拟环境中是否有 pip
if ! python -m pip --version >/dev/null 2>&1 && ! command -v pip >/dev/null 2>&1; then
    echo ""
    echo "⚠️  虚拟环境中缺少 pip，开始安装..."
    
    VENV_PYTHON="$VENV_DIR/bin/python"
    [ ! -f "$VENV_PYTHON" ] && VENV_PYTHON="$VENV_DIR/bin/python3"
    
    # 定义多个 pip 下载源（包括备用地址）
    PIP_SOURCES=(
        "https://bootstrap.pypa.io/get-pip.py"
        "https://raw.githubusercontent.com/pypa/get-pip/main/public/get-pip.py"
        "https://files.pythonhosted.org/packages/source/p/pip/get-pip.py"
    )
    
    PIP_INSTALLED=false
    DOWNLOAD_CMD=""
    
    # 确定下载命令
    if command -v curl >/dev/null 2>&1; then
        DOWNLOAD_CMD="curl"
    elif command -v wget >/dev/null 2>&1; then
        DOWNLOAD_CMD="wget"
    fi
    
    # 尝试从多个源下载
    if [ -n "$DOWNLOAD_CMD" ]; then
        for pip_url in "${PIP_SOURCES[@]}"; do
            echo "   尝试下载 pip 安装脚本: $pip_url"
            
            if [ "$DOWNLOAD_CMD" = "curl" ]; then
                if curl -sSL --connect-timeout 10 --max-time 30 "$pip_url" -o /tmp/get-pip.py 2>/dev/null; then
                    if [ -f /tmp/get-pip.py ] && [ -s /tmp/get-pip.py ] && head -1 /tmp/get-pip.py | grep -q "python\|#!/" 2>/dev/null; then
                        PIP_INSTALLED=true
                        echo "   ✅ 下载成功"
                        break
                    else
                        rm -f /tmp/get-pip.py
                    fi
                fi
            elif [ "$DOWNLOAD_CMD" = "wget" ]; then
                if wget -q --timeout=10 --tries=2 "$pip_url" -O /tmp/get-pip.py 2>/dev/null; then
                    if [ -f /tmp/get-pip.py ] && [ -s /tmp/get-pip.py ] && head -1 /tmp/get-pip.py | grep -q "python\|#!/" 2>/dev/null; then
                        PIP_INSTALLED=true
                        echo "   ✅ 下载成功"
                        break
                    else
                        rm -f /tmp/get-pip.py
                    fi
                fi
            fi
        done
    fi
    
    # 如果所有源都失败，尝试使用系统 python3-pip 包
    if [ "$PIP_INSTALLED" = "false" ]; then
        echo "   ⚠️  所有下载源均失败，尝试使用系统 python3-pip 包..."
        
        if [ -n "$APT_CMD" ]; then
            if $SUDO_CMD $APT_CMD install -y python3-pip 2>/dev/null; then
                # 复制系统 pip 到虚拟环境
                SYSTEM_PIP=$(which pip3 2>/dev/null || which pip 2>/dev/null)
                if [ -n "$SYSTEM_PIP" ] && [ -f "$SYSTEM_PIP" ]; then
                    echo "   复制系统 pip 到虚拟环境..."
                    cp "$SYSTEM_PIP" "$VENV_DIR/bin/pip" 2>/dev/null || true
                    cp "$SYSTEM_PIP" "$VENV_DIR/bin/pip3" 2>/dev/null || true
                    # 复制 pip 相关的包
                    SYSTEM_PIP_DIR=$(dirname "$SYSTEM_PIP")
                    SYSTEM_PYTHON_VERSION=$("$VENV_PYTHON" --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
                    if [ -d "/usr/lib/python3/dist-packages/pip" ]; then
                        mkdir -p "$VENV_DIR/lib/python${SYSTEM_PYTHON_VERSION}/site-packages" 2>/dev/null || true
                        cp -r /usr/lib/python3/dist-packages/pip "$VENV_DIR/lib/python${SYSTEM_PYTHON_VERSION}/site-packages/" 2>/dev/null || true
                    fi
                    if "$VENV_PYTHON" -m pip --version >/dev/null 2>&1 || command -v pip >/dev/null 2>&1; then
                        PIP_INSTALLED=true
                        echo "   ✅ 使用系统 pip 安装成功"
                    fi
                fi
            fi
        fi
    fi
    
    # 如果仍然失败，尝试使用 ensurepip（如果可用）
    if [ "$PIP_INSTALLED" = "false" ]; then
        echo "   ⚠️  尝试使用 ensurepip..."
        
        # 检查系统 Python 是否有 ensurepip
        if "$PYTHON_BIN" -c "import ensurepip" 2>/dev/null; then
            echo "   使用系统 ensurepip 安装 pip..."
            "$VENV_PYTHON" -m ensurepip --upgrade --default-pip 2>&1
            if "$VENV_PYTHON" -m pip --version >/dev/null 2>&1 || command -v pip >/dev/null 2>&1; then
                PIP_INSTALLED=true
                echo "   ✅ 使用 ensurepip 安装成功"
            fi
        fi
    fi
    
    # 安装 pip（如果下载成功）
    if [ "$PIP_INSTALLED" = "true" ] && [ -f /tmp/get-pip.py ]; then
        echo "   正在安装 pip..."
        if "$VENV_PYTHON" /tmp/get-pip.py --quiet 2>&1; then
            rm -f /tmp/get-pip.py
            # 验证 pip 是否安装成功
            if "$VENV_PYTHON" -m pip --version >/dev/null 2>&1 || command -v pip >/dev/null 2>&1; then
                echo "   ✅ pip 安装完成"
                PIP_INSTALLED=true
            else
                echo "   ⚠️  pip 安装可能不完整"
                PIP_INSTALLED=false
            fi
        else
            echo "   ⚠️  pip 安装过程有警告"
            rm -f /tmp/get-pip.py
            PIP_INSTALLED=false
        fi
    fi
    
    # 如果仍然失败，提供手动安装指导
    if [ "$PIP_INSTALLED" = "false" ]; then
        echo ""
        echo "❌ 错误: 无法自动安装 pip"
        echo ""
        echo "请手动安装 pip，然后重新运行脚本："
        echo ""
        echo "方法 1: 下载并安装 pip"
        echo "  curl -sSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py"
        echo "  $VENV_PYTHON /tmp/get-pip.py"
        echo ""
        echo "方法 2: 使用系统 pip"
        echo "  $SUDO_CMD $APT_CMD install -y python3-pip"
        echo "  cp \$(which pip3) $VENV_DIR/bin/pip"
        echo "  cp \$(which pip3) $VENV_DIR/bin/pip3"
        echo ""
        exit 1
    fi
fi

echo ""

# ============================================
# 第三步：安装 Python 依赖
# ============================================
echo "📦 第三步：安装 Python 依赖..."

# 验证 pip 是否可用
if ! python -m pip --version >/dev/null 2>&1 && ! command -v pip >/dev/null 2>&1; then
    echo "❌ 错误: pip 不可用，无法安装依赖"
    echo "   请先安装 pip，然后重新运行脚本"
    exit 1
fi

# 升级 pip
echo "   升级 pip..."
if python -m pip --version >/dev/null 2>&1; then
    python -m pip install --upgrade pip --quiet 2>&1 || pip install --upgrade pip --quiet 2>&1 || true
else
    pip install --upgrade pip --quiet 2>&1 || true
fi

# 安装依赖
if [ ! -f "requirements.txt" ]; then
    echo "❌ 错误: requirements.txt 文件不存在"
    exit 1
fi

echo "   安装项目依赖（这可能需要几分钟）..."
if python -m pip --version >/dev/null 2>&1; then
    if python -m pip install -r requirements.txt 2>&1; then
        echo "✅ 依赖安装完成"
    else
        echo "❌ 错误: 依赖安装失败"
        echo "   请检查 requirements.txt 和网络连接"
        exit 1
    fi
elif command -v pip >/dev/null 2>&1; then
    if pip install -r requirements.txt 2>&1; then
        echo "✅ 依赖安装完成"
    else
        echo "❌ 错误: 依赖安装失败"
        echo "   请检查 requirements.txt 和网络连接"
        exit 1
    fi
else
    echo "❌ 错误: 无法找到 pip 命令"
    exit 1
fi
echo ""

# ============================================
# 第四步：预加载 YOLO 模型（可选，不阻塞）
# ============================================
echo "🤖 第四步：预加载 YOLO 模型（可选，不阻塞启动）..."
if [ -f "services/yolo_detector.py" ]; then
    echo "   尝试预加载 YOLO 模型（后台进行，不阻塞服务启动）..."
    python - << 'PY' 2>&1 | head -30 || true
try:
    import sys
    import os
    sys.path.insert(0, os.getcwd())
    from services.yolo_detector import preload_model
    ok = preload_model()
    if ok:
        print("✅ YOLO 模型已准备就绪")
    else:
        print("⚠️  预加载 YOLO 模型失败，服务仍会启动")
        print("   稍后可手动运行: python tests/test_yolo_download.py")
except ImportError as e:
    print(f"⚠️  YOLO 依赖未安装: {e}")
    print("   服务仍会正常启动，YOLO 功能可能不可用")
except Exception as e:
    print(f"⚠️  YOLO 模型预加载跳过: {type(e).__name__}: {e}")
    print("   服务仍会正常启动")
PY
    echo "   ✅ YOLO 模型预加载完成（或已跳过）"
else
    echo "   ℹ️  未找到 YOLO 检测器，跳过模型预加载"
fi
echo ""

# ============================================
# 第五步：检查静态文件
# ============================================
echo "📁 第五步：检查静态文件..."

if [ -f "check_static_files.py" ]; then
    echo "   运行静态文件检查脚本..."
    if python check_static_files.py 2>&1; then
        echo "   ✅ 静态文件检查完成"
    else
        echo "   ⚠️  静态文件检查失败，请确保所有前端文件已正确上传"
    fi
else
    echo "   ⚠️  未找到 check_static_files.py，跳过静态文件检查"
fi
echo ""

# ============================================
# 第六步：初始化数据库表
# ============================================
echo "🗄️  第六步：初始化数据库表..."

if [ -f "init_db_tables.py" ]; then
    echo "   运行数据库表初始化脚本..."
    if python init_db_tables.py 2>&1; then
        echo "   ✅ 数据库表初始化完成"
    else
        echo "   ⚠️  数据库表初始化失败，但继续执行（应用启动时会再次尝试创建表）"
    fi
else
    echo "   ⚠️  未找到 init_db_tables.py，跳过显式表创建（应用启动时会自动创建）"
fi
echo ""

# ============================================
# 第七步：停止旧服务
# ============================================
echo "🛑 第七步：停止旧服务（如果存在）..."

# 查找并停止旧进程
OLD_PID=$(ps aux | grep "uvicorn.*$APP_MODULE" | grep -v grep | awk '{print $2}' | head -1)
if [ -n "$OLD_PID" ]; then
    echo "   发现运行中的进程 (PID: $OLD_PID)，正在停止..."
    kill -15 "$OLD_PID" 2>/dev/null || true
    sleep 2
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        kill -9 "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
    echo "   ✅ 旧进程已停止"
else
    echo "   ℹ️  未发现运行中的服务进程"
fi

# 检查并释放端口
if command -v lsof >/dev/null 2>&1; then
    PORT_PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PORT_PID" ]; then
        echo "   ⚠️  端口 $PORT 被占用 (PID: $PORT_PID)，正在释放..."
        kill -15 "$PORT_PID" 2>/dev/null || true
        sleep 2
        if ps -p "$PORT_PID" > /dev/null 2>&1; then
            kill -9 "$PORT_PID" 2>/dev/null || true
        fi
        echo "   ✅ 端口已释放"
    fi
fi
echo ""

# ============================================
# 第八步：启动服务
# ============================================
echo "🚀 第八步：启动服务..."
echo ""

# 创建日志目录并设置权限
LOG_FILE="$PROJECT_DIR/logs/app.log"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
# 确保日志目录有正确的权限（当前用户可读写执行，组和其他用户可读执行）
chmod 755 "$LOG_DIR" 2>/dev/null || true
# 确保日志目录的所有者是当前用户（如果可能）
CURRENT_USER=$(whoami 2>/dev/null || echo "")
if [ -n "$CURRENT_USER" ]; then
    chown "$CURRENT_USER:$CURRENT_USER" "$LOG_DIR" 2>/dev/null || true
fi
# 如果日志文件已存在，确保有写入权限；若当前用户无法写入则先尝试修复再检查
if [ -f "$LOG_FILE" ]; then
    chmod 644 "$LOG_FILE" 2>/dev/null || true
    if [ -n "$CURRENT_USER" ]; then
        chown "$CURRENT_USER:$CURRENT_USER" "$LOG_FILE" 2>/dev/null || true
    fi
fi
# 确保当前用户能写入日志文件（避免 nohup > app.log 时 Permission denied）
if ! ( : > "$LOG_FILE" ) 2>/dev/null; then
    echo "❌ 无法写入日志文件: $LOG_FILE"
    echo "   可能原因: 文件属主为 root 或其他用户。请执行以下命令后重试:"
    echo "   sudo chown $CURRENT_USER:$CURRENT_USER $LOG_FILE"
    echo "   或: sudo chown -R $CURRENT_USER:$CURRENT_USER $LOG_DIR"
    exit 1
fi

# 检查 uvicorn 是否安装
if ! python -c "import uvicorn" 2>/dev/null; then
    echo "❌ 错误: uvicorn 未安装"
    echo "   请检查依赖安装是否成功"
    exit 1
fi

# 启动服务
echo "   启动命令: uvicorn $APP_MODULE --host 0.0.0.0 --port $PORT --workers 1"
nohup uvicorn "$APP_MODULE" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    > "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo "   ✅ 服务已启动 (PID: $NEW_PID)"
echo "   📝 日志文件: $LOG_FILE"
echo ""

# 等待服务启动
echo "⏳ 等待服务启动（5秒）..."
sleep 5

# 检查服务是否正常运行
if ps -p "$NEW_PID" > /dev/null 2>&1; then
    # 尝试获取服务器 IP
    SERVER_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "localhost")
    
    echo "✅ 服务运行正常"
    echo ""
    echo "=========================================="
    echo "🎉 部署完成！服务信息："
    echo "=========================================="
    echo "  - 进程 ID: $NEW_PID"
    echo "  - 服务端口: $PORT"
    echo "  - Web 界面: http://$SERVER_IP:$PORT"
    echo "  - API 文档: http://$SERVER_IP:$PORT/docs"
    echo "  - 健康检查: http://$SERVER_IP:$PORT/healthz"
    echo "=========================================="
    echo ""
    echo "📋 常用命令："
    echo "  查看日志: tail -f $LOG_FILE"
    echo "  停止服务: kill $NEW_PID"
    echo "  查看进程: ps aux | grep uvicorn"
    echo ""
    
    # 尝试访问健康检查端点（可选）
    echo "🔍 验证服务可访问性..."
    sleep 3
    
    # 多次尝试健康检查（最多3次）
    HEALTH_CHECK_OK=false
    for i in {1..3}; do
        if command -v curl >/dev/null 2>&1; then
            if curl -s -f -m 5 "http://localhost:$PORT/healthz" >/dev/null 2>&1; then
                HEALTH_CHECK_OK=true
                echo "   ✅ 健康检查通过（尝试 $i/3）"
                break
            fi
        elif command -v wget >/dev/null 2>&1; then
            if wget -q -O /dev/null --timeout=5 "http://localhost:$PORT/healthz" 2>/dev/null; then
                HEALTH_CHECK_OK=true
                echo "   ✅ 健康检查通过（尝试 $i/3）"
                break
            fi
        fi
        if [ $i -lt 3 ]; then
            sleep 2
        fi
    done
    
    if [ "$HEALTH_CHECK_OK" = "false" ]; then
        echo "   ⚠️  健康检查未响应（服务可能仍在启动中）"
        echo "   请稍后访问: http://$SERVER_IP:$PORT"
        echo "   或查看日志: tail -f $LOG_FILE"
    fi
else
    echo "❌ 服务启动失败"
    echo ""
    echo "请检查日志文件: $LOG_FILE"
    echo "查看最后 50 行日志:"
    tail -50 "$LOG_FILE" 2>/dev/null || echo "   无法读取日志文件（请检查权限: sudo chown \$(whoami) $LOG_FILE）"
    echo ""
    echo "若日志中出现 'Can't connect to MySQL server'，请先启动 MySQL 并确认配置正确。"
    exit 1
fi

echo ""
echo "✨ 部署脚本执行完成！"
