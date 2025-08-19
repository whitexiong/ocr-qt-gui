#!/bin/bash

# OCR Camera 应用一键安装脚本 (Ubuntu)
# 使用方法: curl -fsSL https://your-server.com/install_ubuntu.sh | bash

set -e

echo "=== OCR Camera 应用安装器 ==="
echo "正在为Ubuntu系统安装OCR Camera应用..."

# 检查系统要求
echo "检查系统要求..."

# 检查是否为Ubuntu/Debian系统
if ! command -v apt &> /dev/null; then
    echo "错误: 此脚本仅支持Ubuntu/Debian系统"
    exit 1
fi

# 安装必要的依赖
echo "安装系统依赖..."
sudo apt update
sudo apt install -y wget curl unzip libgl1-mesa-glx libglib2.0-0 libxcb-xinerama0 libfontconfig1 libx11-xcb1 libxcb-glx0 libxcb-render0 libxcb-render-util0 libxcb-randr0 libxcb-image0 libxcb-keysyms1 libxcb-icccm4

# 创建应用目录
APP_DIR="$HOME/OCRCamera"
echo "创建应用目录: $APP_DIR"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# 下载应用包 (你需要将压缩包上传到服务器)
DOWNLOAD_URL="https://your-server.com/OCRCamera.tar.gz"  # 替换为你的下载链接
echo "下载应用包..."

if command -v wget &> /dev/null; then
    wget -O OCRCamera.tar.gz "$DOWNLOAD_URL"
elif command -v curl &> /dev/null; then
    curl -L -o OCRCamera.tar.gz "$DOWNLOAD_URL"
else
    echo "错误: 需要wget或curl来下载文件"
    exit 1
fi

# 解压应用
echo "解压应用..."
tar -xzf OCRCamera.tar.gz
rm OCRCamera.tar.gz

# 设置执行权限
chmod +x OCRCamera/OCRCamera

# 创建桌面快捷方式
DESKTOP_FILE="$HOME/Desktop/OCRCamera.desktop"
echo "创建桌面快捷方式..."
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=OCR Camera
Comment=OCR摄像头应用
Exec=$APP_DIR/OCRCamera/OCRCamera
Icon=$APP_DIR/OCRCamera/logo.png
Terminal=false
StartupNotify=true
Categories=Graphics;Photography;
EOF

chmod +x "$DESKTOP_FILE"

# 创建启动脚本
LAUNCHER_SCRIPT="$HOME/bin/ocr-camera"
mkdir -p "$HOME/bin"
cat > "$LAUNCHER_SCRIPT" << EOF
#!/bin/bash
cd "$APP_DIR/OCRCamera"
./OCRCamera
EOF
chmod +x "$LAUNCHER_SCRIPT"

# 添加到PATH (如果还没有)
if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
    echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
    echo "已将 $HOME/bin 添加到PATH"
fi

echo ""
echo "=== 安装完成! ==="
echo "应用已安装到: $APP_DIR"
echo ""
echo "启动方式:"
echo "1. 双击桌面图标"
echo "2. 在终端运行: ocr-camera"
echo "3. 直接运行: $APP_DIR/OCRCamera/OCRCamera"
echo ""
echo "正在启动应用..."
cd "$APP_DIR/OCRCamera"
./OCRCamera &

echo "安装完成！应用正在启动中..."