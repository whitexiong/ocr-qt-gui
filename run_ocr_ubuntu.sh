#!/bin/bash

# OCR Camera 运行脚本 (Ubuntu)
# 此脚本与打包后的应用一起发送给客户

set -e

echo "=== OCR Camera 启动器 ==="

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR"

# 检查应用文件是否存在
if [ ! -f "$APP_DIR/OCRCamera" ]; then
    echo "错误: 找不到OCRCamera可执行文件"
    echo "请确保此脚本与OCRCamera应用在同一目录下"
    exit 1
fi

# 检查并安装必要的系统依赖
echo "检查系统依赖..."
MISSING_DEPS=()

# 检查Qt相关库
if ! ldconfig -p | grep -q libQt6; then
    if ! ldconfig -p | grep -q libQt5; then
        MISSING_DEPS+=("qt6-base-dev 或 qt5-default")
    fi
fi

# 检查其他必要库
REQUIRED_LIBS=("libgl1-mesa-glx" "libglib2.0-0" "libxcb-xinerama0" "libfontconfig1")
for lib in "${REQUIRED_LIBS[@]}"; do
    if ! dpkg -l | grep -q "$lib"; then
        MISSING_DEPS+=("$lib")
    fi
done

# 如果有缺失的依赖，提示安装
if [ ${#MISSING_DEPS[@]} -ne 0 ]; then
    echo "检测到缺失的系统依赖，正在安装..."
    echo "需要安装: ${MISSING_DEPS[*]}"
    
    if command -v sudo &> /dev/null; then
        sudo apt update
        sudo apt install -y "${MISSING_DEPS[@]}"
    else
        echo "请手动安装以下依赖:"
        echo "apt update && apt install -y ${MISSING_DEPS[*]}"
        exit 1
    fi
fi

# 设置执行权限
chmod +x "$APP_DIR/OCRCamera"

# 设置环境变量
export QT_QPA_PLATFORM=xcb
export QT_X11_NO_MITSHM=1

# 检查显示环境
if [ -z "$DISPLAY" ]; then
    echo "警告: 未设置DISPLAY环境变量"
    echo "如果您使用SSH连接，请使用 ssh -X 或设置 DISPLAY 变量"
fi

echo "启动OCR Camera应用..."
echo "应用路径: $APP_DIR/OCRCamera"

# 切换到应用目录并启动
cd "$APP_DIR"
./OCRCamera

echo "应用已退出"