@echo off
REM Windows 批处理部署脚本
REM 使用方法: deploy.bat [服务器地址] [目标路径]
REM 示例: deploy.bat ubuntu@192.168.54.188 /data

setlocal enabledelayedexpansion

set SERVER=%1
if "%SERVER%"=="" set SERVER=ubuntu@192.168.54.188

set TARGET_DIR=%2
if "%TARGET_DIR%"=="" set TARGET_DIR=/data

set PROJECT_NAME=Smart_RTSP_Stream_Manager
set LOCAL_DIR=%~dp0

echo ==========================================
echo 代码部署脚本 (Windows Batch)
echo ==========================================
echo 服务器: %SERVER%
echo 目标目录: %TARGET_DIR%
echo 项目名称: %PROJECT_NAME%
echo 本地目录: %LOCAL_DIR%
echo.

REM 检查是否有 rsync (通过 Git Bash)
set RSYNC_CMD=
where rsync >nul 2>&1
if %ERRORLEVEL%==0 (
    set RSYNC_CMD=rsync
) else if exist "C:\Program Files\Git\usr\bin\rsync.exe" (
    set RSYNC_CMD="C:\Program Files\Git\usr\bin\rsync.exe"
) else (
    echo 使用 scp 命令同步（较慢但兼容性好）...
    echo.
    echo 正在同步代码...
    scp -r "%LOCAL_DIR%Smart_RTSP_Stream_Manager" %SERVER%:%TARGET_DIR%/
    if %ERRORLEVEL%==0 (
        echo.
        echo 代码同步完成！
        echo.
        echo 下一步操作：
        echo   1. SSH 连接到服务器: ssh %SERVER%
        echo   2. 进入项目目录: cd %TARGET_DIR%/%PROJECT_NAME%
        echo   3. 运行部署脚本: sudo ./deploy_and_start.sh
        echo.
    ) else (
        echo.
        echo 代码同步失败，请检查网络连接和服务器权限
        exit /b 1
    )
    exit /b 0
)

echo 使用 rsync 同步代码（推荐）...
echo.

REM 排除的文件和目录（rsync 格式）
set EXCLUDE_ARGS=--exclude=__pycache__ --exclude=*.pyc --exclude=*.pyo --exclude=*.pyd --exclude=.venv --exclude=venv --exclude=env --exclude=.git --exclude=.gitignore --exclude=.idea --exclude=.vscode --exclude=*.log --exclude=*.log.* --exclude=hls --exclude=screenshots --exclude=data --exclude=logs --exclude=.pytest_cache --exclude=*.egg-info --exclude=dist --exclude=build --exclude=.mypy_cache --exclude=.ruff_cache

%RSYNC_CMD% -avz --delete --progress %EXCLUDE_ARGS% "%LOCAL_DIR%" %SERVER%:%TARGET_DIR%/%PROJECT_NAME%/

if %ERRORLEVEL%==0 (
    echo.
    echo 代码同步完成！
    echo.
    echo 下一步操作：
    echo   1. SSH 连接到服务器: ssh %SERVER%
    echo   2. 进入项目目录: cd %TARGET_DIR%/%PROJECT_NAME%
    echo   3. 运行部署脚本: sudo ./deploy_and_start.sh
    echo.
) else (
    echo.
    echo 代码同步失败，请检查网络连接和服务器权限
    exit /b 1
)

